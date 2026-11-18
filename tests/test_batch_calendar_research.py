import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.batch_calendar_research import build_batch_calendar_research, main
from scripts.offline_batch_research_runner import _canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]


def job(symbol='000776.SZ'):
    original=json.loads((ROOT/'examples/backtest/SYNTHETIC_sma_oos_config.json').read_text())
    snapshot=original['snapshot'];snapshot['symbol']=symbol
    raw={'schema_version':'0.1','data_kind':'SYNTHETIC','snapshot':snapshot,
         'calendar':{'schema_version':'0.1','exchange':symbol[-2:],
                     'start_date':snapshot['start_date'],'end_date':snapshot['end_date'],
                     'source':'SYNTHETIC fixture calendar; not official',
                     'sessions':[r['date'] for r in snapshot['records']]},
         'evidence_as_of':original['settings']['evidence_as_of'],
         'expected_adjustment':original['settings']['expected_adjustment']}
    return {'symbol':symbol,'config':raw}


def batch(*items):
    return {'schema_version':'0.1','items':list(items)}


class BatchCalendarTests(unittest.TestCase):
    def test_two_successful_jobs_are_sorted_hash_bound_and_deterministic(self):
        config=batch(job('600519.SS'),job())
        original=copy.deepcopy(config)
        result=build_batch_calendar_research(config)
        self.assertEqual(result,build_batch_calendar_research(config))
        self.assertEqual(config,original)
        self.assertEqual(result['status'],'ALL_RESEARCH_GENERATED_UNVERIFIED')
        self.assertEqual(result['generated_count'],2)
        self.assertEqual([r['symbol'] for r in result['results']],['000776.SZ','600519.SS'])
        for entry in result['results']:
            acceptance=entry['result']['acceptance']
            self.assertEqual(entry['snapshot_sha256'],acceptance['snapshot_sha256'])
            self.assertEqual(entry['calendar_sha256'],acceptance['calendar_coverage']['calendar_sha256'])
            self.assertFalse(entry['source_content_verified'])
            self.assertFalse(entry['result']['exchange_calendar_verified'])
        payload=dict(result);digest=payload.pop('artifact_payload_sha256')
        self.assertEqual(digest,hashlib.sha256(_canonical_json_bytes(payload)).hexdigest())
        self.assertIn('总任务：2；已生成：2',result['summary_markdown'])

    def test_partial_success_retains_calendar_gap_and_invalid_item_without_research(self):
        gap=job('000001.SZ');gap['config']['snapshot']['records'].pop(1)
        invalid=job('600519.SS');invalid['config']['snapshot']['records'][0]['close']=-1
        result=build_batch_calendar_research(batch(job(),gap,invalid))
        self.assertEqual(result['status'],'PARTIAL_RESEARCH_UNVERIFIED')
        self.assertEqual((result['generated_count'],result['calendar_blocked_count'],result['failed_count']),(1,1,1))
        results={r['symbol']:r for r in result['results']}
        self.assertEqual(results['000001.SZ']['status'],'REVIEW_REQUIRED')
        self.assertNotIn('research',results['000001.SZ']['result'])
        self.assertEqual(results['000001.SZ']['result']['acceptance']['calendar_coverage']['missing_dates'],['2026-11-03'])
        self.assertNotIn('result',results['600519.SS'])
        self.assertEqual(len(results['600519.SS']['snapshot_sha256']),64)

    def test_all_failed_cannot_be_labeled_success_and_exception_details_are_sanitized(self):
        with patch('scripts.batch_calendar_research.build_calendar_gated_research',side_effect=RuntimeError('PRIVATE_MARKER')):
            result=build_batch_calendar_research(batch(job()))
        self.assertEqual(result['status'],'NO_RESEARCH_GENERATED')
        self.assertEqual(result['failed_count'],1)
        self.assertNotIn('PRIVATE_MARKER',json.dumps(result))
        self.assertNotIn('result',result['results'][0])

    def test_duplicate_jobs_and_invalid_envelope_fail_before_execution(self):
        for config in (batch(job(),job()),batch(),{'schema_version':'0.1','items':[job()]*21},
                       {'schema_version':'0.1','items':[{'symbol':'../x','config':{}}]},
                       {'schema_version':'0.1','items':[{'symbol':'000776.SZ','config':{},'extra':1}]}):
            with self.subTest(config=str(config)[:50]),patch('scripts.batch_calendar_research.build_calendar_gated_research') as runner:
                with self.assertRaises(ValueError):
                    build_batch_calendar_research(config)
                runner.assert_not_called()

    def test_symbol_mismatch_and_null_are_item_failures_not_batch_failures(self):
        mismatch=job('600519.SS');mismatch['config']['snapshot']['symbol']='000776.SZ'
        null={'symbol':'000001.SZ','config':None}
        result=build_batch_calendar_research(batch(job(),mismatch,null))
        self.assertEqual(result['generated_count'],1)
        self.assertEqual(result['failed_count'],2)
        self.assertIsNone(result['results'][0]['snapshot_sha256'])

    def test_each_job_keeps_its_own_cutoff_and_data_declaration(self):
        local=job('600519.SS');local['config']['data_kind']='UNVERIFIED_LOCAL'
        early=job('000001.SZ');early['config']['evidence_as_of']='2020-01-01T00:00:00Z'
        result=build_batch_calendar_research(batch(job(),local,early))
        entries={r['symbol']:r for r in result['results']}
        self.assertEqual(entries['600519.SS']['result']['batch_config']['data_kind'],'UNVERIFIED_LOCAL')
        self.assertEqual(entries['000776.SZ']['result']['batch_config']['data_kind'],'SYNTHETIC')
        self.assertEqual(entries['000001.SZ']['status'],'FAILED_INPUT_OR_GENERATION')
        self.assertEqual(result['generated_count'],2)

    def test_cli_exit_codes_and_existing_source_output_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source,output=Path(folder)/'input.json',Path(folder)/'output.json'
            config=batch(job());source.write_text(json.dumps(config))
            args=['--input',str(source),'--output',str(output)]
            self.assertEqual(main(args),0)
            original=output.read_bytes()
            with self.assertRaises(FileExistsError):main(args)
            self.assertEqual(output.read_bytes(),original)
            with self.assertRaises(FileExistsError):main(['--input',str(source),'--output',str(source)])
            output.unlink();config['items'][0]['config']['snapshot']['records'].pop(1)
            source.write_text(json.dumps(config));self.assertEqual(main(args),2)

    def test_cli_malformed_duplicate_keys_and_symlink_output_leave_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source,output=Path(folder)/'input.json',Path(folder)/'output.json'
            for raw in ('{','{"items":[],"items":[]}','{"schema_version":"0.1","items":[NaN]}'):
                source.write_text(raw)
                with self.assertRaises(ValueError):main(['--input',str(source),'--output',str(output)])
                self.assertFalse(output.exists())
            source.write_text(json.dumps(batch(job())))
            output.symlink_to(source)
            with self.assertRaises(FileExistsError):main(['--input',str(source),'--output',str(output)])
            self.assertTrue(output.is_symlink())

    def test_concurrent_output_winner_and_temporary_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            source,output=Path(folder)/'input.json',Path(folder)/'output.json'
            source.write_text(json.dumps(batch(job())))
            def race(temporary,destination):
                Path(destination).write_bytes(b'winner');raise FileExistsError('concurrent output')
            with patch('scripts.batch_calendar_research.os.link',side_effect=race):
                with self.assertRaises(FileExistsError):main(['--input',str(source),'--output',str(output)])
            self.assertEqual(output.read_bytes(),b'winner')
            self.assertEqual(set(Path(folder).iterdir()),{source,output})
