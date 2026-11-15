import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.calendar_acceptance_cli import build_calendar_acceptance, main
from scripts.offline_batch_research_runner import _canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    original = json.loads((ROOT / 'examples/backtest/SYNTHETIC_sma_oos_config.json').read_text())
    s = original['snapshot']
    return {'schema_version': '0.1', 'data_kind': 'SYNTHETIC', 'snapshot': s,
            'calendar': {'schema_version': '0.1', 'exchange': s['symbol'][-2:],
                         'start_date': s['start_date'], 'end_date': s['end_date'],
                         'source': 'SYNTHETIC offline test calendar',
                         'sessions': [r['date'] for r in s['records']]},
            'evidence_as_of': original['settings']['evidence_as_of'],
            'expected_adjustment': original['settings']['expected_adjustment']}


class AcceptanceTests(unittest.TestCase):
    def test_deterministic_hash_bound_record_without_prices_or_verified_claims(self):
        config = fixture()
        artifact = build_calendar_acceptance(config)
        self.assertEqual(artifact, build_calendar_acceptance(copy.deepcopy(config)))
        self.assertEqual(artifact['status'], 'MATCH')
        payload = dict(artifact)
        digest = payload.pop('artifact_payload_sha256')
        self.assertEqual(digest, hashlib.sha256(_canonical_json_bytes(payload)).hexdigest())
        self.assertFalse(artifact['source_content_verified'])
        self.assertFalse(artifact['historical_point_in_time_verified'])
        self.assertFalse(artifact['exchange_calendar_verified'])
        self.assertNotIn('snapshot', artifact)
        changed = copy.deepcopy(config)
        changed['snapshot']['records'][0]['volume'] += 1
        other = build_calendar_acceptance(changed)
        self.assertNotEqual(artifact['snapshot_sha256'], other['snapshot_sha256'])
        self.assertNotEqual(artifact['config_input_sha256'], other['config_input_sha256'])
        self.assertEqual(artifact['calendar_coverage']['calendar_sha256'], other['calendar_coverage']['calendar_sha256'])

    def test_date_match_cannot_bypass_bad_prices_units_flags_or_cutoff(self):
        for field, value in [('volume_unit', 'unknown'), ('source_content_verified', True),
                             ('retrieved_at', '2099-01-01T00:00:00Z')]:
            config = fixture()
            config['snapshot'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_calendar_acceptance(config)
        config = fixture()
        config['snapshot']['records'][0]['close'] = -1
        with self.assertRaises(ValueError):
            build_calendar_acceptance(config)

    def test_exact_config_and_calendar_window_required(self):
        for mutate in (lambda c: c.update(verified=True),
                       lambda c: c.update(data_kind='VERIFIED'),
                       lambda c: c['calendar'].update(exchange='XX'),
                       lambda c: c.update(evidence_as_of='2026-01-01')):
            config = fixture()
            mutate(config)
            with self.assertRaises(ValueError):
                build_calendar_acceptance(config)

    def test_cli_match_and_gap_write_records_with_distinct_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'input.json', Path(folder)/'output.json'
            config = fixture()
            source.write_text(json.dumps(config))
            args = ['--input', str(source), '--output', str(output)]
            self.assertEqual(main(args), 0)
            original = output.read_bytes()
            with self.assertRaises(FileExistsError):
                main(args)
            self.assertEqual(output.read_bytes(), original)
            output.unlink()
            missing = config['snapshot']['records'].pop(1)['date']
            source.write_text(json.dumps(config))
            self.assertEqual(main(args), 2)
            result = json.loads(output.read_text())
            self.assertEqual(result['status'], 'REVIEW_REQUIRED')
            self.assertEqual(result['calendar_coverage']['missing_dates'], [missing])

    def test_malformed_duplicate_and_oversized_input_leave_no_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'input.json', Path(folder)/'output.json'
            for raw in ['{', '{"a":1,"a":2}', '{"a":NaN}', 'x' * 100]:
                source.write_text(raw)
                with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                    main(['--input', str(source), '--output', str(output)])
                self.assertFalse(output.exists())
            source.write_text('x' * 101)
            with patch('scripts.calendar_acceptance_cli.MAX_INPUT_BYTES', 100):
                with self.assertRaises(ValueError):
                    main(['--input', str(source), '--output', str(output)])

    def test_concurrent_output_preserved_and_temporary_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'input.json', Path(folder)/'output.json'
            source.write_text(json.dumps(fixture()))
            def race(temporary, destination):
                Path(destination).write_bytes(b'winner')
                raise FileExistsError('concurrent writer')
            with patch('scripts.calendar_acceptance_cli.os.link', side_effect=race):
                with self.assertRaises(FileExistsError):
                    main(['--input', str(source), '--output', str(output)])
            self.assertEqual(output.read_bytes(), b'winner')
            self.assertEqual(set(Path(folder).iterdir()), {source, output})

    @unittest.skipUnless(hasattr(os, 'symlink'), 'symlinks unavailable')
    def test_input_output_alias_and_output_symlink_preserve_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'input.json', Path(folder)/'output.json'
            original = json.dumps(fixture())
            source.write_text(original)
            with self.assertRaises(FileExistsError):
                main(['--input', str(source), '--output', str(source)])
            output.symlink_to(source)
            with self.assertRaises(FileExistsError):
                main(['--input', str(source), '--output', str(output)])
            self.assertEqual(source.read_text(), original)
