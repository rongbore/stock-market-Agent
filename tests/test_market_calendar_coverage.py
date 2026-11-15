import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.collect_market_research import collect_market_research, main
from scripts.market_calendar_coverage import check_calendar_coverage, validate_calendar

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    s = json.loads((ROOT / 'examples/backtest/SYNTHETIC_sma_oos_config.json').read_text())['snapshot']
    c = {'schema_version': '0.1', 'exchange': s['symbol'][-2:],
         'start_date': s['start_date'], 'end_date': s['end_date'],
         'source': 'SYNTHETIC test calendar, not an exchange calendar',
         'sessions': [r['date'] for r in s['records']]}
    return s, c


class CalendarCoverageTests(unittest.TestCase):
    def collect(self, s, c):
        return collect_market_research(s['symbol'], s['start_date'], s['end_date'],
                                      'eastmoney', calendar=c, fetcher=lambda *a, **kw: s)

    def test_matching_dates_allow_research_without_verification_claim(self):
        s, c = fixture()
        result = self.collect(s, c)
        self.assertEqual(result['status'], 'COLLECTED_RESEARCH_UNVERIFIED')
        coverage = result['calendar_coverage']
        self.assertEqual(coverage['status'], 'MATCH')
        self.assertFalse(coverage['exchange_calendar_verified'])
        self.assertEqual(len(coverage['calendar_sha256']), 64)
        changed = copy.deepcopy(c)
        changed['source'] += ' changed'
        self.assertNotEqual(coverage['calendar_sha256'], check_calendar_coverage(changed, s)['calendar_sha256'])

    def test_missing_and_unexpected_dates_block_downstream(self):
        for mode in ('missing', 'unexpected'):
            s, c = fixture()
            if mode == 'missing':
                expected = s['records'].pop(1)['date']
            else:
                expected = c['sessions'].pop(1)
            with self.subTest(mode=mode), patch('scripts.collect_market_research.build_pipeline') as pipeline:
                result = self.collect(s, c)
                self.assertEqual(result['status'], 'FAILED')
                self.assertEqual(result['stage'], 'calendar_coverage')
                self.assertIn(expected, result['calendar_coverage'][mode + '_dates'])
                self.assertNotIn('research', result)
                pipeline.assert_not_called()

    def test_invalid_calendar_never_calls_fetcher(self):
        s, original = fixture()
        invalid = []
        for field, value in [('exchange', 'XX'), ('start_date', '2000-01-01'),
                             ('source', ''), ('sessions', ['20261101']),
                             ('sessions', ['2000-01-01']), ('sessions', [None]),
                             ('sessions', original['sessions'] * 2),
                             ('sessions', list(reversed(original['sessions'])))]:
            c = copy.deepcopy(original)
            c[field] = value
            invalid.append(c)
        c = copy.deepcopy(original)
        c['verified'] = True
        invalid.append(c)
        for c in invalid:
            with self.subTest(calendar=c), patch('scripts.collect_market_research.fetch_a_share_daily') as fetcher:
                with self.assertRaises(ValueError):
                    collect_market_research(s['symbol'], s['start_date'], s['end_date'], 'eastmoney', calendar=c)
                fetcher.assert_not_called()

    def test_duplicate_snapshot_dates_rejected(self):
        s, c = fixture()
        s['records'].append(s['records'][0])
        with self.assertRaises(ValueError):
            check_calendar_coverage(c, s)

    def test_empty_calendar_does_not_accept_nonempty_snapshot(self):
        s, c = fixture()
        c['sessions'] = []
        self.assertEqual(self.collect(s, c)['status'], 'FAILED')

    def test_cli_calendar_failure_writes_diagnostic_and_exit_two(self):
        s, c = fixture()
        s['records'].pop(1)
        with tempfile.TemporaryDirectory() as folder:
            calendar, output = Path(folder)/'calendar.json', Path(folder)/'output.json'
            calendar.write_text(json.dumps(c))
            args = ['--symbol', s['symbol'], '--start-date', s['start_date'],
                    '--end-date', s['end_date'], '--upstream', 'eastmoney',
                    '--allow-network', '--calendar', str(calendar), '--output', str(output)]
            with patch('scripts.collect_market_research.fetch_a_share_daily', return_value=s):
                self.assertEqual(main(args), 2)
            self.assertEqual(json.loads(output.read_text())['reason'], 'calendar_date_mismatch')
            output.unlink()
            for raw in ['{"sessions":[],"sessions":[]}', 'x' * 65537]:
                calendar.write_text(raw)
                with patch('scripts.collect_market_research.fetch_a_share_daily') as fetcher:
                    with self.assertRaises(ValueError):
                        main(args)
                    fetcher.assert_not_called()
                self.assertFalse(output.exists())
