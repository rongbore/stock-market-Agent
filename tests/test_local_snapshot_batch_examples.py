"""Keep local-file SYNTHETIC demo inputs bound to the existing fixture."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.batch_calendar_research import build_batch_calendar_research

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples/local_snapshot_batch'


def load(name):
    return json.loads((EXAMPLES / name).read_text())


class LocalSnapshotBatchExamplesTests(unittest.TestCase):
    def test_manifest_files_and_synthetic_metadata_match_existing_sources(self):
        source = json.loads((ROOT / 'examples/backtest/SYNTHETIC_sma_oos_config.json').read_text())
        manifest = load('SYNTHETIC_manifest.json')
        self.assertEqual(set(manifest), {'schema_version', 'data_kind', 'evidence_as_of', 'expected_adjustment', 'items'})
        self.assertEqual(manifest['data_kind'], 'SYNTHETIC')
        self.assertEqual(manifest['evidence_as_of'], source['settings']['evidence_as_of'])
        self.assertEqual(manifest['expected_adjustment'], source['settings']['expected_adjustment'])
        self.assertEqual(len(manifest['items']), 2)
        for item in manifest['items']:
            self.assertEqual(set(item), {'symbol', 'snapshot_path', 'calendar_path'})
            for key in ('snapshot_path', 'calendar_path'):
                self.assertFalse(Path(item[key]).is_absolute())
                self.assertEqual((EXAMPLES / item[key]).resolve().parent, EXAMPLES.resolve())
                self.assertTrue((EXAMPLES / item[key]).is_file())
        self.assertEqual({i['calendar_path'] for i in manifest['items']}, {'SYNTHETIC_calendar.json'})
        complete = load('SYNTHETIC_000776_snapshot.json')
        self.assertEqual(complete, source['snapshot'])
        self.assertIn('SYNTHETIC', complete['akshare_version'])
        expected_gap = deepcopy(complete)
        expected_gap['symbol'] = '000001.SZ'
        expected_gap['records'].pop(1)
        self.assertEqual(load('SYNTHETIC_000001_missing_date_snapshot.json'), expected_gap)
        calendar = load('SYNTHETIC_calendar.json')
        self.assertIn('SYNTHETIC', calendar['source'])
        self.assertEqual(calendar['sessions'], [row['date'] for row in complete['records']])

    def test_local_inputs_produce_one_success_and_one_date_block_in_existing_engine(self):
        manifest = load('SYNTHETIC_manifest.json')
        items = []
        for item in manifest['items']:
            items.append({'symbol': item['symbol'], 'config': {
                'schema_version': manifest['schema_version'], 'data_kind': manifest['data_kind'],
                'evidence_as_of': manifest['evidence_as_of'], 'expected_adjustment': manifest['expected_adjustment'],
                'snapshot': load(item['snapshot_path']), 'calendar': load(item['calendar_path'])}})
        result = build_batch_calendar_research({'schema_version': '0.1', 'items': items})
        self.assertEqual(result['status'], 'PARTIAL_RESEARCH_UNVERIFIED')
        self.assertEqual((result['generated_count'], result['calendar_blocked_count'], result['failed_count']), (1, 1, 0))
        by_symbol = {item['symbol']: item for item in result['results']}
        self.assertEqual(by_symbol['000776.SZ']['status'], 'RESEARCH_GENERATED_UNVERIFIED')
        blocked = by_symbol['000001.SZ']['result']
        self.assertEqual(blocked['acceptance']['calendar_coverage']['missing_dates'], ['2026-11-03'])
        self.assertNotIn('dashboard_html', blocked)
        self.assertFalse(result['source_content_verified'])
