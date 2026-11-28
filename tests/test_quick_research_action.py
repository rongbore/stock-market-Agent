import contextlib
import csv
import hashlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.batch_research_package import build_batch_research_package
from scripts.quick_research_action import main
from tests.test_batch_calendar_research import batch, job


VALID_ENV = {'RESEARCH_SYMBOLS': '000776.SZ', 'RESEARCH_UPSTREAM': 'eastmoney',
             'RESEARCH_START_DATE': '2026-11-02', 'RESEARCH_END_DATE': '2026-11-06'}


class QuickResearchActionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / 'research-output'
        self.summary = Path(self.temporary.name) / 'summary.md'
        self.action_output = Path(self.temporary.name) / 'action-output.txt'
        self.success, _ = build_batch_research_package(batch(job()))
        self.success_pair, _ = build_batch_research_package(batch(job(), job("600519.SS")))
        invalid = job('600519.SS')
        invalid['config'] = None
        self.partial, _ = build_batch_research_package(batch(job(), invalid))

    def run_action(self, provider, env=None):
        environment = dict(VALID_ENV, GITHUB_STEP_SUMMARY=str(self.summary), GITHUB_OUTPUT=str(self.action_output))
        if env:
            environment.update(env)
        output = StringIO()
        with patch.dict(os.environ, environment, clear=True):
            with patch('scripts.quick_research_action.OUTPUT_DIRECTORY', self.directory):
                with patch('scripts.quick_research_action.quick_main', side_effect=provider) as quick:
                    with contextlib.redirect_stdout(output):
                        code = main()
        return code, output.getvalue(), quick

    def builder(self, data, exit_code=0):
        def build(argv):
            Path(argv[argv.index('--output') + 1]).write_bytes(data)
            return exit_code
        return build

    def test_partial_run_builds_downloadable_report_and_csv_offline(self):
        # Exercise the real Actions entry point and ZIP builder. Only replace
        # the two data providers with deterministic fixtures.
        successful = '000776.SZ'
        blocked = '000001.SZ'
        snapshot = job(successful)['config']['snapshot']
        sessions = [row['date'] for row in snapshot['records']]

        def fetch_prices(symbol, *args, **kwargs):
            data = job(symbol)['config']['snapshot']
            if symbol == blocked:
                del data['records'][1]
            return data

        environment = dict(VALID_ENV, RESEARCH_SYMBOLS=f'{successful},{blocked}',
                           GITHUB_STEP_SUMMARY=str(self.summary), GITHUB_OUTPUT=str(self.action_output))
        with (
            patch.dict(os.environ, environment, clear=True),
            patch('scripts.quick_research_action.OUTPUT_DIRECTORY', self.directory),
            patch('scripts.quick_market_research.fetch_sina_calendar',
                  return_value=(sessions, {'interface': 'SYNTHETIC_calendar',
                                           'full_date_list_sha256': 'a' * 64})) as calendar,
            patch('scripts.collect_batch_research.fetch_a_share_daily', side_effect=fetch_prices) as prices,
            contextlib.redirect_stdout(StringIO()),
        ):
            self.assertEqual(main(), 2)

        calendar.assert_called_once()
        self.assertEqual([call.args[0] for call in prices.call_args_list], [blocked, successful])
        self.assertEqual(self.action_output.read_text(), 'artifacts_ready=true\n')
        verification = json.loads((self.directory / 'verification.json').read_text())
        self.assertTrue(verification['integrity_verified'])
        self.assertFalse(verification['source_content_verified'])
        result = json.loads((self.directory / 'action-result.json').read_text())
        package = (self.directory / 'research.zip').read_bytes()
        sha256 = hashlib.sha256(package).hexdigest()
        self.assertEqual(result['package'], {'filename': 'research.zip',
                                             'size_bytes': len(package), 'sha256': sha256})
        self.assertIn(sha256, self.summary.read_text())
        self.assertEqual(result['generated_count'], 1)
        self.assertEqual(result['calendar_blocked_count'], 1)
        self.assertEqual(result['rerun_request']['symbols'], [blocked])
        self.assertTrue(result['rerun_request']['calendar_review_required'])
        with ZipFile(self.directory / 'research.zip') as archive:
            page = archive.read('index.html').decode('utf-8')
            self.assertIn(f'href="items/{successful}/dashboard.html"', page)
            self.assertIn(f'items/{successful}/dashboard.html', archive.namelist())
            self.assertNotIn(f'items/{blocked}/dashboard.html', archive.namelist())
            self.assertIn('href="market-data.csv"', page)
            rows = list(csv.DictReader(StringIO(archive.read('market-data.csv').decode('utf-8-sig'))))
            self.assertEqual([(row['symbol'], row['date']) for row in rows],
                             [(successful, date) for date in sessions])

        # CI can keep this validated fixture for the artifact round-trip check.
        if destination := os.environ.get('SYNTHETIC_QUICK_RESEARCH_ARTIFACT_DIR'):
            shutil.copytree(self.directory, destination)

    def test_valid_env_explicit_safe_argv_and_success_artifacts(self):
        code, output, quick = self.run_action(self.builder(self.success_pair), {'RESEARCH_SYMBOLS': '000776.SZ，600519.SS'})
        self.assertEqual(code, 0)
        argv = quick.call_args.args[0]
        self.assertEqual(argv[:4], ['--symbols', '000776.SZ', '600519.SS', '--upstream'])
        self.assertIn('--allow-network', argv)
        self.assertEqual(argv[-2:], ['--output', str(self.directory / 'research.zip')])
        self.assertEqual((self.directory / 'research.zip').read_bytes(), self.success_pair)
        verification = json.loads((self.directory / 'verification.json').read_text())
        self.assertTrue(verification['integrity_verified'])
        self.assertFalse(verification['source_content_verified'])
        self.assertIn('总任务：2；已生成：2；日期待核查：0；失败：0', output)
        self.assertIn('独立来源已核验：否', output)
        self.assertEqual(self.summary.read_text(), output)
        self.assertNotIn('rerun_request', json.loads((self.directory / 'action-result.json').read_text()))
        self.assertNotIn('Run workflow', output)
        self.assertEqual(self.action_output.read_text(), 'artifacts_ready=true\n')

    def test_whitespace_symbols_and_omitted_dates_resolve_before_call(self):
        code, _, quick = self.run_action(self.builder(self.success_pair), {
            'RESEARCH_SYMBOLS': '000776.SZ\n600519.SS', 'RESEARCH_START_DATE': '', 'RESEARCH_END_DATE': ''})
        self.assertEqual(code, 0)
        argv = quick.call_args.args[0]
        self.assertEqual(argv[1:3], ['000776.SZ', '600519.SS'])
        self.assertRegex(argv[argv.index('--start-date') + 1], r'^\d{4}-\d{2}-\d{2}$')

    def test_invalid_env_never_calls_network_or_creates_outputs_or_echoes_raw(self):
        values = [
            {'RESEARCH_SYMBOLS': ''}, {'RESEARCH_SYMBOLS': '000776.SZ,000776.SZ'},
            {'RESEARCH_SYMBOLS': '$(SECRET)'}, {'RESEARCH_SYMBOLS': '../SECRET'},
            {'RESEARCH_SYMBOLS': 'x' * 201},
            {'RESEARCH_SYMBOLS': ' '.join(f'{n:06}.SZ' for n in range(6))},
            {'RESEARCH_UPSTREAM': 'autoSECRET'}, {'RESEARCH_UPSTREAM': 'x' * 201},
            {'RESEARCH_START_DATE': '', 'RESEARCH_END_DATE': '2026-11-06'},
            {'RESEARCH_START_DATE': '2026-11-07'}, {'RESEARCH_START_DATE': '2026-02-30'},
            {'RESEARCH_END_DATE': '2999-01-01'}, {'RESEARCH_END_DATE': '2026-11-06\nSECRET'}]
        for env in values:
            with self.subTest(env=env):
                code, output, quick = self.run_action(self.builder(self.success), env)
                self.assertEqual(code, 2)
                quick.assert_not_called()
                self.assertFalse(self.directory.exists())
                self.assertNotIn('### 本次请求', output)
                self.assertNotIn('SECRET', output)

    def test_partial_package_is_verified_preserved_and_returns_two(self):
        code, output, _ = self.run_action(self.builder(self.partial, 2), {"RESEARCH_SYMBOLS": "000776.SZ,600519.SS"})
        self.assertEqual(code, 2)
        self.assertEqual((self.directory / 'research.zip').read_bytes(), self.partial)
        self.assertTrue(json.loads((self.directory / 'verification.json').read_text())['integrity_verified'])
        self.assertIn('总任务：2；已生成：1；日期待核查：0；失败：1', output)
        action = json.loads((self.directory / 'action-result.json').read_text())
        self.assertEqual(action['rerun_request'], {'schema_version': '0.1', 'symbols': ['600519.SS'],
            'upstream': 'eastmoney', 'start_date': '2026-11-02', 'end_date': '2026-11-06',
            'manual_only': True, 'calendar_review_required': False})
        self.assertIn('| symbols | 600519.SS |', output)
        self.assertNotIn('| symbols | 000776.SZ', output.split('### 本次请求')[0])
        self.assertIn('同窗口手动重跑不保证修复', output)

    def test_inconsistent_all_status_cannot_make_partial_package_green(self):
        with ZipFile(BytesIO(self.partial)) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        manifest = json.loads(files['manifest.json'])
        manifest['status'] = 'ALL_RESEARCH_GENERATED_UNVERIFIED'
        files['manifest.json'] = json.dumps(manifest).encode()
        stream = BytesIO()
        with ZipFile(stream, 'w') as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        code, output, _ = self.run_action(self.builder(stream.getvalue(), 0), {"RESEARCH_SYMBOLS": "000776.SZ,600519.SS"})
        self.assertEqual(code, 2)
        self.assertTrue((self.directory / 'research.zip').exists())
        self.assertTrue(json.loads((self.directory / 'verification.json').read_text())['integrity_verified'])
        self.assertIn('总任务：2；已生成：1；日期待核查：0；失败：1', output)
        self.assertEqual(self.action_output.read_text(), 'artifacts_ready=true\n')

    def test_no_package_and_adapter_exception_emit_safe_failure(self):
        def fail(argv):
            print('SECRET stdout')
            raise RuntimeError('SECRET error')
        for provider in (lambda argv: 2, fail):
            with self.subTest(provider=provider):
                code, output, _ = self.run_action(provider)
                self.assertEqual(code, 2)
                self.assertNotIn('SECRET', output)
                self.assertNotIn('Traceback', output)
                self.assertFalse((self.directory / 'research.zip').exists())
                self.assertFalse(json.loads((self.directory / 'verification.json').read_text())['integrity_verified'])
                (self.directory / 'verification.json').unlink()
                (self.directory / 'action-result.json').unlink()

    def test_invalid_package_is_not_available_for_upload(self):
        code, output, _ = self.run_action(self.builder(b'not a zip'))
        self.assertEqual(code, 2)
        self.assertFalse((self.directory / 'research.zip').exists())
        self.assertNotIn('package', json.loads((self.directory / 'action-result.json').read_text()))
        self.assertIn('完整性校验失败', output)
        self.assertEqual(json.loads((self.directory / 'action-result.json').read_text())['request'],
                         {'symbols': ['000776.SZ'], 'upstream': 'eastmoney',
                          'start_date': '2026-11-02', 'end_date': '2026-11-06'})
        self.assertIn('| end_date | 2026-11-06 |', output)
        self.assertNotIn('rerun_request', json.loads((self.directory / 'action-result.json').read_text()))
        self.assertNotIn('Run workflow', output)
        self.assertFalse(json.loads((self.directory / 'verification.json').read_text())['integrity_verified'])

    def test_exception_after_creating_package_does_not_publish(self):
        def fail(argv):
            self.builder(self.success)(argv)
            raise RuntimeError('SECRET')
        code, _, _ = self.run_action(fail)
        self.assertEqual(code, 2)
        self.assertFalse((self.directory / 'research.zip').exists())

    def test_nonempty_output_directory_refuses_to_reuse_previous_results(self):
        self.directory.mkdir()
        stale = self.directory / 'research.zip'
        stale.write_bytes(b'old evidence')
        code, output, quick = self.run_action(self.builder(self.success))
        self.assertEqual(code, 2)
        quick.assert_not_called()
        self.assertIn('输出目录必须全新或为空', output)
        self.assertNotIn('### 本次请求', output)
        self.assertEqual(stale.read_bytes(), b'old evidence')
        self.assertFalse((self.directory / 'verification.json').exists())
        self.assertFalse(self.action_output.exists())

    def test_empty_directory_accepted_symlink_directory_rejected(self):
        self.directory.mkdir()
        code, _, _ = self.run_action(self.builder(self.success))
        self.assertEqual(code, 0)
        for path in self.directory.iterdir():
            path.unlink()
        self.directory.rmdir()
        target = self.directory.parent / 'target'
        target.mkdir()
        self.directory.symlink_to(target, target_is_directory=True)
        code, _, quick = self.run_action(self.builder(self.success))
        self.assertEqual(code, 2)
        quick.assert_not_called()
        self.assertEqual(list(target.iterdir()), [])

    def test_cannot_emit_ready_does_not_publish_zip(self):
        code, output, _ = self.run_action(self.builder(self.success), {'GITHUB_OUTPUT': str(self.directory / 'missing' / 'output')})
        self.assertEqual(code, 2)
        self.assertFalse((self.directory / 'research.zip').exists())
        self.assertIn('本次研究包不予发布', output)
        self.assertFalse(self.action_output.exists())

    def test_cleanup_permission_error_still_returns_fixed_failure_without_ready(self):
        original = Path.unlink
        def deny_package(path, *args, **kwargs):
            if path.name == 'research.zip':
                raise PermissionError('SECRET')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', deny_package):
            code, output, _ = self.run_action(self.builder(b'bad zip'))
        self.assertEqual(code, 2)
        self.assertNotIn('SECRET', output)
        self.assertFalse(self.action_output.exists())

    def test_classified_exceptions_never_save_or_echo_raw_secrets(self):
        for exception, reason in ((ImportError('SECRET'), 'dependency_unavailable'),
                                  (OSError('SECRET'), 'output_or_execution_failed'),
                                  (ValueError('SECRET'), 'validation_failed'),
                                  (RuntimeError('SECRET'), 'research_execution_failed')):
            with self.subTest(reason=reason):
                def fail(argv):
                    print('SECRET provider body')
                    raise exception
                code, output, _ = self.run_action(fail)
                self.assertEqual(code, 2)
                action = json.loads((self.directory / 'action-result.json').read_text())
                verification = json.loads((self.directory / 'verification.json').read_text())
                self.assertEqual(action['reason'], reason)
                self.assertEqual(action['status'], 'ACTION_FAILED')
                self.assertEqual(action['stage'], 'execution')
                self.assertFalse(verification['integrity_verified'])
                self.assertNotIn('rerun_request', action)
                self.assertNotIn('Run workflow', output)
                self.assertNotIn('integrity_verified', action)
                self.assertNotIn('SECRET', output + json.dumps(action) + json.dumps(verification))
                self.assertTrue(all(value is False for key, value in action.items() if key.endswith('_verified')))
                self.assertIn('artifacts_ready=true', self.action_output.read_text())
                for path in self.directory.iterdir():
                    path.unlink()

    def test_partial_items_use_fixed_reasons_and_counts_without_raw_text(self):
        from tests.test_collect_batch_research import NOW, fetched, request
        from scripts.collect_batch_research import build_collected_batch_package
        def prices(symbol, *args, **kwargs):
            if symbol == '600519.SS':
                raise RuntimeError('SECRET')
            snapshot = fetched(symbol)
            if symbol == '000001.SZ':
                snapshot['records'].pop(1)
            return snapshot
        encoded, _ = build_collected_batch_package(request('000776.SZ', '000001.SZ', '600519.SS'),
            allow_network=True, fetcher=prices, now=NOW)
        code, output, _ = self.run_action(self.builder(encoded, 2), {"RESEARCH_SYMBOLS": "000776.SZ,000001.SZ,600519.SS"})
        self.assertEqual(code, 2)
        action = json.loads((self.directory / 'action-result.json').read_text())
        self.assertEqual(action['status'], 'ACTION_PARTIAL_UNVERIFIED')
        self.assertEqual(action['stage'], 'completed')
        self.assertEqual((action['item_count'], action['generated_count'], action['calendar_blocked_count'], action['failed_count']), (3, 1, 1, 1))
        items = {item['symbol']: item for item in action['items']}
        self.assertEqual(items['600519.SS']['reason'], 'collection_failed')
        self.assertEqual(items['000001.SZ']['missing_date_count'], 1)
        self.assertEqual(items['000001.SZ']['unexpected_date_count'], 0)
        self.assertIn('| 000001.SZ | 日期待核查 | 返回日期与提供的日历不一致；缺失日期：1；额外日期：0 |', output)
        self.assertIn('| 600519.SS | 输入或生成失败 | 供应商采集失败，未取得可用数据 |', output)
        self.assertNotIn('SECRET', output + json.dumps(action))
        self.assertEqual(action['rerun_request']['symbols'], ['000001.SZ', '600519.SS'])
        self.assertTrue(action['rerun_request']['calendar_review_required'])
        self.assertIn('请先核查日历与实际数据', output)
        self.assertNotIn('integrity_verified', action)
        self.assertTrue(json.loads((self.directory / 'verification.json').read_text())['integrity_verified'])

    def test_action_result_save_failure_never_emits_ready_or_publishes_zip(self):
        original = Path.open
        def deny_result(path, *args, **kwargs):
            if path.name == 'action-result.json':
                raise PermissionError('SECRET')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', deny_result):
            code, output, _ = self.run_action(self.builder(self.success))
        self.assertEqual(code, 2)
        self.assertFalse((self.directory / 'research.zip').exists())
        self.assertFalse(self.action_output.exists())
        self.assertNotIn('SECRET', output)

    def test_unsafe_item_metadata_cannot_inject_markdown_in_actions_summary(self):
        with ZipFile(BytesIO(self.success)) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        raw = json.loads(files['batch-result.json'])
        raw['results'][0]['reason'] = 'SECRET | injected\n## Heading'
        files['batch-result.json'] = json.dumps(raw).encode()
        import hashlib
        manifest = json.loads(files['manifest.json'])
        for entry in manifest['files']:
            if entry['path'] == 'batch-result.json':
                entry['size_bytes'] = len(files[entry['path']])
                entry['sha256'] = hashlib.sha256(files[entry['path']]).hexdigest()
        files['manifest.json'] = json.dumps(manifest).encode()
        encoded = BytesIO()
        with ZipFile(encoded, 'w') as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        code, output, _ = self.run_action(self.builder(encoded.getvalue()))
        self.assertEqual(code, 0)
        action = json.loads((self.directory / 'action-result.json').read_text())
        self.assertEqual(action['items'][0]['reason'], 'unknown')
        self.assertNotIn('SECRET', output + json.dumps(action))
        self.assertNotIn('## Heading', output)

    def test_item_status_counts_disagreeing_with_manifest_cannot_make_action_green(self):
        import hashlib
        with ZipFile(BytesIO(self.success)) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        batch_result = json.loads(files['batch-result.json'])
        batch_result['results'][0]['status'] = 'FAILED_INPUT_OR_GENERATION'
        files['batch-result.json'] = json.dumps(batch_result).encode()
        manifest = json.loads(files['manifest.json'])
        for entry in manifest['files']:
            if entry['path'] == 'batch-result.json':
                entry.update(size_bytes=len(files[entry['path']]),
                             sha256=hashlib.sha256(files[entry['path']]).hexdigest())
        files['manifest.json'] = json.dumps(manifest).encode()
        encoded = BytesIO()
        with ZipFile(encoded, 'w') as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        code, output, _ = self.run_action(self.builder(encoded.getvalue()))
        self.assertEqual(code, 2)
        self.assertFalse((self.directory / 'research.zip').exists())
        action = json.loads((self.directory / 'action-result.json').read_text())
        self.assertEqual(action['status'], 'ACTION_FAILED')
        self.assertEqual(action['stage'], 'result_summary')
        self.assertEqual(action['reason'], 'validation_failed')
        self.assertTrue(json.loads((self.directory / 'verification.json').read_text())['integrity_verified'])
        self.assertEqual(self.action_output.read_text(), 'artifacts_ready=true\n')

    def test_rerun_retains_resolved_actual_window_and_original_source(self):
        resolved = {'start_date': '2026-09-01', 'end_date': '2026-09-21'}
        with patch('scripts.quick_research_action.resolve_market_window', return_value=resolved):
            code, output, quick = self.run_action(self.builder(self.partial, 2), {
                'RESEARCH_SYMBOLS': '600519.SS,000776.SZ', 'RESEARCH_UPSTREAM': 'sina',
                'RESEARCH_START_DATE': '', 'RESEARCH_END_DATE': ''})
        self.assertEqual(code, 2)
        quick.assert_called_once()
        argv = quick.call_args.args[0]
        rerun = json.loads((self.directory / 'action-result.json').read_text())['rerun_request']
        self.assertEqual(rerun['start_date'], argv[argv.index('--start-date') + 1])
        self.assertEqual(rerun['end_date'], argv[argv.index('--end-date') + 1])
        self.assertEqual((rerun['start_date'], rerun['end_date']), ('2026-09-01', '2026-09-21'))
        self.assertEqual(rerun['upstream'], 'sina')
        self.assertIn('| upstream | sina |', output)

    def test_wrong_stock_package_is_rejected_without_rerun_advice(self):
        code, output, quick = self.run_action(self.builder(self.success), {'RESEARCH_SYMBOLS': '600519.SS'})
        self.assertEqual(code, 2)
        quick.assert_called_once()
        action = json.loads((self.directory / 'action-result.json').read_text())
        self.assertEqual((action['stage'], action['reason']), ('result_summary', 'validation_failed'))
        self.assertNotIn('rerun_request', action)
        self.assertNotIn('Run workflow', output)
        self.assertFalse((self.directory / 'research.zip').exists())

    def test_resolved_request_matches_quick_argv_result_and_success_summary(self):
        resolved = {'start_date': '2026-09-01', 'end_date': '2026-09-21'}
        with patch('scripts.quick_research_action.resolve_market_window', return_value=resolved):
            code, output, quick = self.run_action(self.builder(self.success_pair), {
                'RESEARCH_SYMBOLS': '600519.SS,000776.SZ', 'RESEARCH_UPSTREAM': 'sina',
                'RESEARCH_START_DATE': '', 'RESEARCH_END_DATE': ''})
        self.assertEqual(code, 0)
        quick.assert_called_once()
        argv = quick.call_args.args[0]
        request = json.loads((self.directory / 'action-result.json').read_text())['request']
        self.assertEqual(request, {'symbols': ['000776.SZ', '600519.SS'], 'upstream': 'sina',
                                  'start_date': '2026-09-01', 'end_date': '2026-09-21'})
        self.assertEqual(request['start_date'], argv[argv.index('--start-date') + 1])
        self.assertEqual(request['end_date'], argv[argv.index('--end-date') + 1])
        self.assertEqual(request['upstream'], argv[argv.index('--upstream') + 1])
        self.assertIn('### 本次请求', output)
        self.assertIn('| symbols | 000776.SZ,600519.SS |', output)
        for key in ('upstream', 'start_date', 'end_date'):
            self.assertIn('| ' + key + ' | ' + request[key] + ' |', output)
        self.assertEqual(self.summary.read_text(), output)
        self.assertNotIn('rerun_request', json.loads((self.directory / 'action-result.json').read_text()))

    def test_execution_failure_retains_only_validated_request(self):
        def fail(argv):
            raise ImportError('SECRET dependency details')
        code, output, quick = self.run_action(fail, {'RESEARCH_SYMBOLS': '600519.SS,000776.SZ'})
        self.assertEqual(code, 2)
        quick.assert_called_once()
        action = json.loads((self.directory / 'action-result.json').read_text())
        self.assertEqual(action['reason'], 'dependency_unavailable')
        self.assertEqual(action['request'], {'symbols': ['000776.SZ', '600519.SS'], 'upstream': 'eastmoney',
                                             'start_date': '2026-11-02', 'end_date': '2026-11-06'})
        self.assertIn('| symbols | 000776.SZ,600519.SS |', output)
        self.assertIn('| start_date | 2026-11-02 |', output)
        self.assertNotIn('SECRET', output + json.dumps(action))
        self.assertNotIn('rerun_request', action)
