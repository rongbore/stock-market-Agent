import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.local_snapshot_batch import load_local_batch_config, main
from scripts.batch_research_package import build_batch_research_package
from tests.test_batch_calendar_research import job


def local_manifest(folder, jobs):
    folder=Path(folder);items=[]
    for item in jobs:
        symbol=item['symbol'];raw=item['config']
        snapshot,calendar=folder/(symbol+'-snapshot.json'),folder/(symbol+'-calendar.json')
        snapshot.write_text(json.dumps(raw['snapshot']))
        calendar.write_text(json.dumps(raw['calendar']))
        items.append({'symbol':symbol,'snapshot_path':snapshot.name,'calendar_path':calendar.name})
    first=jobs[0]['config']
    manifest={'schema_version':'0.1','data_kind':first['data_kind'],'evidence_as_of':first['evidence_as_of'],
              'expected_adjustment':first['expected_adjustment'],'items':items}
    path=folder/'manifest.json';path.write_text(json.dumps(manifest))
    return path,manifest


class LocalSnapshotBatchTests(unittest.TestCase):
    def test_relative_files_produce_identical_content_bound_package_to_inline_config(self):
        with tempfile.TemporaryDirectory() as folder:
            path,_=local_manifest(folder,[job(),job('600519.SS')])
            config,sources=load_local_batch_config(path)
            expected={'schema_version':'0.1','items':[job(),job('600519.SS')]}
            self.assertEqual(config,expected)
            self.assertEqual(len(sources),5)
            encoded,manifest=build_batch_research_package(config)
            self.assertEqual((encoded,manifest),build_batch_research_package(expected))
            output=Path(folder)/'output.zip'
            self.assertEqual(main(['--input',str(path),'--output',str(output)]),0)
            self.assertEqual(output.read_bytes(),encoded)

    def test_semantic_source_errors_remain_isolated_with_partial_exit_two(self):
        with tempfile.TemporaryDirectory() as folder:
            gap=job('000001.SZ');gap['config']['snapshot']['records'].pop(1)
            invalid=job('600519.SS');invalid['config']['snapshot']['volume_unit']='unknown'
            path,_=local_manifest(folder,[job(),gap,invalid]);output=Path(folder)/'output.zip'
            self.assertEqual(main(['--input',str(path),'--output',str(output)]),2)
            with ZipFile(output) as archive:
                m=json.loads(archive.read('manifest.json'))
                self.assertEqual((m['generated_count'],m['calendar_blocked_count'],m['failed_count']),(1,1,1))
                self.assertIn('items/000776.SZ/dashboard.html',archive.namelist())
                self.assertNotIn('items/000001.SZ/dashboard.html',archive.namelist())
                self.assertNotIn('items/600519.SS/dashboard.html',archive.namelist())

    def test_missing_or_invalid_json_file_stops_before_package_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            path,m=local_manifest(folder,[job()]);output=Path(folder)/'output.zip'
            calendar=Path(folder)/m['items'][0]['calendar_path']
            for raw in ('{','{"x":1,"x":2}'):
                calendar.write_text(raw)
                with patch('scripts.local_snapshot_batch.build_batch_research_package') as build:
                    with self.assertRaises(ValueError):main(['--input',str(path),'--output',str(output)])
                    build.assert_not_called()
                self.assertFalse(output.exists())
            calendar.unlink()
            with self.assertRaises(FileNotFoundError):main(['--input',str(path),'--output',str(output)])
            self.assertFalse(output.exists())

    def test_invalid_envelope_duplicate_symbols_absolute_paths_and_common_settings_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path,m=local_manifest(folder,[job()])
            invalid=[]
            extra=copy.deepcopy(m);extra['unknown']=1;invalid.append(extra)
            duplicate=copy.deepcopy(m);duplicate['items']*=2;invalid.append(duplicate)
            absolute=copy.deepcopy(m);absolute['items'][0]['snapshot_path']=str(Path(folder)/'file.json');invalid.append(absolute)
            empty=copy.deepcopy(m);empty['items']=[];invalid.append(empty)
            many=copy.deepcopy(m);many['items']*=21;invalid.append(many)
            for field,value in [('data_kind','VERIFIED'),('evidence_as_of','2026-11-01'),('expected_adjustment','mystery')]:
                one=copy.deepcopy(m);one[field]=value;invalid.append(one)
            for value in invalid:
                path.write_text(json.dumps(value))
                with self.subTest(manifest=str(value)[:80]),self.assertRaises(ValueError):load_local_batch_config(path)

    def test_manifest_snapshot_and_calendar_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path,m=local_manifest(folder,[job()])
            for output in [path]+[Path(folder)/m['items'][0][k] for k in ('snapshot_path','calendar_path')]:
                before=output.read_bytes()
                with self.assertRaises(FileExistsError):main(['--input',str(path),'--output',str(output)])
                self.assertEqual(output.read_bytes(),before)
            output=Path(folder)/'alias.zip';output.symlink_to(path)
            with self.assertRaises(FileExistsError):main(['--input',str(path),'--output',str(output)])
            self.assertTrue(output.is_symlink())

    def test_bounded_regular_json_loader_rejects_oversized_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path,m=local_manifest(folder,[job()]);calendar=Path(folder)/m['items'][0]['calendar_path']
            calendar.write_text(' '*5000)
            with patch('scripts.calendar_acceptance_cli.MAX_INPUT_BYTES',4000):
                with self.assertRaises(ValueError):load_local_batch_config(path)

    def test_concurrent_output_preserved_and_temp_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            path,_=local_manifest(folder,[job()]);output=Path(folder)/'output.zip'
            before=set(Path(folder).iterdir())
            def race(temporary,destination):
                Path(destination).write_bytes(b'winner');raise FileExistsError('concurrent writer')
            with patch('scripts.local_snapshot_batch.os.link',side_effect=race):
                with self.assertRaises(FileExistsError):main(['--input',str(path),'--output',str(output)])
            self.assertEqual(output.read_bytes(),b'winner')
            self.assertEqual(set(Path(folder).iterdir()),before|{output})
