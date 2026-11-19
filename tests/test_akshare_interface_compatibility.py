"""Offline current/legacy API contracts; no vendor calls or paid inference."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

from scripts.akshare_provider import fetch_a_share_daily
from scripts.akshare_sina_provider import fetch_sina_daily
from scripts.akshare_dual_smoke import run
from scripts.akshare_crosscheck import compare
from scripts.akshare_snapshot_quality import check_snapshot
from scripts.backtest_data_contract import build_backtest_dataset


class Frame:
    def __init__(self, rows):
        self.rows = rows
    def to_dict(self, orient):
        assert orient == 'records'
        return self.rows


EAST = [{'日期':'2026-11-02','开盘':10,'最高':12,'最低':9,'收盘':11,'成交量':25}]
SINA = [{'date':'2026-11-02','open':10,'high':12,'low':9,'close':11,'volume':2500}]


class InterfaceCompatibilityTests(unittest.TestCase):
    def test_eastmoney_current_and_legacy_keep_called_interface_and_lot_units(self):
        for name in ('stock_zh_a_hist_em','stock_zh_a_hist'):
            function = Mock(return_value=Frame(EAST))
            client = SimpleNamespace(**{name:function,'__version__':'SYNTHETIC_CLIENT'})
            result = fetch_a_share_daily('000776.SZ','2026-11-02','2026-11-02',client=client)
            self.assertEqual(result['interface'],name)
            self.assertEqual(result['volume_unit'],'lots_100_shares')
            function.assert_called_once_with(symbol='000776',period='daily',start_date='20261102',end_date='20261102',adjust='')
            self.assertEqual(check_snapshot(result)['status'],'passed')
            dataset = build_backtest_dataset(result,evidence_as_of=result['retrieved_at'],expected_adjustment='unadjusted')
            self.assertEqual(dataset['provenance']['interface'],name)
            self.assertEqual(dataset['bars'][0]['volume'],2500)

    def test_sina_three_generations_keep_share_units_and_only_hist_gets_period(self):
        for name in ('stock_zh_a_hist_sina','stock_zh_a_daily_sina','stock_zh_a_daily'):
            function = Mock(return_value=Frame(SINA))
            client = SimpleNamespace(**{name:function,'__version__':'SYNTHETIC_CLIENT'})
            result = fetch_sina_daily('000776.SZ','2026-11-02','2026-11-02',client=client)
            self.assertEqual(result['interface'],name)
            self.assertEqual(result['volume_unit'],'shares')
            expected={'symbol':'sz000776','start_date':'20261102','end_date':'20261102','adjust':''}
            if name=='stock_zh_a_hist_sina':
                expected['period']='daily'
            function.assert_called_once_with(**expected)
            dataset=build_backtest_dataset(result,evidence_as_of=result['retrieved_at'],expected_adjustment='unadjusted')
            self.assertEqual(dataset['provenance']['interface'],name)
            self.assertEqual(dataset['bars'][0]['volume'],2500)

    def test_current_api_has_priority_and_call_failures_do_not_switch_names(self):
        for fetch,new,old,rows in ((fetch_a_share_daily,'stock_zh_a_hist_em','stock_zh_a_hist',EAST),
                                   (fetch_sina_daily,'stock_zh_a_hist_sina','stock_zh_a_daily',SINA)):
            current,legacy=Mock(side_effect=ValueError('provider failed')),Mock(return_value=Frame(rows))
            client=SimpleNamespace(**{new:current,old:legacy})
            with self.assertRaises(ValueError):
                fetch('000776.SZ','2026-11-02','2026-11-02',client=client)
            legacy.assert_not_called()
            self.assertEqual(current.call_count,1)

    def test_missing_noncallable_and_rename_hint_attributes_are_safe_dependency_errors(self):
        class Renamed:
            def __getattr__(self,name):
                raise AttributeError('SECRET upstream URL in rename message')
        for client in (SimpleNamespace(),SimpleNamespace(stock_zh_a_hist_em='not_callable'),Renamed()):
            for fetch in (fetch_a_share_daily,fetch_sina_daily):
                with self.assertRaises(RuntimeError):
                    fetch('000776.SZ','2026-11-02','2026-11-02',client=client)

    def test_noncallable_current_attribute_does_not_silently_fall_back(self):
        legacy=Mock(return_value=Frame(EAST))
        client=SimpleNamespace(stock_zh_a_hist_em='invalid',stock_zh_a_hist=legacy)
        with self.assertRaises(RuntimeError):
            fetch_a_share_daily('000776.SZ','2026-11-02','2026-11-02',client=client)
        legacy.assert_not_called()

    def test_new_interfaces_still_reject_wrong_columns_and_mismatched_units(self):
        client=SimpleNamespace(stock_zh_a_hist_em=Mock(return_value=Frame(SINA)))
        with self.assertRaises(ValueError):
            fetch_a_share_daily('000776.SZ','2026-11-02','2026-11-02',client=client)
        client=SimpleNamespace(stock_zh_a_hist_sina=Mock(return_value=Frame(SINA)))
        result=fetch_sina_daily('000776.SZ','2026-11-02','2026-11-02',client=client)
        result['volume_unit']='lots_100_shares'
        with self.assertRaises(ValueError):
            build_backtest_dataset(result,evidence_as_of=result['retrieved_at'],expected_adjustment='unadjusted')

    def test_missing_attribute_cannot_abort_other_source_or_leak_error_text(self):
        def missing(*args):
            raise AttributeError('SECRET upstream URL')
        client=SimpleNamespace(stock_zh_a_hist_sina=Mock(return_value=Frame(SINA)))
        def sina(*args):
            return fetch_sina_daily(*args,client=client)
        with tempfile.TemporaryDirectory() as folder:
            result=run('000776.SZ','2026-11-02','2026-11-02',folder,eastmoney=missing,sina=sina,
                       sleep=lambda _:self.fail('interface errors must not retry'))
            self.assertEqual(result,1)
            raw=(Path(folder)/'dual_upstream_diagnostics.json').read_text()
            diag=json.loads(raw)
            self.assertEqual(diag['eastmoney_attempts'],1)
            self.assertEqual(diag['eastmoney_error_kind'],'interface_unavailable')
            self.assertEqual(diag['sina_status'],'success')
            self.assertNotIn('SECRET',raw)
            self.assertFalse(diag['cross_source_numerical_agreement'])

    def test_new_names_numerically_compare_using_explicit_units(self):
        east=fetch_a_share_daily('000776.SZ','2026-11-02','2026-11-02',
            client=SimpleNamespace(stock_zh_a_hist_em=Mock(return_value=Frame(EAST))))
        sina=fetch_sina_daily('000776.SZ','2026-11-02','2026-11-02',
            client=SimpleNamespace(stock_zh_a_hist_sina=Mock(return_value=Frame(SINA))))
        self.assertEqual(compare(east,sina)['status'],'passed')
        self.assertFalse(compare(east,sina)['independent_source_verified'])
