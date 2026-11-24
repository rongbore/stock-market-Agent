import contextlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
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

    def test_valid_env_explicit_safe_argv_and_success_artifacts(self):
        code, output, quick = self.run_action(self.builder(self.success), {'RESEARCH_SYMBOLS': '000776.SZ，600519.SS'})
        self.assertEqual(code, 0)
        argv = quick.call_args.args[0]
        self.assertEqual(argv[:4], ['--symbols', '000776.SZ', '600519.SS', '--upstream'])
        self.assertIn('--allow-network', argv)
        self.assertEqual(argv[-2:], ['--output', str(self.directory / 'research.zip')])
        self.assertEqual((self.directory / 'research.zip').read_bytes(), self.success)
        verification = json.loads((self.directory / 'verification.json').read_text())
        self.assertTrue(verification['integrity_verified'])
        self.assertFalse(verification['source_content_verified'])
        self.assertIn('总任务：1；已生成：1；日期待核查：0；失败：0', output)
        self.assertIn('独立来源已核验：否', output)
        self.assertEqual(self.summary.read_text(), output)
        self.assertEqual(self.action_output.read_text(), 'artifacts_ready=true\n')

    def test_whitespace_symbols_and_omitted_dates_resolve_before_call(self):
        code, _, quick = self.run_action(self.builder(self.success), {
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
                self.assertNotIn('SECRET', output)

    def test_partial_package_is_verified_preserved_and_returns_two(self):
        code, output, _ = self.run_action(self.builder(self.partial, 2))
        self.assertEqual(code, 2)
        self.assertEqual((self.directory / 'research.zip').read_bytes(), self.partial)
        self.assertTrue(json.loads((self.directory / 'verification.json').read_text())['integrity_verified'])
        self.assertIn('总任务：2；已生成：1；日期待核查：0；失败：1', output)

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
        code, output, _ = self.run_action(self.builder(stream.getvalue(), 0))
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

    def test_invalid_package_is_not_available_for_upload(self):
        code, output, _ = self.run_action(self.builder(b'not a zip'))
        self.assertEqual(code, 2)
        self.assertFalse((self.directory / 'research.zip').exists())
        self.assertIn('完整性校验失败', output)
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
