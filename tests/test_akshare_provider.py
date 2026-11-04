import unittest
from unittest.mock import Mock

from scripts.akshare_provider import fetch_a_share_daily, fetch_cninfo_disclosure_index


class Frame:
    columns = ["日期", "开盘", "收盘", "最高", "最低", "成交量"]

    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


class AKShareProviderTests(unittest.TestCase):
    def test_daily_offline(self):
        client = Mock()
        client.stock_zh_a_hist.return_value = Frame([
            {"日期": "2026-10-29", "开盘": 15, "收盘": 16,
             "最高": 17, "最低": 14, "成交量": 1000}])
        result = fetch_a_share_daily("000776.SZ", "2026-10-01", "2026-10-30", client=client)
        self.assertEqual(result["records"][0]["close"], 16)
        self.assertFalse(result["source_content_verified"])
        self.assertFalse(result["historical_point_in_time_verified"])
        client.stock_zh_a_hist.assert_called_once_with(
            symbol="000776", period="daily", start_date="20261001",
            end_date="20261030", adjust="")

    def test_disclosures_offline(self):
        client = Mock()
        client.stock_zh_a_disclosure_report_cninfo.return_value = Frame(
            [{"公告标题": "SYNTHETIC", "公告日期": "2026-10-29"}])
        result = fetch_cninfo_disclosure_index(
            "000776.SZ", "2026-10-01", "2026-10-30", client=client)
        self.assertEqual(result["records"][0]["公告标题"], "SYNTHETIC")
        self.assertFalse(result["source_content_verified"])

    def test_reject_bad_symbols_and_dates(self):
        for symbol in ("000776", "000776.SZ;evil", "000776.SH", "ABCDEF.SZ"):
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                fetch_a_share_daily(symbol, "2026-10-01", "2026-10-30", client=Mock())
        with self.assertRaises(ValueError):
            fetch_a_share_daily("000776.SZ", "2026-10-30", "2026-10-01", client=Mock())

    def test_reject_bad_ohlc_and_duplicate_dates(self):
        bad = {"日期": "2026-10-29", "开盘": 15, "收盘": 16,
               "最高": 14, "最低": 13, "成交量": 1000}
        client = Mock()
        client.stock_zh_a_hist.return_value = Frame([bad])
        with self.assertRaises(ValueError):
            fetch_a_share_daily("000776.SZ", "2026-10-01", "2026-10-30", client=client)
        good = dict(bad, 最高=17)
        client.stock_zh_a_hist.return_value = Frame([good, good])
        with self.assertRaises(ValueError):
            fetch_a_share_daily("000776.SZ", "2026-10-01", "2026-10-30", client=client)


if __name__ == "__main__":
    unittest.main()
