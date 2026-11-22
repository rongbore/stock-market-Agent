import copy
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.collect_batch_research import build_collected_batch_package, main
from tests.test_batch_calendar_research import job

NOW=datetime(2026,11,19,tzinfo=timezone.utc)


def request(*symbols,upstream='eastmoney'):
    first=job(symbols[0] if symbols else '000776.SZ')
    return {'schema_version':'0.1','upstream':upstream,'start_date':first['config']['snapshot']['start_date'],
            'end_date':first['config']['snapshot']['end_date'],
            'items':[{'symbol':s,'calendar':job(s)['config']['calendar']} for s in (symbols or ('000776.SZ',))]}


def fetched(symbol,*args,**kwargs):
    return job(symbol)['config']['snapshot']


class BatchCollectionTests(unittest.TestCase):
    def test_explicit_provider_collection_package_is_hash_bound_and_unverified(self):
        config=request('000776.SZ','600519.SS')
        calls=[]
        def provider(symbol,start,end,*,adjust):
            calls.append((symbol,start,end,adjust));return fetched(symbol)
        encoded,manifest=build_collected_batch_package(config,allow_network=True,fetcher=provider,now=NOW)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(c[1:]==(config['start_date'],config['end_date'],'') for c in calls))
        self.assertEqual(manifest['status'],'ALL_RESEARCH_GENERATED_UNVERIFIED')
        self.assertEqual((encoded,manifest),build_collected_batch_package(config,allow_network=True,fetcher=fetched,now=NOW))
        with ZipFile(BytesIO(encoded)) as archive:
            self.assertIsNone(archive.testzip())
            collection=json.loads(archive.read('collection.json'))
            self.assertEqual(collection['upstream'],'eastmoney')
            self.assertTrue(all(i['status']=='COLLECTED_UNVERIFIED' for i in collection['items']))
            self.assertFalse(collection['source_content_verified'])
            for symbol in ('000776.SZ','600519.SS'):
                self.assertIn('collected/'+symbol+'.snapshot.json',archive.namelist())
                self.assertIn('items/'+symbol+'/dashboard.html',archive.namelist())
            for entry in manifest['files']:
                data=archive.read(entry['path'])
                self.assertEqual(len(data),entry['size_bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(),entry['sha256'])

    def test_fetch_exception_and_calendar_gap_isolated_without_failed_dashboard(self):
        class ProviderLimit(Exception):pass
        def provider(symbol,*args,**kwargs):
            if symbol=='600519.SS':raise ProviderLimit('PRIVATE_DO_NOT_LOG')
            snapshot=fetched(symbol)
            if symbol=='000001.SZ':snapshot['records'].pop(1)
            return snapshot
        encoded,manifest=build_collected_batch_package(request('000776.SZ','000001.SZ','600519.SS'),
                                                       allow_network=True,fetcher=provider,now=NOW)
        self.assertEqual((manifest['generated_count'],manifest['calendar_blocked_count'],manifest['failed_count']),(1,1,1))
        with ZipFile(BytesIO(encoded)) as archive:
            self.assertNotIn(b'PRIVATE_DO_NOT_LOG',encoded)
            collection=json.loads(archive.read('collection.json'))
            entries={r['symbol']:r for r in collection['items']}
            self.assertEqual(entries['600519.SS']['status'],'FAILED_COLLECTION')
            self.assertEqual(entries['000001.SZ']['status'],'COLLECTED_UNVERIFIED')
            self.assertIn('collected/000001.SZ.snapshot.json',archive.namelist())
            for symbol in ('000001.SZ','600519.SS'):
                self.assertNotIn('items/'+symbol+'/dashboard.html',archive.namelist())

    def test_invalid_second_calendar_or_request_never_calls_any_provider(self):
        config=request('000776.SZ','600519.SS')
        bad=[]
        one=copy.deepcopy(config);one['items'][1]['calendar']['exchange']='SZ';bad.append(one)
        one=copy.deepcopy(config);one['items']*=3;bad.append(one)
        one=copy.deepcopy(config);one['items'][1]['symbol']='000776.SZ';bad.append(one)
        one=copy.deepcopy(config);one['start_date']='';one['end_date']='';bad.append(one)
        for field,value in [('upstream','automatic'),('end_date','2026-11-19'),
                            ('end_date','2026-11-20'),('start_date','2020-01-01')]:
            one=copy.deepcopy(config);one[field]=value;bad.append(one)
        for config in bad:
            calls=[]
            def provider(*a,**kw):calls.append(a);return fetched('000776.SZ')
            with self.subTest(config=str(config)[:100]),self.assertRaises(ValueError):
                build_collected_batch_package(config,allow_network=True,fetcher=provider,now=NOW)
            self.assertEqual(calls,[])

    def test_snapshot_identity_window_and_adjustment_mismatch_cannot_generate(self):
        for field,value in [('symbol','600519.SS'),('upstream','sina'),('start_date','2026-11-01'),
                            ('end_date','2026-11-07'),('adjust','qfq'),('source_content_verified',True)]:
            snapshot=fetched('000776.SZ');snapshot[field]=value
            encoded,manifest=build_collected_batch_package(request(),allow_network=True,
                                                          fetcher=lambda *a,**kw:snapshot,now=NOW)
            self.assertEqual(manifest['status'],'NO_RESEARCH_GENERATED')
            with ZipFile(BytesIO(encoded)) as archive:
                item=json.loads(archive.read('collection.json'))['items'][0]
                self.assertEqual(item['status'],'FAILED_SNAPSHOT_VALIDATION')
                self.assertFalse(any(n.startswith('collected/') or n.endswith('dashboard.html') for n in archive.namelist()))

    def test_sina_selection_never_calls_eastmoney_and_keeps_single_source(self):
        def sina(*a,**kw):
            snapshot=fetched(*a,**kw);snapshot.update(upstream='sina',interface='stock_zh_a_hist_sina',volume_unit='shares')
            return snapshot
        with patch('scripts.collect_batch_research.fetch_sina_daily',side_effect=sina) as selected:
            with patch('scripts.collect_batch_research.fetch_a_share_daily') as other:
                encoded,manifest=build_collected_batch_package(request(upstream='sina'),allow_network=True,now=NOW)
                selected.assert_called_once();other.assert_not_called()
        self.assertEqual(manifest['generated_count'],1)
        with ZipFile(BytesIO(encoded)) as archive:
            result=json.loads(archive.read('batch-result.json'))['results'][0]['result']
            report=result['batch_config']['reports']['000776.SZ']
            self.assertFalse(report['numerical_agreement'])
            self.assertEqual(report['price_basis'],'single_source_close')

    def test_network_opt_in_and_baseexception_are_not_swallowed(self):
        with patch('scripts.collect_batch_research.fetch_a_share_daily') as provider:
            with self.assertRaises(ValueError):build_collected_batch_package(request(),now=NOW)
            provider.assert_not_called()
        with self.assertRaises(KeyboardInterrupt):
            build_collected_batch_package(request(),allow_network=True,
                                         fetcher=lambda *a,**kw:(_ for _ in ()).throw(KeyboardInterrupt()),now=NOW)

    def test_cli_requires_opt_in_preflights_output_and_preserves_existing_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            source,output=Path(folder)/'request.json',Path(folder)/'result.zip';source.write_text(json.dumps(request()))
            args=['--input',str(source),'--output',str(output)]
            with self.assertRaises(SystemExit):main(args)
            with patch('scripts.collect_batch_research.fetch_a_share_daily') as provider:
                with patch('scripts.collect_batch_research.tempfile.NamedTemporaryFile',side_effect=PermissionError('no output access')):
                    with self.assertRaises(PermissionError):main(args+['--allow-network'])
                provider.assert_not_called()
            with patch('scripts.collect_batch_research.fetch_a_share_daily',side_effect=fetched):
                self.assertEqual(main(args+['--allow-network']),0)
            before=output.read_bytes()
            with self.assertRaises(FileExistsError):main(args+['--allow-network'])
            self.assertEqual(output.read_bytes(),before)
            with self.assertRaises(FileExistsError):main(['--input',str(source),'--output',str(source),'--allow-network'])

    def test_cli_failed_collection_publishes_diagnostic_exit_two_and_race_is_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            source,output=Path(folder)/'request.json',Path(folder)/'result.zip';source.write_text(json.dumps(request()))
            args=['--input',str(source),'--output',str(output),'--allow-network']
            with patch('scripts.collect_batch_research.fetch_a_share_daily',side_effect=RuntimeError('private')):
                self.assertEqual(main(args),2)
            output.unlink()
            def race(temp,destination):
                Path(destination).write_bytes(b'winner');raise FileExistsError('concurrent output')
            with patch('scripts.collect_batch_research.fetch_a_share_daily',side_effect=fetched):
                with patch('scripts.collect_batch_research.os.link',side_effect=race):
                    with self.assertRaises(FileExistsError):main(args)
            self.assertEqual(output.read_bytes(),b'winner')
            self.assertEqual(set(Path(folder).iterdir()),{source,output})
