import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.snapshot_research_config import build_snapshot_research_config, main
from scripts.offline_batch_pipeline import build_pipeline
from scripts.offline_research_dashboard import build_dashboard

ROOT = Path(__file__).resolve().parents[1]


def config():
    snapshot = json.loads((ROOT / "examples/backtest/SYNTHETIC_sma_oos_config.json").read_text())["snapshot"]
    return {"schema_version": "0.1", "data_kind": "SYNTHETIC", "analysis_date": snapshot["end_date"],
            "evidence_as_of": snapshot["retrieved_at"], "expected_adjustment": "unadjusted",
            "snapshots": {snapshot["symbol"]: snapshot}}


class SnapshotAdapterTests(unittest.TestCase):
    def test_snapshot_to_pipeline_and_dashboard_without_mocks(self):
        source = config()
        original = copy.deepcopy(source)
        result = build_snapshot_research_config(source)
        artifact = build_pipeline(result)
        self.assertEqual(artifact["bundle"]["succeeded_count"], 1)
        self.assertIn("批量研究任务", build_dashboard(batch_config=result))
        self.assertFalse(artifact["bundle"]["source_verified"])
        facts = " ".join(artifact["bundle"]["results"][0]["brief"]["facts"])
        self.assertIn("单源收盘价", facts)
        self.assertNotIn("共同日期", facts)
        self.assertNotIn("收盘价均值", facts)
        self.assertFalse(result["reports"][result["symbols"][0]]["numerical_agreement"])
        self.assertEqual(source, original)

    def test_content_changes_change_snapshot_hash(self):
        source = config()
        symbol = next(iter(source["snapshots"]))
        one = build_snapshot_research_config(source)
        source["snapshots"][symbol]["records"][0]["volume"] += 1
        two = build_snapshot_research_config(source)
        a, b = [x["reports"][symbol]["snapshot_provenance_unverified"]["snapshot_sha256"] for x in (one, two)]
        self.assertNotEqual(a, b)
        self.assertEqual(one["reports"][symbol]["prices"], two["reports"][symbol]["prices"])

    def test_future_rows_wrong_symbol_and_units_are_not_silently_dropped(self):
        for change in ("future", "symbol", "unit", "adjustment"):
            source = config()
            snapshot = next(iter(source["snapshots"].values()))
            if change == "future":
                source["analysis_date"] = snapshot["start_date"]
            elif change == "symbol":
                snapshot["symbol"] = "600519.SS"
            elif change == "unit":
                snapshot["volume_unit"] = "unknown"
            else:
                source["expected_adjustment"] = "forward_adjusted"
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_snapshot_research_config(source)

    def test_unverified_local_is_not_promoted(self):
        source = config()
        source["data_kind"] = "UNVERIFIED_LOCAL"
        result = build_snapshot_research_config(source)
        self.assertEqual(result["data_kind"], "UNVERIFIED_LOCAL")
        provenance = result["reports"][result["symbols"][0]]["snapshot_provenance_unverified"]
        self.assertFalse(provenance["historical_point_in_time_verified"])

    def test_single_source_cannot_claim_dual_source_agreement(self):
        from scripts.market_research_brief import build_brief
        brief = build_brief({"symbol": "000776.SZ", "dates": ["2026-11-06"], "prices": [10],
                             "price_basis": "single_source_close", "numerical_agreement": True})
        self.assertNotIn("所附比较结果标记双源数值一致", " ".join(brief["facts"]))
        self.assertFalse(brief["source_verified"])

    def test_cli_is_deterministic_and_invalid_input_preserves_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/"snapshots.json", Path(folder)/"batch.json"
            value = config()
            source.write_text(json.dumps(value))
            args = ["--input", str(source), "--output", str(output)]
            main(args)
            original = output.read_bytes()
            main(args)
            self.assertEqual(output.read_bytes(), original)
            value["snapshots"] = {}
            source.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                main(args)
            self.assertEqual(output.read_bytes(), original)
            with self.assertRaises(ValueError):
                main(["--input", str(source), "--output", str(source)])
