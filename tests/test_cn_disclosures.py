import unittest

from scripts.cn_disclosures import normalize_disclosure


def sample():
    return {
        "symbol": "000776.sz",
        "title": "测试公告（非真实数据）",
        "provider": "测试数据源",
        "url": "https://example.org/announcement.pdf",
        "announcement_date": "2026-10-30",
    }


class CNDisclosureTests(unittest.TestCase):
    def test_normalize(self):
        result = normalize_disclosure(sample(), analysis_date="2026-11-01")
        self.assertEqual(result["symbol"], "000776.SZ")
        self.assertFalse(result["publication_time_verified"])
        self.assertEqual(result["same_day_historical_eligibility"], "unknown")

    def test_reject_future_disclosure(self):
        with self.assertRaises(ValueError):
            normalize_disclosure(sample(), analysis_date="2026-10-29")

    def test_reject_bad_symbol(self):
        data = sample()
        data["symbol"] = "NVDA"
        with self.assertRaises(ValueError):
            normalize_disclosure(data)

    def test_reject_http(self):
        data = sample()
        data["url"] = "http://example.org"
        with self.assertRaises(ValueError):
            normalize_disclosure(data)

    def test_reject_embedded_credentials(self):
        data = sample()
        data["url"] = "https://user:password@example.org/a"
        with self.assertRaises(ValueError):
            normalize_disclosure(data)

    def test_reject_invalid_date(self):
        data = sample()
        data["announcement_date"] = "2026-13-30"
        with self.assertRaises(ValueError):
            normalize_disclosure(data)

    def test_accept_timezone_aware_publication(self):
        data = sample()
        data["published_at"] = "2026-10-30T19:00:00+08:00"
        result = normalize_disclosure(data)
        self.assertFalse(result["publication_time_verified"])

    def test_reject_naive_publication(self):
        data = sample()
        data["published_at"] = "2026-10-30T19:00:00"
        with self.assertRaises(ValueError):
            normalize_disclosure(data)


if __name__ == "__main__":
    unittest.main()
