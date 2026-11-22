"""User-visible provenance is rendered from the already collected evidence."""
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
import unittest
from zipfile import ZipFile

from scripts.batch_research_package import _index
from scripts.collect_batch_research import build_collected_batch_package
from scripts.quick_market_research import build_quick_research_package
from tests.test_collect_batch_research import NOW, fetched, request
from tests.test_quick_market_research import calendar


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.targets.extend(value for key, value in attrs if key == 'href')


class ResearchResultContextTests(unittest.TestCase):
    def inspect(self, encoded, manifest):
        with ZipFile(BytesIO(encoded)) as archive:
            page = archive.read('index.html').decode()
            links = Links()
            links.feed(page)
            self.assertTrue(links.targets)
            for target in links.targets:
                self.assertIn(target, archive.namelist())
            self.assertNotIn('<script', page)
            self.assertNotIn('src=', page)
            for entry in manifest['files']:
                data = archive.read(entry['path'])
                self.assertEqual(len(data), entry['size_bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
            return page, json.loads(archive.read('batch-result.json')), json.loads(archive.read('collection.json'))

    def test_source_requested_vs_observed_dates_and_missing_sessions(self):
        config = request()
        def provider(*args, **kwargs):
            snapshot = fetched(*args, **kwargs)
            snapshot['records'].pop(0)
            return snapshot
        encoded, manifest = build_collected_batch_package(config, allow_network=True, fetcher=provider, now=NOW)
        page, batch, collection = self.inspect(encoded, manifest)
        item = collection['items'][0]
        self.assertIn('行情来源：东方财富（eastmoney）（单一来源，未核验）', page)
        self.assertIn('请求窗口：2026-11-02 至 2026-11-06', page)
        self.assertIn('实际有数据日期：2026-11-03 至 2026-11-06', page)
        self.assertIn('采集条数：4', page)
        self.assertIn(item['retrieved_at'], page)
        self.assertIn(item['interface'], page)
        self.assertIn('缺失日期（1）：2026-11-02', page)
        self.assertIn('额外日期（0）：无', page)
        self.assertNotIn('/dashboard.html', page)
        self.assertEqual(batch['calendar_blocked_count'], 1)

    def test_non_session_window_end_is_not_reported_as_missing(self):
        config = request()
        config['end_date'] = '2026-11-08'
        config['items'][0]['calendar']['end_date'] = '2026-11-08'
        def provider(*args, **kwargs):
            snapshot = fetched(*args, **kwargs)
            snapshot['end_date'] = '2026-11-08'
            return snapshot
        encoded, manifest = build_collected_batch_package(config, allow_network=True, fetcher=provider, now=NOW)
        page, batch, _ = self.inspect(encoded, manifest)
        self.assertEqual(batch['generated_count'], 1)
        self.assertIn('请求窗口：2026-11-02 至 2026-11-08', page)
        self.assertIn('实际有数据日期：2026-11-02 至 2026-11-06', page)
        self.assertNotIn('返回日期与提供的日历不一致', page)

    def test_extra_date_reports_difference_from_sessions_not_window(self):
        config = request()
        config['items'][0]['calendar']['sessions'].pop(1)
        encoded, manifest = build_collected_batch_package(config, allow_network=True, fetcher=fetched, now=NOW)
        page, _, _ = self.inspect(encoded, manifest)
        self.assertIn('缺失日期（0）：无', page)
        self.assertIn('额外日期（1）：2026-11-03', page)

    def test_failure_reasons_are_chinese_and_never_exception_details(self):
        def fail(*args, **kwargs):
            raise RuntimeError('SECRET<script>alert(1)</script>')
        encoded, manifest = build_collected_batch_package(request(), allow_network=True, fetcher=fail, now=NOW)
        page, _, _ = self.inspect(encoded, manifest)
        self.assertIn('供应商采集失败，未取得可用数据', page)
        self.assertNotIn('SECRET', page)
        self.assertNotIn('/dashboard.html', page)
        def invalid(*args, **kwargs):
            snapshot = fetched(*args, **kwargs)
            snapshot['volume_unit'] = 'INVALID'
            return snapshot
        encoded, manifest = build_collected_batch_package(request(), allow_network=True, fetcher=invalid, now=NOW)
        page, _, _ = self.inspect(encoded, manifest)
        self.assertIn('快照结构、来源、时间或单位校验失败', page)

    def test_context_values_escape_and_unknown_reason_has_safe_fallback(self):
        encoded, manifest = build_collected_batch_package(request(), allow_network=True, fetcher=fetched, now=NOW)
        _, batch, collection = self.inspect(encoded, manifest)
        injected = '<img src=x onerror="alert(1)">'
        item = collection['items'][0]
        for field in ('observed_start', 'observed_end', 'interface', 'retrieved_at', 'record_count'):
            item[field] = injected
        item['reason'] = 'PRIVATE_UNKNOWN_REASON'
        collection['request']['start_date'] = injected
        metadata = {'interface': injected, 'retrieved_at': injected, 'observed_start': injected}
        page = _index(batch, collection=collection, calendar_source={'vendor_metadata_supplied_unverified': metadata})
        self.assertNotIn(injected, page)
        self.assertIn('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;', page)
        self.assertIn('需要核查，详见诊断', page)
        self.assertNotIn('PRIVATE_UNKNOWN_REASON', page)

    def test_quick_calendar_link_and_scope_survive_manifest_rehash_without_refetch(self):
        calls = []
        def sessions(*args, **kwargs):
            calls.append('calendar')
            dates, metadata = calendar(*args, **kwargs)
            metadata.update(observed_start='1990-12-19', observed_end='2026-12-31', retrieved_at=NOW.isoformat())
            return dates, metadata
        def prices(*args, **kwargs):
            calls.append('price')
            return fetched(*args, **kwargs)
        encoded, manifest = build_quick_research_package(['000776.SZ'], 'eastmoney',
            start_date='2026-11-02', end_date='2026-11-06', allow_network=True,
            calendar_fetcher=sessions, price_fetcher=prices, now=NOW)
        page, _, _ = self.inspect(encoded, manifest)
        self.assertEqual(calls, ['calendar', 'price'])
        self.assertIn('href="calendar-source.json"', page)
        self.assertIn('覆盖范围：1990-12-19 至 2026-12-31；窗口内日期数：5', page)
        self.assertIn('交易所日历已核验：否；独立来源已核验：否', page)
        self.assertIn('同一供应商日历用于 SS/SZ 是未核验假设', page)
