from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.batch_research_plan import build_batch_plan
from scripts.batch_research_summary import render_summary, validate_bundle, main
from scripts.offline_batch_research_runner import run_batch_plan


def report(symbol="000776.SZ"):
    return {"symbol": symbol, "dates": ["2026-11-05", "2026-11-06"], "prices": [10, 11]}


def bundle():
    plan = build_batch_plan(["000776.SZ", "600519.SS"], "2026-11-08")
    return run_batch_plan(plan, {"000776.SZ": report(), "600519.SS": report("wrong")})


class BatchSummaryTests(unittest.TestCase):
    def test_mixed_success_failure_provenance_and_determinism(self):
        result = bundle()
        original = deepcopy(result)
        text = render_summary(result)
        self.assertIn("摘要生成成功 1 项，失败或缺失 1 项", text)
        self.assertIn("股票代码、日期或价格校验失败", text)
        self.assertIn("历史方向：上涨", text)
        self.assertIn(result["plan_sha256"], text)
        self.assertTrue(all(row["input_sha256"] in text for row in result["results"]))
        self.assertIn("来源、价格和历史时点均未核实", text)
        self.assertEqual(text, render_summary(deepcopy(result)))
        self.assertEqual(result, original)

    def test_rejects_tampered_counts_status_hash_encoding_and_job_identity(self):
        for field, value in (("succeeded_count", 2), ("job_count", True), ("failed_count", -1),
                             ("status", "COMPLETED_UNVERIFIED"), ("hash_encoding", "unknown"),
                             ("plan_sha256", "0" * 64), ("plan_id", "batch-" + "0" * 64)):
            changed = bundle()
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                render_summary(changed)
        for field, value in (("input_sha256", "X" * 64), ("input_sha256", None),
                             ("status", "APPROVED"), ("job_id", "../../x"),
                             ("input_hash_status", "missing"), ("reason", "pretend success")):
            changed = bundle()
            changed["results"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                render_summary(changed)

    def test_rejects_verification_prediction_and_advice_promotions(self):
        for level, flags in (("top", ["source_verified", "historical_point_in_time_verified", "is_prediction", "is_trading_advice"]),
                             ("result", ["source_verified"]),
                             ("brief", ["source_verified", "official_verified", "is_prediction", "is_trading_advice"])):
            for flag in flags:
                for bad in (True, 0, "false"):
                    changed = bundle()
                    target = changed if level == "top" else changed["results"][0]
                    if level == "brief":
                        target = target["brief"]
                    target[flag] = bad
                    with self.subTest(level=level, flag=flag, bad=bad), self.assertRaises(ValueError):
                        render_summary(changed)

    def test_escapes_html_markdown_newlines_and_bounds_rows_text(self):
        result = bundle()
        facts = result["results"][0]["brief"]["facts"]
        facts[:] = ["<script>alert(1)</script> [click](https://evil) | **bold**\n# heading", "x" * 200,
                    "third", "omitted fourth"]
        text = render_summary(result, max_rows=1)
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn(r"\[click\]\(https://evil\)", text)
        self.assertIn(r"\| \*\*bold\*\*", text)
        self.assertNotIn("\n# heading", text)
        self.assertIn("省略 40 字", text)
        self.assertIn("事实显示 3 条，省略 1 条", text)
        self.assertIn("显示 1 项，省略 1 项", text)
        self.assertNotIn("omitted fourth", text)

    def test_missing_and_non_json_failure_hashes_are_explicit(self):
        plan = build_batch_plan(["000776.SZ", "600519.SS"], "2026-11-08")
        result = run_batch_plan(plan, {"000776.SZ": {"extra": float("nan")}})
        text = render_summary(result)
        self.assertIn("无法生成有界 JSON 哈希", text)
        self.assertIn("缺失输入", text)
        self.assertIn("输入不是受支持的有界 JSON", text)
        self.assertIn("未提供趋势报告", text)

    def test_rejects_future_windows_unknown_fields_and_duplicate_symbols(self):
        result = bundle()
        result["results"][0]["brief"]["evidence_window"]["end"] = "2026-11-09"
        with self.assertRaises(ValueError):
            validate_bundle(result)
        result = bundle()
        result["extra"] = "x"
        with self.assertRaises(ValueError):
            validate_bundle(result)
        result = bundle()
        result["results"][1]["symbol"] = "000776.SZ"
        with self.assertRaises(ValueError):
            validate_bundle(result)
        for limit in (0, 101, True):
            with self.assertRaises(ValueError):
                render_summary(bundle(), limit)

    def test_cli_writes_one_file_and_preserves_input_on_invalid_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "result.json", Path(directory) / "summary.md"
            source.write_text(json.dumps(bundle()))
            args = ["--input", str(source), "--output", str(output)]
            self.assertEqual(main(args), 0)
            text = output.read_text()
            self.assertIn("批量研究结果摘要（未核验）", text)
            with self.assertRaises(ValueError):
                main(args[:-1] + [str(source)])
            source.write_text('{"schema_version":"0.1","schema_version":"wrong"}')
            with self.assertRaises(ValueError):
                main(args)
            self.assertEqual(output.read_text(), text)
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["result.json", "summary.md"])
