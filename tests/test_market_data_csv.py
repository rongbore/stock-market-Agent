"""Market CSV reuses validated bars and never exports failed research items."""
import csv
from datetime import datetime
import hashlib
from io import BytesIO, StringIO
import json
import unittest
from zipfile import ZipFile

from scripts.batch_research_package import build_batch_research_package
from scripts.collect_batch_research import build_collected_batch_package
from scripts.quick_market_research import build_quick_research_package
from tests.test_batch_calendar_research import batch, job
from tests.test_collect_batch_research import NOW, fetched, request
from tests.test_quick_market_research import calendar


class MarketDataCsvTests(unittest.TestCase):
    def inspect(self, encoded, manifest):
        with ZipFile(BytesIO(encoded)) as archive:
            page = archive.read('index.html').decode()
            for entry in manifest['files']:
                data = archive.read(entry['path'])
                self.assertEqual(entry['size_bytes'], len(data))
                self.assertEqual(entry['sha256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(json.loads(archive.read('manifest.json')), manifest)
            if 'market-data.csv' not in archive.namelist():
                self.assertNotIn('href="market-data.csv"', page)
                return None
            data = archive.read('market-data.csv')
            self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
            self.assertIn('href="market-data.csv"', page)
            self.assertIn('人民币/股', page)
            self.assertIn('成交量单位为股', page)
            return list(csv.DictReader(StringIO(data.decode('utf-8-sig'), newline='')))

    def test_eastmoney_normalized_volume_units_source_and_deterministic_order(self):
        calls = []
        def prices(symbol, *args, **kwargs):
            calls.append(symbol)
            return fetched(symbol)
        config = request('600519.SS', '000776.SZ')
        encoded, manifest = build_collected_batch_package(config, allow_network=True, fetcher=prices, now=NOW)
        self.assertEqual(calls, ['000776.SZ', '600519.SS'])
        self.assertEqual((encoded, manifest), build_collected_batch_package(config, allow_network=True, fetcher=fetched, now=NOW))
        rows = self.inspect(encoded, manifest)
        self.assertEqual(len(rows), 10)
        self.assertEqual([(r['symbol'], r['date']) for r in rows], sorted((r['symbol'], r['date']) for r in rows))
        original = fetched('000776.SZ')['records'][0]
        row = rows[0]
        for key in ('open', 'high', 'low', 'close'):
            self.assertEqual(float(row[key]), original[key])
        self.assertEqual(float(row['volume']), original['volume'] * 100)
        for key, value in (('price_unit', 'CNY_per_share'), ('volume_unit', 'shares'),
                           ('adjustment', 'unadjusted'), ('source', 'akshare'), ('upstream', 'eastmoney')):
            self.assertEqual(row[key], value)
        self.assertEqual(row['interface'], fetched('000776.SZ')['interface'])
        self.assertIsNotNone(datetime.fromisoformat(row['retrieved_at']).utcoffset())
        self.assertEqual(datetime.fromisoformat(row['retrieved_at']),
                         datetime.fromisoformat(fetched('000776.SZ')['retrieved_at']))
        self.assertTrue(all(row[key] == 'false' for key in row if key.endswith('_verified')))

    def test_sina_share_volume_is_not_multiplied_again(self):
        def prices(symbol, *args, **kwargs):
            snapshot = fetched(symbol)
            snapshot.update(upstream='sina', interface='stock_zh_a_hist_sina', volume_unit='shares')
            return snapshot
        encoded, manifest = build_collected_batch_package(request(upstream='sina'), allow_network=True, fetcher=prices, now=NOW)
        rows = self.inspect(encoded, manifest)
        self.assertEqual(float(rows[0]['volume']), fetched('000776.SZ')['records'][0]['volume'])
        self.assertEqual(rows[0]['upstream'], 'sina')
        self.assertEqual(rows[0]['interface'], 'stock_zh_a_hist_sina')

    def test_blocked_and_failed_research_items_are_not_exported(self):
        def prices(symbol, *args, **kwargs):
            if symbol == '600519.SS':
                raise RuntimeError('PRIVATE_DO_NOT_EXPORT')
            snapshot = fetched(symbol)
            if symbol == '000001.SZ':
                snapshot['records'].pop(1)
            return snapshot
        encoded, manifest = build_collected_batch_package(request('600519.SS', '000001.SZ', '000776.SZ'),
            allow_network=True, fetcher=prices, now=NOW)
        self.assertEqual((manifest['generated_count'], manifest['calendar_blocked_count'], manifest['failed_count']), (1, 1, 1))
        rows = self.inspect(encoded, manifest)
        self.assertEqual(len(rows), 5)
        self.assertEqual({row['symbol'] for row in rows}, {'000776.SZ'})
        self.assertNotIn('PRIVATE_DO_NOT_EXPORT', json.dumps(rows))

    def test_no_generated_items_omit_csv_and_link(self):
        def fail(*args, **kwargs):
            raise RuntimeError('PRIVATE')
        encoded, manifest = build_collected_batch_package(request(), allow_network=True, fetcher=fail, now=NOW)
        self.assertIsNone(self.inspect(encoded, manifest))
        def gap(symbol, *args, **kwargs):
            snapshot = fetched(symbol)
            snapshot['records'].pop(1)
            return snapshot
        encoded, manifest = build_collected_batch_package(request(), allow_network=True, fetcher=gap, now=NOW)
        self.assertEqual(manifest['calendar_blocked_count'], 1)
        self.assertIsNone(self.inspect(encoded, manifest))

    def test_quick_preserves_csv_link_and_final_hashes_offline_default_unchanged(self):
        calls = []
        def sessions(*args, **kwargs):
            calls.append('calendar')
            return calendar(*args, **kwargs)
        def prices(symbol, *args, **kwargs):
            calls.append('prices')
            return fetched(symbol)
        encoded, manifest = build_quick_research_package(['000776.SZ'], 'eastmoney', start_date='2026-11-02',
            end_date='2026-11-06', allow_network=True, calendar_fetcher=sessions, price_fetcher=prices, now=NOW)
        rows = self.inspect(encoded, manifest)
        self.assertEqual(len(rows), 5)
        self.assertEqual(calls, ['calendar', 'prices'])
        encoded, manifest = build_batch_research_package(batch(job()))
        self.assertIsNone(self.inspect(encoded, manifest))
