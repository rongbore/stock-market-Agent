"""Exercise the committed mixed-data quickstart through the real ZIP CLI."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(value for name, value in attrs if name == 'href')


class BatchPackageQuickstartTests(unittest.TestCase):
    def test_mixed_demo_exports_only_success_page_and_all_index_links_resolve(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'mixed.zip'
            result = subprocess.run([sys.executable, '-m', 'scripts.batch_research_package',
                '--input', str(ROOT / 'examples/offline_quickstart/SYNTHETIC_batch_calendar_research.json'),
                '--output', str(output)], cwd=ROOT, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            with ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                manifest = json.loads(archive.read('manifest.json'))
                self.assertEqual((manifest['generated_count'], manifest['calendar_blocked_count'], manifest['failed_count']), (1, 1, 1))
                parser = Links()
                parser.feed(archive.read('index.html').decode())
                self.assertTrue(parser.links)
                self.assertTrue(all(link in archive.namelist() for link in parser.links))
                dashboards = [name for name in archive.namelist() if name.endswith('/dashboard.html')]
                self.assertEqual(dashboards, ['items/000776.SZ/dashboard.html'])
                for entry in manifest['files']:
                    data = archive.read(entry['path'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
