from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.market_date_window import main, resolve_market_window


class MarketWindowTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 12, 7, 38, tzinfo=timezone.utc)

    def test_recent_window_is_21_inclusive_calendar_days_not_fixed_october(self):
        result = resolve_market_window(now=self.now)
        self.assertEqual((result["start_date"], result["end_date"]), ("2026-10-22", "2026-11-11"))
        self.assertFalse(result["exchange_calendar_checked"])

    def test_shanghai_midnight_and_year_boundary(self):
        result = resolve_market_window(now=datetime(2026, 12, 31, 17, tzinfo=timezone.utc))
        self.assertEqual(result["end_date"], "2026-12-31")
        result = resolve_market_window(now=datetime(2026, 11, 12, 17, tzinfo=timezone.utc))
        self.assertEqual(result["end_date"], "2026-11-12")

    def test_explicit_history_is_preserved(self):
        result = resolve_market_window("2026-10-01", "2026-10-30", now=self.now)
        self.assertEqual(result["start_date"], "2026-10-01")
        self.assertEqual(result["end_date"], "2026-10-30")
        self.assertEqual(result["mode"], "explicit_history")

    def test_partial_future_reversed_oversized_noncanonical_dates_rejected(self):
        for start, end in (("2026-10-01", None), (None, "2026-10-30"),
                           ("2026-11-12", "2026-11-12"), ("2026-11-11", "2026-11-01"),
                           ("2024-01-01", "2026-10-30"), ("20261001", "2026-10-30"),
                           ("2026-02-30", "2026-10-30"), ("\nX=1", "2026-10-30")):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                resolve_market_window(start, end, now=self.now)
        with self.assertRaises(ValueError):
            resolve_market_window(now=datetime(2026, 11, 12))

    def test_environment_output_contains_only_validated_values(self):
        out = io.StringIO()
        with patch.dict("os.environ", {"REQUEST_START_DATE": "2026-10-01", "REQUEST_END_DATE": "2026-10-30"}), redirect_stdout(out):
            self.assertEqual(main(), 0)
        self.assertEqual(out.getvalue(), "STOCK_START_DATE=2026-10-01\nSTOCK_END_DATE=2026-10-30\n")
        out = io.StringIO()
        with patch.dict("os.environ", {"REQUEST_START_DATE": "\nX=1", "REQUEST_END_DATE": "2026-10-30"}), redirect_stdout(out):
            with self.assertRaises(ValueError):
                main()
        self.assertEqual(out.getvalue(), "")

    def test_workflow_resolves_every_trigger_before_optional_collection_setup(self):
        text = (Path(__file__).resolve().parents[1]/".github/workflows/akshare-dual-crosscheck.yml").read_text()
        self.assertNotIn("2026-10-01", text)
        self.assertNotIn("2026-10-30", text)
        self.assertNotIn("if: github.event_name == 'schedule'", text)
        self.assertIn('python -m scripts.market_date_window >> "$GITHUB_ENV"', text)
        self.assertLess(text.index("Resolve validated market date window"), text.index("Install optional read-only"))
