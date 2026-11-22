from datetime import date, datetime, timezone
import hashlib
import unittest
from unittest.mock import patch

from scripts.market_calendar_provider import fetch_sina_calendar
from scripts.offline_batch_research_runner import _canonical_json_bytes

NOW = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
DATES = ['2026-10-30', '2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06', '2026-11-09']


class Frame:
    def __init__(self, rows):
        self.rows = rows
    def to_dict(self, orient):
        if orient != 'records':
            raise AssertionError('unexpected record orientation')
        return self.rows


class CurrentClient:
    __version__ = 'SYNTHETIC client'
    def __init__(self, rows=None):
        self.calls = 0
        self.rows = rows if rows is not None else [{'trade_date': date.fromisoformat(d)} for d in DATES]
    def calendar_trade_date_hist_sina(self):
        self.calls += 1
        return Frame(self.rows)


class CalendarProviderTests(unittest.TestCase):
    def test_current_interface_normalizes_dates_and_hashes_full_list(self):
        client = CurrentClient()
        sessions, metadata = fetch_sina_calendar('2026-11-02', '2026-11-06', client=client, now=NOW)
        self.assertEqual(sessions, DATES[1:-1])
        self.assertEqual(client.calls, 1)
        self.assertEqual(metadata['interface'], 'calendar_trade_date_hist_sina')
        self.assertEqual(metadata['full_date_count'], 7)
        self.assertEqual(metadata['full_date_list_sha256'], hashlib.sha256(_canonical_json_bytes(DATES)).hexdigest())
        self.assertEqual(metadata['retrieved_at'], NOW.isoformat())
        self.assertFalse(metadata['exchange_calendar_verified'])
        self.assertFalse(metadata['independent_source_verified'])
        self.assertIn('SS/SZ', metadata['limitations'][2])

    def test_legacy_selected_only_for_missing_current_attribute(self):
        class Legacy:
            def tool_trade_date_hist_sina(self):
                return Frame([{'trade_date': d} for d in DATES])
        _, metadata = fetch_sina_calendar('2026-11-02', '2026-11-06', client=Legacy(), now=NOW)
        self.assertEqual(metadata['interface'], 'tool_trade_date_hist_sina')
        class Both(Legacy):
            calendar_trade_date_hist_sina = None
            def tool_trade_date_hist_sina(self):
                raise AssertionError('must not fallback from noncallable current attribute')
        with self.assertRaises(RuntimeError):
            fetch_sina_calendar('2026-11-02', '2026-11-06', client=Both(), now=NOW)

    def test_call_failure_never_changes_interface(self):
        class Both:
            def calendar_trade_date_hist_sina(self):
                raise ValueError('provider failure')
            def tool_trade_date_hist_sina(self):
                raise AssertionError('must not fallback from selected call failure')
        with self.assertRaisesRegex(ValueError, 'provider failure'):
            fetch_sina_calendar('2026-11-02', '2026-11-06', client=Both(), now=NOW)

    def test_invalid_request_precedes_client_loading(self):
        for start, end, now in [('20261102', '2026-11-06', NOW), ('2026-11-06', '2026-11-02', NOW),
                                ('2026-11-02', '2026-11-22', NOW), ('2025-01-01', '2026-11-06', NOW),
                                ('2026-11-02', '2026-11-06', datetime(2026, 11, 22))]:
            with self.subTest(start=start, end=end, now=now), patch('scripts.market_calendar_provider._client') as loader:
                with self.assertRaises(ValueError):
                    fetch_sina_calendar(start, end, now=now)
                loader.assert_not_called()

    def test_empty_duplicate_unsorted_noncanonical_and_wrong_columns_rejected(self):
        for rows in [[], [{'trade_date': '2026-11-02'}]*2,
                     [{'trade_date': d} for d in reversed(DATES)],
                     [{'trade_date': '20261102'}], [{'other': '2026-11-02'}],
                     [{'trade_date': None}]]:
            with self.subTest(rows=str(rows)[:60]), self.assertRaises(ValueError):
                fetch_sina_calendar('2026-11-02', '2026-11-06', client=CurrentClient(rows), now=NOW)
        with patch('scripts.market_calendar_provider.MAX_CALENDAR_DATES', 2):
            with self.assertRaises(ValueError):
                fetch_sina_calendar('2026-11-02', '2026-11-06', client=CurrentClient(), now=NOW)

    def test_inadequate_range_not_silently_truncated(self):
        for dates in [DATES[2:], DATES[:-2]]:
            with self.subTest(dates=dates), self.assertRaisesRegex(ValueError, 'does not cover'):
                fetch_sina_calendar('2026-11-02', '2026-11-06',
                                    client=CurrentClient([{'trade_date': d} for d in dates]), now=NOW)

    def test_empty_window_is_not_invented_from_weekdays(self):
        sessions, metadata = fetch_sina_calendar('2026-11-07', '2026-11-08', client=CurrentClient(), now=NOW)
        self.assertEqual(sessions, [])
        self.assertEqual(metadata['window_session_count'], 0)

    def test_missing_interface_and_unexpected_response_rejected(self):
        with self.assertRaises(RuntimeError):
            fetch_sina_calendar('2026-11-02', '2026-11-06', client=object(), now=NOW)
        class Bad:
            def calendar_trade_date_hist_sina(self):
                return []
        with self.assertRaises(ValueError):
            fetch_sina_calendar('2026-11-02', '2026-11-06', client=Bad(), now=NOW)
