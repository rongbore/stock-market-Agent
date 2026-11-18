from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.offline_batch_research_runner import _canonical_json_bytes
from scripts.sma_evaluation_cli import build_evaluation_artifact

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/backtest/SYNTHETIC_sma_oos_config.json'


def fixture():
    config = json.loads(EXAMPLE.read_text())
    snapshot = config['snapshot']
    calendar = {'schema_version':'0.1','exchange':snapshot['symbol'][-2:],
                'start_date':snapshot['start_date'],'end_date':snapshot['end_date'],
                'source':'SYNTHETIC fixture dates; not independent completeness evidence',
                'sessions':[r['date'] for r in snapshot['records']]}
    return config, calendar


def cli(source, calendar, output):
    return subprocess.run([sys.executable,'-m','scripts.sma_evaluation_cli',
        '--input',str(source),'--calendar',str(calendar),'--output',str(output)],
        cwd=ROOT,capture_output=True,text=True,timeout=20)


class EvaluationCalendarGateTests(unittest.TestCase):
    def test_matching_calendar_leaves_financial_results_unchanged_and_binds_inputs(self):
        config, calendar = fixture()
        original_config, original_calendar = deepcopy(config), deepcopy(calendar)
        default = build_evaluation_artifact(config)
        gated = build_evaluation_artifact(config, calendar=calendar)
        self.assertEqual(gated['evaluation'], default['evaluation'])
        self.assertEqual(gated['config_input_sha256'],default['config_input_sha256'])
        self.assertEqual(gated['calendar_coverage']['calendar_sha256'],
                         hashlib.sha256(_canonical_json_bytes(calendar)).hexdigest())
        self.assertEqual(gated['calendar_gate_input_sha256'],
                         hashlib.sha256(_canonical_json_bytes({'config':config,'calendar':calendar})).hexdigest())
        self.assertEqual(gated,build_evaluation_artifact(config,calendar=calendar))
        self.assertEqual((config,calendar),(original_config,original_calendar))
        self.assertFalse(gated['calendar_coverage']['exchange_calendar_verified'])
        self.assertFalse(gated['verified_performance'])
        payload={k:v for k,v in gated.items() if k!='artifact_payload_sha256'}
        self.assertEqual(gated['artifact_payload_sha256'],hashlib.sha256(_canonical_json_bytes(payload)).hexdigest())
        self.assertNotIn('calendar_coverage',default)
        self.assertNotIn('calendar_gate_input_sha256',default)

    def test_gap_or_unexpected_session_blocks_evaluator_before_any_paper_run(self):
        for field in ('records','sessions'):
            config, calendar = fixture()
            (config['snapshot'] if field=='records' else calendar)[field].pop(1)
            with self.subTest(field=field), patch('scripts.sma_evaluation_cli.evaluate_sma_out_of_sample') as evaluator:
                with self.assertRaisesRegex(ValueError,'calendar coverage mismatch'):
                    build_evaluation_artifact(config,calendar=calendar)
                evaluator.assert_not_called()

    def test_wrong_calendar_scope_and_duplicates_do_not_reach_evaluation(self):
        for field, value in [('exchange','SS'),('start_date','2026-01-01'),
                             ('sessions',['20261101']),('sessions',['2026-11-02']*2)]:
            config,calendar=fixture();calendar[field]=value
            with self.subTest(field=field),patch('scripts.sma_evaluation_cli.evaluate_sma_out_of_sample') as evaluator:
                with self.assertRaises(ValueError):
                    build_evaluation_artifact(config,calendar=calendar)
                evaluator.assert_not_called()

    def test_date_match_never_bypasses_raw_bar_contract(self):
        for field,value in [('volume_unit','unknown'),('source_content_verified',True),
                            ('retrieved_at','2099-01-01T00:00:00Z')]:
            config,calendar=fixture();config['snapshot'][field]=value
            with self.subTest(field=field),patch('scripts.sma_evaluation_cli.evaluate_sma_out_of_sample') as evaluator:
                with self.assertRaises(ValueError):
                    build_evaluation_artifact(config,calendar=calendar)
                evaluator.assert_not_called()
        config,calendar=fixture();config['snapshot']['records'][0]['close']=-1
        with self.assertRaises(ValueError):
            build_evaluation_artifact(config,calendar=calendar)

    def test_actual_cli_success_repeatability_and_mismatch_preserves_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source,calendar_path,output=[Path(folder)/name for name in ('config.json','calendar.json','result.json')]
            config,calendar=fixture();source.write_text(json.dumps(config));calendar_path.write_text(json.dumps(calendar))
            completed=cli(source,calendar_path,output)
            self.assertEqual(completed.returncode,0,completed.stderr)
            original=output.read_bytes()
            self.assertEqual(cli(source,calendar_path,output).returncode,0)
            self.assertEqual(output.read_bytes(),original)
            calendar['sessions'].pop(1);calendar_path.write_text(json.dumps(calendar))
            self.assertNotEqual(cli(source,calendar_path,output).returncode,0)
            self.assertEqual(output.read_bytes(),original)
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()),['calendar.json','config.json','result.json'])

    def test_calendar_output_alias_duplicate_keys_and_symlinks_preserve_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            source,calendar_path,output=[Path(folder)/name for name in ('config.json','calendar.json','result.json')]
            config,calendar=fixture();source.write_text(json.dumps(config));calendar_path.write_text(json.dumps(calendar))
            original=calendar_path.read_bytes()
            self.assertNotEqual(cli(source,calendar_path,calendar_path).returncode,0)
            self.assertEqual(calendar_path.read_bytes(),original)
            os.link(calendar_path,output)
            self.assertNotEqual(cli(source,calendar_path,output).returncode,0)
            self.assertEqual(calendar_path.read_bytes(),original)
            output.unlink();output.symlink_to(calendar_path)
            self.assertNotEqual(cli(source,calendar_path,output).returncode,0)
            self.assertEqual(calendar_path.read_bytes(),original)
            output.unlink()
            for raw in ('{"sessions":[],"sessions":[]}', 'null', 'false', '[]'):
                calendar_path.write_text(raw)
                with self.subTest(calendar=raw):
                    self.assertNotEqual(cli(source,calendar_path,output).returncode,0)
                    self.assertFalse(output.exists())
