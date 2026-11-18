"""Run the committed SYNTHETIC quickstart examples through actual CLIs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples/offline_quickstart'
SMA = ROOT / 'examples/backtest/SYNTHETIC_sma_oos_config.json'
ACCEPTANCE = EXAMPLES / 'SYNTHETIC_acceptance_config.json'
CALENDAR = EXAMPLES / 'SYNTHETIC_calendar.json'
BATCH = EXAMPLES / 'SYNTHETIC_batch_calendar_research.json'


def run_cli(module, *args):
    return subprocess.run([sys.executable, '-m', module, *map(str, args)], cwd=ROOT,
                          capture_output=True, text=True, timeout=20)


class OfflineQuickstartExamplesTests(unittest.TestCase):
    def test_committed_examples_remain_bound_to_existing_synthetic_sma_fixture(self):
        sma = json.loads(SMA.read_text())
        acceptance = json.loads(ACCEPTANCE.read_text())
        calendar = json.loads(CALENDAR.read_text())
        self.assertEqual(acceptance['snapshot'], sma['snapshot'])
        self.assertEqual(acceptance['data_kind'], 'SYNTHETIC')
        self.assertIn('SYNTHETIC', acceptance['snapshot']['akshare_version'])
        self.assertEqual(acceptance['evidence_as_of'], sma['settings']['evidence_as_of'])
        self.assertEqual(acceptance['expected_adjustment'], sma['settings']['expected_adjustment'])
        self.assertEqual(acceptance['calendar'], calendar)
        self.assertIn('SYNTHETIC', calendar['source'])
        self.assertEqual(calendar['sessions'], [r['date'] for r in sma['snapshot']['records']])
        batch = json.loads(BATCH.read_text())
        self.assertEqual(len(batch['items']), 3)
        self.assertTrue(all(item['config']['data_kind'] == 'SYNTHETIC' for item in batch['items']))

    def test_actual_single_stock_acceptance_evaluation_and_zip_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            acceptance, evaluation, archive = folder/'acceptance.json', folder/'sma.json', folder/'single.zip'
            result = run_cli('scripts.calendar_acceptance_cli', '--input', ACCEPTANCE, '--output', acceptance)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(acceptance.read_text())['status'], 'MATCH')
            result = run_cli('scripts.sma_evaluation_cli', '--input', SMA, '--calendar', CALENDAR, '--output', evaluation)
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluated = json.loads(evaluation.read_text())
            self.assertEqual(evaluated['calendar_coverage']['status'], 'MATCH')
            self.assertFalse(evaluated['verified_performance'])
            result = run_cli('scripts.offline_research_package', '--input', ACCEPTANCE, '--output', archive)
            self.assertEqual(result.returncode, 0, result.stderr)
            with ZipFile(archive) as package:
                self.assertIsNone(package.testzip())
                manifest = json.loads(package.read('manifest.json'))
                self.assertEqual(manifest['status'], 'RESEARCH_GENERATED_UNVERIFIED')
                self.assertIn('合成测试数据', package.read('dashboard.html').decode())
                for item in manifest['files']:
                    self.assertEqual(hashlib.sha256(package.read(item['path'])).hexdigest(), item['sha256'])

    def test_actual_mixed_batch_exit_two_retains_complete_isolated_results(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'batch.json'
            result = run_cli('scripts.batch_calendar_research', '--input', BATCH, '--output', output)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            batch = json.loads(output.read_text())
            self.assertEqual(batch['status'], 'PARTIAL_RESEARCH_UNVERIFIED')
            self.assertEqual((batch['generated_count'], batch['calendar_blocked_count'], batch['failed_count']), (1,1,1))
            results = {item['symbol']: item for item in batch['results']}
            self.assertEqual(results['000776.SZ']['status'], 'RESEARCH_GENERATED_UNVERIFIED')
            self.assertEqual(results['000001.SZ']['status'], 'REVIEW_REQUIRED')
            self.assertEqual(results['600519.SS']['status'], 'FAILED_INPUT_OR_GENERATION')
            blocked = results['000001.SZ']['result']
            self.assertEqual(blocked['acceptance']['calendar_coverage']['missing_dates'], ['2026-11-03'])
            self.assertNotIn('dashboard_html', blocked)
            self.assertNotIn('result', results['600519.SS'])
            self.assertFalse(batch['source_content_verified'])
