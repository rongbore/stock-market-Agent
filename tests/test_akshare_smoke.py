import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.akshare_smoke import main


class AKShareSmokeTests(unittest.TestCase):
    def test_writes_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            with patch("scripts.akshare_smoke.fetch_a_share_daily", return_value={
                "source_content_verified": False,
                "records": [{"date": "2026-10-29"}],
            }) as fetch:
                main(["--start-date", "2026-10-01", "--end-date", "2026-10-30",
                      "--output", str(path)])
            self.assertFalse(json.loads(path.read_text())["source_content_verified"])
            fetch.assert_called_once_with("000776.SZ", "2026-10-01", "2026-10-30")

    def test_empty_response_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            with patch("scripts.akshare_smoke.fetch_a_share_daily", return_value={"records": []}):
                with self.assertRaises(RuntimeError):
                    main(["--start-date", "2026-10-01", "--end-date", "2026-10-30",
                          "--output", str(path)])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
