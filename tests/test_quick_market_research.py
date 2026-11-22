from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.quick_market_research import build_quick_research_package, main
from tests.test_batch_calendar_research import job

NOW=datetime(2026,11,22,tzinfo=timezone.utc)


def calendar(start,end,*,now=None):
    return job('000776.SZ')['config']['calendar']['sessions'], {'interface':'SYNTHETIC_calendar','full_date_list_sha256':'a'*64}


def price(symbol,*args,**kwargs):
    return job(symbol)['config']['snapshot']


class QuickResearchTests(unittest.TestCase):
    def build(self,**kwargs):
        return build_quick_research_package(['000776.SZ'],'eastmoney',start_date='2026-11-02',end_date='2026-11-06',
            allow_network=True,calendar_fetcher=calendar,price_fetcher=price,now=NOW,**kwargs)

    def test_separate_calendar_and_prices_produce_hash_bound_package(self):
        encoded,manifest=self.build()
        self.assertEqual((encoded,manifest),self.build())
        with ZipFile(BytesIO(encoded)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn('items/000776.SZ/dashboard.html',archive.namelist())
            record=json.loads(archive.read('calendar-source.json'))
            self.assertFalse(record['independent_source_verified'])
            self.assertFalse(record['exchange_calendar_verified'])
            for item in manifest['files']:
                data=archive.read(item['path'])
                self.assertEqual(len(data),item['size_bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])

    def test_default_window_is_recent_21_days_ending_shanghai_yesterday(self):
        calls=[]
        def sessions(start,end,*,now=None):
            calls.append((start,end))
            return calendar(start,end,now=now)
        def quotes(symbol,start,end,**kwargs):
            snapshot=price(symbol)
            snapshot.update(start_date=start,end_date=end)
            return snapshot
        _,manifest=build_quick_research_package(['000776.SZ'],'eastmoney',allow_network=True,
            calendar_fetcher=sessions,price_fetcher=quotes,now=NOW)
        self.assertEqual(calls,[('2026-11-01','2026-11-21')])
        self.assertEqual(manifest['generated_count'],1)

    def test_bad_symbols_dates_or_opt_in_never_fetch_calendar(self):
        for kwargs in ({'symbols':['../bad'],'upstream':'sina'},
                       {'symbols':['000776.SZ']*2,'upstream':'sina'},
                       {'symbols':['000776.SZ'],'upstream':'sina','end_date':'2026-11-22','start_date':'2026-11-02'},
                       {'symbols':['000776.SZ'],'upstream':'automatic'},
                       {'symbols':['000776.SZ'],'upstream':'sina','allow_network':False}):
            with patch('scripts.quick_market_research.fetch_sina_calendar') as fetcher:
                values={'allow_network':True,'now':NOW};values.update(kwargs)
                with self.assertRaises(ValueError):build_quick_research_package(**values)
                fetcher.assert_not_called()

    def test_calendar_failure_or_empty_session_never_fetches_prices(self):
        for response in (ValueError('calendar range not covered'), ([],{'interface':'none'})):
            with patch('scripts.quick_market_research.fetch_sina_calendar',side_effect=response if isinstance(response,Exception) else None,
                       return_value=response) as fetcher:
                with patch('scripts.collect_batch_research.fetch_sina_daily') as quotes:
                    with self.assertRaises(ValueError):
                        build_quick_research_package(['000776.SZ'],'sina',allow_network=True,now=NOW)
                    quotes.assert_not_called()

    def test_price_failure_returns_diagnostic_only_status(self):
        def fail(*a,**kw):raise RuntimeError('PRIVATE')
        data,manifest=build_quick_research_package(['000776.SZ'],'eastmoney',start_date='2026-11-02',end_date='2026-11-06',
            allow_network=True,calendar_fetcher=calendar,price_fetcher=fail,now=NOW)
        self.assertEqual(manifest['status'],'NO_RESEARCH_GENERATED')
        self.assertNotIn(b'PRIVATE',data)
        with ZipFile(BytesIO(data)) as archive:
            self.assertFalse(any(name.endswith('/dashboard.html') for name in archive.namelist()))

    def test_cli_output_preflight_and_concurrent_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'result.zip'
            args=['--symbols','000776.SZ','--upstream','eastmoney','--allow-network','--output',str(output)]
            with patch('scripts.quick_market_research.tempfile.NamedTemporaryFile',side_effect=PermissionError()):
                with patch('scripts.quick_market_research.build_quick_research_package') as builder:
                    with self.assertRaises(PermissionError):main(args)
                    builder.assert_not_called()
            package,manifest=self.build()
            def race(src,dst):Path(dst).write_bytes(b'winner');raise FileExistsError()
            with patch('scripts.quick_market_research.build_quick_research_package',return_value=(package,manifest)):
                with patch('scripts.quick_market_research.os.link',side_effect=race):
                    with self.assertRaises(FileExistsError):main(args)
            self.assertEqual(output.read_bytes(),b'winner')
            self.assertEqual(list(Path(folder).iterdir()),[output])
