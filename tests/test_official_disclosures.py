import unittest

from scripts.official_disclosures import adapt_official_disclosure


def notice(url, symbol="000776.SZ"):
    return {
        "symbol": symbol,
        "title": "SYNTHETIC ANNOUNCEMENT",
        "url": url,
        "announcement_date": "2026-10-29",
    }


class OfficialDisclosureAdapterTests(unittest.TestCase):
    def test_cninfo_candidate_not_verified(self):
        result = adapt_official_disclosure(
            notice("https://static.cninfo.com.cn/finalpage/test.pdf"),
            source="cninfo", analysis_date="2026-10-30")
        self.assertEqual(result["provider"], "CNINFO")
        self.assertTrue(result["source_domain_allowlisted"])
        self.assertFalse(result["source_content_verified"])
        self.assertFalse(result["publication_time_verified"])

    def test_sse_symbol_accepted(self):
        result = adapt_official_disclosure(
            notice("https://www.sse.com.cn/disclosure/test.pdf", "600519.SS"),
            source="sse", analysis_date="2026-10-30")
        self.assertEqual(result["symbol"], "600519.SS")

    def test_exchange_symbol_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "SSE notice"):
            adapt_official_disclosure(
                notice("https://www.sse.com.cn/test.pdf"),
                source="sse", analysis_date="2026-10-30")

    def test_lookalike_hostname_rejected(self):
        for url in (
            "https://static.cninfo.com.cn.evil.example/test.pdf",
            "https://evil.example/static.cninfo.com.cn/test.pdf",
            "https://www.cninfo.com.cn@evil.example/test.pdf",
            "http://static.cninfo.com.cn/test.pdf",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                adapt_official_disclosure(notice(url), source="cninfo",
                                          analysis_date="2026-10-30")

    def test_cross_source_host_rejected(self):
        with self.assertRaises(ValueError):
            adapt_official_disclosure(
                notice("https://www.sse.com.cn/test.pdf"),
                source="cninfo", analysis_date="2026-10-30")

    def test_future_announcement_rejected(self):
        item = notice("https://static.cninfo.com.cn/test.pdf")
        item["announcement_date"] = "2026-11-01"
        with self.assertRaises(ValueError):
            adapt_official_disclosure(item, source="cninfo",
                                      analysis_date="2026-10-30")


if __name__ == "__main__":
    unittest.main()
