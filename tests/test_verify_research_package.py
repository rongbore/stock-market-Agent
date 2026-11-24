import contextlib
import copy
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZipFile, ZipInfo

from scripts.batch_research_package import build_batch_research_package
from scripts.collect_batch_research import build_collected_batch_package
from scripts.quick_market_research import build_quick_research_package
from scripts.verify_research_package import main, verify_research_package
from tests.test_batch_calendar_research import batch, job
from tests.test_collect_batch_research import NOW, fetched, request
from tests.test_quick_market_research import calendar


class VerifyResearchPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoded, cls.manifest = build_batch_research_package(batch(job()))
        with ZipFile(BytesIO(cls.encoded)) as archive:
            cls.files = {name: archive.read(name) for name in archive.namelist()}

    def verify(self, encoded):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'research.zip'
            path.write_bytes(encoded)
            before = path.read_bytes()
            result = verify_research_package(path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(folder).iterdir()), [path])
            return result

    def archive(self, files=None, extra=()):
        stream = BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with ZipFile(stream, 'w', compression=ZIP_DEFLATED) as archive:
                for name, data in (self.files if files is None else files).items():
                    archive.writestr(name, data)
                for name, data in extra:
                    archive.writestr(name, data)
        return stream.getvalue()

    def invalid(self, encoded, reason=None):
        result = self.verify(encoded)
        self.assertFalse(result['integrity_verified'])
        self.assertEqual(result['status'], 'INVALID_PACKAGE')
        if reason:
            self.assertEqual(result['reason'], reason)
        self.assertTrue(all(result[key] is False for key in result if key.endswith('_verified')))
        return result

    def test_all_three_real_builders_verify_but_never_certify_sources(self):
        collected, _ = build_collected_batch_package(request(), allow_network=True, fetcher=fetched, now=NOW)
        quick, _ = build_quick_research_package(['000776.SZ'], 'eastmoney', start_date='2026-11-02',
            end_date='2026-11-06', allow_network=True, calendar_fetcher=calendar, price_fetcher=fetched, now=NOW)
        for encoded in (self.encoded, collected, quick):
            with self.subTest(size=len(encoded)):
                result = self.verify(encoded)
                self.assertTrue(result['integrity_verified'])
                self.assertGreater(result['checked_file_count'], 0)
                self.assertIn('不认证来源', result['limitation'])
                self.assertFalse(result['source_content_verified'])
                self.assertFalse(result['independent_source_verified'])

    def test_tampered_size_hash_missing_and_extra_members(self):
        for data, reason in ((b'x', 'size_mismatch'), (b'x' * len(self.files['index.html']), 'hash_mismatch')):
            files = dict(self.files)
            files['index.html'] = data
            self.invalid(self.archive(files), reason)
        files = dict(self.files)
        del files['index.html']
        self.invalid(self.archive(files), 'path_set_mismatch')
        self.invalid(self.archive(extra=[('extra.txt', b'x')]), 'path_set_mismatch')
        self.invalid(self.archive(extra=[('index.html', b'x')]), 'duplicate_member')
        files = dict(self.files)
        del files['manifest.json']
        self.invalid(self.archive(files), 'invalid_manifest')

    def test_path_directory_symlink_and_unsupported_compression_rejected(self):
        for name in ('/absolute', '../outside', 'a/../outside', 'a\\b', 'C:/drive', 'a//b', './a', 'a/'):
            with self.subTest(name=name):
                self.invalid(self.archive(extra=[(name, b'x')]), 'unsafe_member')
        nul_name = self.archive(extra=[('nul_suffix', b'x')]).replace(b'nul_suffix', b'nul\x00suffix')
        self.invalid(nul_name, 'unsafe_member')
        link = ZipInfo('link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.invalid(self.archive(extra=[(link, b'/tmp/target')]), 'unsafe_member')
        directory = ZipInfo('dir')
        directory.external_attr = (stat.S_IFDIR | 0o755) << 16
        self.invalid(self.archive(extra=[(directory, b'')]), 'unsafe_member')

    def test_encrypted_and_non_supported_compression_fail_preflight(self):
        unsupported = ZipInfo('unsupported')
        unsupported.compress_type = ZIP_BZIP2
        self.invalid(self.archive(extra=[(unsupported, b'data')]), 'unsafe_member')
        encrypted = bytearray(self.encoded)
        encrypted[6] |= 1
        central = encrypted.index(b'PK\x01\x02')
        encrypted[central + 8] |= 1
        self.invalid(bytes(encrypted), 'unsafe_member')

    def test_strict_manifest_shape_types_duplicates_and_json(self):
        invalid = []
        for key, value in (('schema_version', '9'), ('item_count', True), ('item_count', 2),
                           ('source_content_verified', 'true'), ('batch_input_sha256', 'X' * 64),
                           ('files', {}), ('calendar_source_file', 'evil.json')):
            manifest = copy.deepcopy(self.manifest)
            manifest[key] = value
            invalid.append(json.dumps(manifest).encode())
        manifest = copy.deepcopy(self.manifest)
        manifest['files'].append(manifest['files'][0])
        invalid.append(json.dumps(manifest).encode())
        for entry_change in ({'size_bytes': True}, {'sha256': 'x'}, {'path': '../x'}, {'other': 1}):
            manifest = copy.deepcopy(self.manifest)
            manifest['files'][0].update(entry_change)
            invalid.append(json.dumps(manifest).encode())
        invalid += [b'{', b'[]', b'\xff', b'{"schema_version":"0.1","schema_version":"0.1"}',
                    b'{"files":NaN}']
        for raw in invalid:
            with self.subTest(raw=raw[:100]):
                files = dict(self.files)
                files['manifest.json'] = raw
                self.invalid(self.archive(files), 'invalid_manifest')

    def test_untrusted_verified_labels_are_ignored_and_html_not_executed(self):
        files = dict(self.files)
        manifest = copy.deepcopy(self.manifest)
        for key in ('source_content_verified', 'historical_point_in_time_verified', 'exchange_calendar_verified'):
            manifest[key] = True
        payload = b'<script>throw new Error("MUST_NOT_EXECUTE")</script>'
        files['index.html'] = payload
        for entry in manifest['files']:
            if entry['path'] == 'index.html':
                entry.update(size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        files['manifest.json'] = json.dumps(manifest).encode()
        result = self.verify(self.archive(files))
        self.assertTrue(result['integrity_verified'])
        self.assertFalse(result['source_content_verified'])
        self.assertFalse(result['historical_point_in_time_verified'])
        self.assertFalse(result['exchange_calendar_verified'])

    def test_limits_checked_before_member_reads(self):
        for constant, limit in (('MAX_ARCHIVE_BYTES', 10), ('MAX_MEMBERS', 1), ('MAX_MEMBER_BYTES', 10),
                                ('MAX_TOTAL_BYTES', 10), ('MAX_MANIFEST_BYTES', 10), ('MAX_CENTRAL_DIRECTORY_BYTES', 10)):
            with self.subTest(limit=constant), patch('scripts.verify_research_package.' + constant, limit):
                with patch('zipfile.ZipFile.open', side_effect=AssertionError('must preflight first')):
                    self.invalid(self.encoded, 'limit_exceeded')

    def test_directory_preflight_runs_before_zipfile_metadata_allocation(self):
        oversized_count = self.archive(extra=[('empty' + str(i), b'') for i in range(129)])
        with patch('scripts.verify_research_package.ZipFile', side_effect=AssertionError('must preflight first')):
            self.invalid(oversized_count, 'limit_exceeded')
        # A forged low count cannot bypass the central-directory byte bound.
        raw_directory = b'x' * (256 * 1024 + 1)
        fake_count = raw_directory + struct.pack('<4s4H2LH', b'PK\x05\x06', 0, 0, 1, 1,
                                                len(raw_directory), 0, 0)
        with patch('scripts.verify_research_package.ZipFile', side_effect=AssertionError('must preflight first')):
            self.invalid(fake_count, 'limit_exceeded')
        # ZipFile recognizes this locator even without sentinel EOCD fields.
        locator = b'PK\x06\x07' + b'\x00' * 16
        locator_archive = locator + struct.pack('<4s4H2LH', b'PK\x05\x06', 0, 0, 0, 0, 20, 0, 0)
        with patch('scripts.verify_research_package.ZipFile', side_effect=AssertionError('must preflight first')):
            self.invalid(locator_archive, 'invalid_zip')
        raw = bytearray(self.encoded)
        raw[-12:-10] = b'\xff\xff'  # ZIP64 count sentinel in standard EOCD.
        with patch('scripts.verify_research_package.ZipFile', side_effect=AssertionError('must preflight first')):
            self.invalid(bytes(raw), 'invalid_zip')

    def test_bad_zip_crc_truncation_and_missing_file_are_safe(self):
        self.invalid(b'not a zip', 'invalid_zip')
        self.invalid(self.encoded[:-20], 'invalid_zip')
        damaged = bytearray(self.encoded)
        with ZipFile(BytesIO(self.encoded)) as archive:
            info = archive.getinfo('index.html')
            start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        damaged[start] ^= 1
        self.invalid(bytes(damaged), 'invalid_zip')
        result = verify_research_package('/missing/SECRET.zip')
        self.assertFalse(result['integrity_verified'])
        self.assertNotIn('SECRET', json.dumps(result))

    def test_cli_json_exit_codes_and_module_entry_point(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'research.zip'
            for encoded, code in ((self.encoded, 0), (b'bad zip', 2)):
                path.write_bytes(encoded)
                output = StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(['--input', str(path)]), code)
                self.assertEqual(json.loads(output.getvalue())['integrity_verified'], code == 0)
            path.write_bytes(self.encoded)
            completed = subprocess.run([sys.executable, '-m', 'scripts.verify_research_package', '--input', str(path)],
                                       capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0)
            self.assertTrue(json.loads(completed.stdout)['integrity_verified'])
            self.assertEqual(completed.stderr, '')
