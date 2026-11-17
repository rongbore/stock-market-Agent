import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.calendar_acceptance_cli import build_calendar_gated_research, main
from scripts.offline_batch_research_runner import _canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    original = json.loads((ROOT / 'examples/backtest/SYNTHETIC_sma_oos_config.json').read_text())
    s = original['snapshot']
    return {'schema_version': '0.1', 'data_kind': 'SYNTHETIC', 'snapshot': s,
            'calendar': {'schema_version': '0.1', 'exchange': s['symbol'][-2:],
                         'start_date': s['start_date'], 'end_date': s['end_date'],
                         'source': 'SYNTHETIC fixture calendar',
                         'sessions': [r['date'] for r in s['records']]},
            'evidence_as_of': original['settings']['evidence_as_of'],
            'expected_adjustment': original['settings']['expected_adjustment']}


class GatedResearchTests(unittest.TestCase):
    def test_complete_research_uses_same_snapshot_and_preserves_unverified_labels(self):
        config = fixture()
        untouched = copy.deepcopy(config)
        result = build_calendar_gated_research(config)
        self.assertEqual(config, untouched)
        self.assertEqual(result, build_calendar_gated_research(config))
        self.assertEqual(result['status'], 'RESEARCH_GENERATED_UNVERIFIED')
        self.assertEqual(result['research']['bundle']['succeeded_count'], 1)
        symbol = config['snapshot']['symbol']
        provenance = result['batch_config']['reports'][symbol]['snapshot_provenance_unverified']
        self.assertEqual(provenance['snapshot_sha256'], result['acceptance']['snapshot_sha256'])
        self.assertIn('合成测试数据', result['dashboard_html'])
        self.assertIn('单源收盘价', result['research']['summary_markdown'])
        for flag in ('source_content_verified', 'historical_point_in_time_verified', 'exchange_calendar_verified'):
            self.assertFalse(result[flag])
        payload = dict(result)
        digest = payload.pop('artifact_payload_sha256')
        self.assertEqual(digest, hashlib.sha256(_canonical_json_bytes(payload)).hexdigest())

    def test_missing_or_unexpected_dates_never_run_downstream(self):
        for target in ('snapshot', 'calendar'):
            config = fixture()
            if target == 'snapshot':
                config[target]['records'].pop(1)
            else:
                config[target]['sessions'].pop(1)
            with self.subTest(target=target), patch('scripts.offline_batch_pipeline.build_pipeline') as pipeline:
                with patch('scripts.offline_research_dashboard.build_dashboard') as dashboard:
                    result = build_calendar_gated_research(config)
                    self.assertEqual(result['status'], 'REVIEW_REQUIRED')
                    self.assertNotIn('research', result)
                    self.assertNotIn('dashboard_html', result)
                    self.assertNotIn('batch_config', result)
                    pipeline.assert_not_called()
                    dashboard.assert_not_called()

    def test_forged_acceptance_record_is_not_accepted_as_raw_config(self):
        config = fixture()
        config['acceptance'] = {'status': 'MATCH'}
        with self.assertRaises(ValueError):
            build_calendar_gated_research(config)

    def test_tampered_raw_snapshot_is_rechecked_before_research(self):
        config = fixture()
        config['snapshot']['records'][0]['close'] = -1
        with patch('scripts.offline_batch_pipeline.build_pipeline') as pipeline:
            with self.assertRaises(ValueError):
                build_calendar_gated_research(config)
            pipeline.assert_not_called()

    def test_cli_success_and_mismatch_and_downstream_failure_are_atomic(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'input.json', Path(folder)/'output.json'
            config = fixture()
            source.write_text(json.dumps(config))
            args = ['--input', str(source), '--output', str(output), '--include-research']
            self.assertEqual(main(args), 0)
            self.assertIn('dashboard_html', json.loads(output.read_text()))
            original = output.read_bytes()
            with self.assertRaises(FileExistsError):
                main(args)
            self.assertEqual(output.read_bytes(), original)
            output.unlink()
            with patch('scripts.offline_research_dashboard.build_dashboard', side_effect=ValueError('invalid dashboard')):
                with self.assertRaises(ValueError):
                    main(args)
            self.assertFalse(output.exists())
            config['snapshot']['records'].pop(1)
            source.write_text(json.dumps(config))
            self.assertEqual(main(args), 2)
            self.assertNotIn('dashboard_html', json.loads(output.read_text()))

    def test_failed_research_bundle_cannot_be_labeled_generated(self):
        with patch('scripts.offline_batch_pipeline.build_pipeline', return_value={'bundle': {'succeeded_count': 0}}):
            with self.assertRaises(ValueError):
                build_calendar_gated_research(fixture())
