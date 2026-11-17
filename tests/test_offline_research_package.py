import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.offline_research_package import build_research_package, main

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    original = json.loads((ROOT / 'examples/backtest/SYNTHETIC_sma_oos_config.json').read_text())
    s = original['snapshot']
    return {'schema_version': '0.1', 'data_kind': 'SYNTHETIC', 'snapshot': s,
            'calendar': {'schema_version': '0.1', 'exchange': s['symbol'][-2:],
                         'start_date': s['start_date'], 'end_date': s['end_date'],
                         'source': 'SYNTHETIC fixture dates only',
                         'sessions': [r['date'] for r in s['records']]},
            'evidence_as_of': original['settings']['evidence_as_of'],
            'expected_adjustment': original['settings']['expected_adjustment']}


class ResearchPackageTests(unittest.TestCase):
    def test_success_archive_members_byte_hashes_and_same_snapshot_binding(self):
        config = fixture()
        encoded, manifest = build_research_package(config)
        self.assertEqual((encoded, manifest), build_research_package(copy.deepcopy(config)))
        with ZipFile(BytesIO(encoded)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), {'README.txt', 'acceptance.json', 'manifest.json',
                'research.json', 'batch-config.json', 'summary.md', 'dashboard.html'})
            self.assertEqual(json.loads(archive.read('manifest.json')), manifest)
            for entry in manifest['files']:
                data = archive.read(entry['path'])
                self.assertEqual(len(data), entry['size_bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
            acceptance = json.loads(archive.read('acceptance.json'))
            batch = json.loads(archive.read('batch-config.json'))
            symbol = config['snapshot']['symbol']
            self.assertEqual(acceptance['snapshot_sha256'],
                             batch['reports'][symbol]['snapshot_provenance_unverified']['snapshot_sha256'])
            research = json.loads(archive.read('research.json'))
            self.assertEqual(archive.read('summary.md').decode(), research['summary_markdown'])
            self.assertIn('合成测试数据', archive.read('dashboard.html').decode())
            for item in archive.infolist():
                self.assertNotIn('/', item.filename)
                self.assertEqual(item.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertFalse(manifest['source_content_verified'])
            self.assertFalse(manifest['exchange_calendar_verified'])

    def test_mismatch_archive_contains_diagnostics_only(self):
        config = fixture()
        config['snapshot']['records'].pop(1)
        encoded, manifest = build_research_package(config)
        self.assertEqual(manifest['status'], 'REVIEW_REQUIRED')
        with ZipFile(BytesIO(encoded)) as archive:
            self.assertEqual(set(archive.namelist()), {'README.txt', 'manifest.json', 'acceptance.json'})
            self.assertEqual(json.loads(archive.read('acceptance.json'))['calendar_coverage']['missing_dates'], ['2026-11-03'])

    def test_caller_source_label_cannot_create_archive_paths(self):
        config = fixture()
        config['calendar']['source'] = '../../untrusted.html'
        encoded, _ = build_research_package(config)
        with ZipFile(BytesIO(encoded)) as archive:
            self.assertTrue(all('/' not in name for name in archive.namelist()))

    def test_cli_exit_codes_and_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'input.json', Path(folder)/'result.zip'
            config = fixture()
            source.write_text(json.dumps(config))
            args = ['--input', str(source), '--output', str(output)]
            self.assertEqual(main(args), 0)
            original = output.read_bytes()
            with self.assertRaises(FileExistsError):
                main(args)
            self.assertEqual(output.read_bytes(), original)
            output.unlink()
            config['snapshot']['records'].pop(1)
            source.write_text(json.dumps(config))
            self.assertEqual(main(args), 2)

    def test_invalid_data_and_downstream_failure_leave_no_package(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'input.json', Path(folder)/'result.zip'
            config = fixture()
            source.write_text(json.dumps(config))
            args = ['--input', str(source), '--output', str(output)]
            with patch('scripts.offline_research_dashboard.build_dashboard', side_effect=ValueError('failed')):
                with self.assertRaises(ValueError):
                    main(args)
            self.assertFalse(output.exists())
            config['snapshot']['records'][0]['close'] = -1
            source.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                main(args)
            self.assertEqual(set(Path(folder).iterdir()), {source})

    def test_concurrent_output_preserved_and_temporary_cleaned(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'input.json', Path(folder)/'result.zip'
            source.write_text(json.dumps(fixture()))
            def race(temporary, destination):
                Path(destination).write_bytes(b'winner')
                raise FileExistsError('concurrent writer')
            with patch('scripts.offline_research_package.os.link', side_effect=race):
                with self.assertRaises(FileExistsError):
                    main(['--input', str(source), '--output', str(output)])
            self.assertEqual(output.read_bytes(), b'winner')
            self.assertEqual(set(Path(folder).iterdir()), {source, output})
