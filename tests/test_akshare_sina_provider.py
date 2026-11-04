import unittest
from unittest.mock import Mock

from scripts.akshare_sina_provider import fetch_sina_daily


class Frame:
    def to_dict(self, orient):
        assert orient == "records"
        return [{"date": "2026-10-08", "open": 19.8, "high": 19.98,
                 "low": 19.21, "close": 19.32, "volume": 43288500}]


class SinaProviderTests(unittest.TestCase):
    def test_symbol_mapping_and_share_volume(self):
        ak = Mock()
        ak.__version__ = "test"
        ak.stock_zh_a_daily.return_value = Frame()
        result = fetch_sina_daily("000776.SZ", "2026-10-01", "2026-10-30", client=ak)
        self.assertEqual(ak.stock_zh_a_daily.call_args.kwargs["symbol"], "sz000776")
        self.assertEqual(result["upstream"], "sina")
        self.assertEqual(result["volume_unit"], "shares")
        self.assertEqual(result["records"][0]["volume"], 43288500)

    def test_rejects_duplicate_dates(self):
        class DuplicateFrame:
            def to_dict(self, orient):
                return Frame().to_dict(orient) * 2
        ak = Mock()
        ak.stock_zh_a_daily.return_value = DuplicateFrame()
        with self.assertRaises(ValueError):
            fetch_sina_daily("000776.SZ", "2026-10-01", "2026-10-30", client=ak)


if __name__ == "__main__":
    unittest.main()
