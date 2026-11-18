import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.batch_research_package import build_batch_research_package, main
from scripts.offline_batch_research_runner import _canonical_json_bytes
from tests.test_batch_calendar_research import job, batch


class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.tags=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)
        self.links.extend(value for key,value in attrs if key in ('href','src'))


class BatchPackageTests(unittest.TestCase):
    def test_success_archive_is_deterministic_all_byte_hashes_and_links_resolve(self):
        config=batch(job(),job('600519.SS'))
        encoded,manifest=build_batch_research_package(config)
        self.assertEqual((encoded,manifest),build_batch_research_package(config))
        with ZipFile(BytesIO(encoded)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(archive.namelist()),8)
            for item in manifest['files']:
                data=archive.read(item['path'])
                self.assertEqual(len(data),item['size_bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])
            result=json.loads(archive.read('batch-result.json'))
            self.assertEqual(archive.read('summary.md').decode(),result['summary_markdown'])
            payload=dict(result);digest=payload.pop('artifact_payload_sha256')
            self.assertEqual(digest,manifest['batch_result_payload_sha256'])
            self.assertEqual(digest,hashlib.sha256(_canonical_json_bytes(payload)).hexdigest())
            index=archive.read('index.html').decode();links=Links();links.feed(index)
            self.assertIn('全部已生成 · 未核验',index)
            self.assertNotIn('ALL_RESEARCH_GENERATED_UNVERIFIED',index)
            self.assertNotIn('script',links.tags)
            for link in links.links:self.assertIn(link,archive.namelist())
            for info in archive.infolist():self.assertEqual(info.date_time,(1980,1,1,0,0,0))
            self.assertFalse(manifest['source_content_verified'])
            self.assertFalse(manifest['exchange_calendar_verified'])

    def test_partial_failure_exports_diagnostics_without_failed_pages(self):
        gap=job('000001.SZ');gap['config']['snapshot']['records'].pop(1)
        invalid=job('600519.SS');invalid['config']['snapshot']['records'][0]['close']=-1
        encoded,manifest=build_batch_research_package(batch(job(),gap,invalid))
        self.assertEqual(manifest['status'],'PARTIAL_RESEARCH_UNVERIFIED')
        with ZipFile(BytesIO(encoded)) as archive:
            names=archive.namelist()
            self.assertIn('items/000776.SZ/dashboard.html',names)
            for symbol in ('000001.SZ','600519.SS'):
                self.assertNotIn('items/'+symbol+'/dashboard.html',names)
                self.assertIn('items/'+symbol+'/diagnostic.json',names)
            blocked=json.loads(archive.read('items/000001.SZ/diagnostic.json'))
            self.assertEqual(blocked['acceptance']['calendar_coverage']['missing_dates'],['2026-11-03'])
            invalid=json.loads(archive.read('items/600519.SS/diagnostic.json'))
            self.assertNotIn('research',invalid)
            self.assertNotIn('acceptance',invalid)
            index=archive.read('index.html').decode()
            self.assertIn('日期待核查',index);self.assertIn('输入或生成失败',index)
            self.assertNotIn('items/000001.SZ/dashboard.html',index)

    def test_untrusted_config_strings_cannot_create_members_or_index_html(self):
        config=batch(job())
        config['items'][0]['config']['calendar']['source']='../../<script>alert(1)</script>'
        encoded,_=build_batch_research_package(config)
        with ZipFile(BytesIO(encoded)) as archive:
            self.assertNotIn('<script>',archive.read('index.html').decode())
            self.assertTrue(all('..' not in name and not name.startswith('/') for name in archive.namelist()))
        config['items'][0]['symbol']='../payload'
        with self.assertRaises(ValueError):build_batch_research_package(config)

    def test_cli_success_failure_exit_and_existing_output_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            source,output=Path(folder)/'input.json',Path(folder)/'output.zip'
            config=batch(job());source.write_text(json.dumps(config))
            args=['--input',str(source),'--output',str(output)]
            self.assertEqual(main(args),0)
            original=output.read_bytes()
            with self.assertRaises(FileExistsError):main(args)
            self.assertEqual(output.read_bytes(),original)
            output.unlink();config['items'][0]['config']=None
            source.write_text(json.dumps(config));self.assertEqual(main(args),2)
            with ZipFile(output) as archive:
                self.assertFalse(any(name.endswith('dashboard.html') for name in archive.namelist()))

    def test_invalid_input_and_output_alias_or_symlink_preserve_files(self):
        with tempfile.TemporaryDirectory() as folder:
            source,output=Path(folder)/'input.json',Path(folder)/'output.zip'
            for raw in ('{','{"items":[],"items":[]}'):
                source.write_text(raw)
                with self.assertRaises(ValueError):main(['--input',str(source),'--output',str(output)])
                self.assertFalse(output.exists())
            source.write_text(json.dumps(batch(job())))
            with self.assertRaises(FileExistsError):main(['--input',str(source),'--output',str(source)])
            output.symlink_to(source)
            with self.assertRaises(FileExistsError):main(['--input',str(source),'--output',str(output)])
            self.assertTrue(output.is_symlink())

    def test_concurrent_output_and_temporary_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            source,output=Path(folder)/'input.json',Path(folder)/'output.zip'
            source.write_text(json.dumps(batch(job())))
            def race(temporary,destination):
                Path(destination).write_bytes(b'winner');raise FileExistsError('concurrent output')
            with patch('scripts.batch_research_package.os.link',side_effect=race):
                with self.assertRaises(FileExistsError):main(['--input',str(source),'--output',str(output)])
            self.assertEqual(output.read_bytes(),b'winner')
            self.assertEqual(set(Path(folder).iterdir()),{source,output})
