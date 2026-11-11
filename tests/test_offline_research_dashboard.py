import base64
from copy import deepcopy
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.offline_research_dashboard import CSS, build_dashboard
from scripts.sma_evaluation_cli import build_evaluation_artifact
from scripts.financial_review_pipeline import build_financial_review_artifact
from tests.test_financial_table_review_integration import synthetic_table_pdf

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "examples/batch_research/SYNTHETIC_offline_pipeline.json"
EVALUATION = ROOT / "examples/backtest/SYNTHETIC_sma_oos_config.json"


def read(path):
    return json.loads(path.read_text())


def cli(output, *options):
    return subprocess.run([sys.executable, "-m", "scripts.offline_research_dashboard", "--output", str(output),
                           *map(str, options)], cwd=ROOT, capture_output=True, text=True, timeout=20)


class Tags(HTMLParser):
    def __init__(self, value):
        super().__init__()
        self.tags = []
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class OfflineDashboardTests(unittest.TestCase):
    def test_true_cli_both_raw_configs_render_values_and_repeatable_single_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dashboard.html"
            args = ("--batch-config", BATCH, "--evaluation-config", EVALUATION)
            result = cli(output, *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            first = output.read_bytes()
            html = first.decode()
            self.assertIn("任务总数<strong>3", html)
            self.assertIn("生成摘要<strong>1", html)
            self.assertIn("缺失或失败<strong>2", html)
            for status in ("COMPLETED_UNVERIFIED", "FAILED_INPUT_VALIDATION", "MISSING_INPUT"):
                self.assertIn(status, html)
            self.assertIn("合成测试数据", html)
            evaluated = build_evaluation_artifact(read(EVALUATION))["evaluation"]
            for key in ("train", "test", "benchmark"):
                self.assertIn(f'{evaluated[key]["final_marked_equity"]:,.2f}', html)
                self.assertIn(f'{evaluated["metrics"][key]["max_drawdown_fraction"] * 100:,.2f}%', html)
            self.assertEqual(len([tag for tag, attrs in Tags(html).tags if tag == "polyline"]), 2)
            self.assertIn("初始资金", html)
            self.assertIn("不是实际行情或已核实绩效", html)
            self.assertEqual(cli(output, *args).returncode, 0)
            self.assertEqual(output.read_bytes(), first)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["dashboard.html"])

    def test_either_section_alone_and_at_least_one_input_required(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dashboard.html"
            self.assertEqual(cli(output, "--batch-config", BATCH).returncode, 0)
            self.assertIn("批量研究任务", output.read_text())
            self.assertNotIn("<h2>样本外纸面评估", output.read_text())
            self.assertEqual(cli(output, "--evaluation-config", EVALUATION).returncode, 0)
            self.assertIn("样本外纸面评估", output.read_text())
            self.assertNotIn("<h2>批量研究任务", output.read_text())
            before = output.read_bytes()
            self.assertNotEqual(cli(output).returncode, 0)
            self.assertEqual(output.read_bytes(), before)

    def test_html_data_escapes_without_creating_active_elements_or_attributes(self):
        batch, evaluation = read(BATCH), read(EVALUATION)
        notice = '</td><script>alert("x")</script><img src="https://evil.invalid" onerror="alert(1)">'
        version = '<svg onload="alert(1)">'
        batch["reports"]["000776.SZ"]["fixture_notice"] = notice
        evaluation["snapshot"]["akshare_version"] = version
        html = build_dashboard(batch_config=batch, evaluation_config=evaluation)
        self.assertIn(escape(notice, quote=True), html)
        self.assertIn(escape(version, quote=True), html)
        parsed = Tags(html)
        self.assertFalse(set(tag for tag, attrs in parsed.tags) & {"script", "img", "iframe", "object", "link", "form"})
        for tag, attrs in parsed.tags:
            self.assertFalse(any(key.lower().startswith("on") or key in ("src", "href", "style") for key in attrs))
        self.assertEqual(len([tag for tag, attrs in parsed.tags if tag == "svg"]), 1)

    def test_csp_only_allows_the_exact_static_style_and_no_scripts_or_connections(self):
        html = build_dashboard(batch_config=read(BATCH))
        expected_hash = base64.b64encode(hashlib.sha256(CSS.encode()).digest()).decode()
        metas = [attrs for tag, attrs in Tags(html).tags if tag == "meta"]
        csp = next(meta["content"] for meta in metas if meta.get("http-equiv") == "Content-Security-Policy")
        self.assertIn(f"style-src 'sha256-{expected_hash}'", csp)
        for directive in ("default-src 'none'", "script-src 'none'", "connect-src 'none'", "base-uri 'none'"):
            self.assertIn(directive, csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertIn(f"<style>{CSS}</style>", html)
        self.assertIn("@media(max-width:650px)", html)

    def test_inputs_are_recomputed_and_cannot_supply_forged_result_metrics(self):
        batch, evaluation = read(BATCH), read(EVALUATION)
        original_batch, original_evaluation = deepcopy(batch), deepcopy(evaluation)
        html = build_dashboard(batch_config=batch, evaluation_config=evaluation)
        self.assertEqual(batch, original_batch)
        self.assertEqual(evaluation, original_evaluation)
        batch["reports"].pop("000776.SZ")
        changed = build_dashboard(batch_config=batch)
        self.assertIn("生成摘要<strong>0", changed)
        self.assertNotEqual(html, changed)
        evaluation["settings"]["initial_cash"] = 20000
        expected = build_evaluation_artifact(evaluation)["evaluation"]["test"]["final_marked_equity"]
        self.assertIn(f"{expected:,.2f}", build_dashboard(evaluation_config=evaluation))
        with self.assertRaises(ValueError):
            build_dashboard(evaluation_config=build_evaluation_artifact(evaluation))
        evaluation["evaluation"] = {"experimental_total_return": 999}
        with self.assertRaises(ValueError):
            build_dashboard(evaluation_config=evaluation)

    def test_true_cli_bad_json_or_invalid_other_section_preserves_previous_html(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "config.json", Path(directory) / "dashboard.html"
            output.write_text("prior dashboard")
            for raw in ('{"schema_version":"0.1","schema_version":"0.1"}', '{broken',
                        EVALUATION.read_text().replace('"initial_cash": 10000', '"initial_cash": NaN')):
                source.write_text(raw)
                completed = cli(output, "--batch-config", BATCH, "--evaluation-config", source)
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(output.read_text(), "prior dashboard")
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["config.json", "dashboard.html"])

    def test_explicit_null_section_never_silently_disappears_with_another_valid_section(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "null.json", Path(directory) / "dashboard.html"
            source.write_text("null")
            output.write_text("prior dashboard")
            for flag in ("--financial-config", "--evaluation-config", "--batch-config"):
                valid = ("--evaluation-config", EVALUATION) if flag == "--batch-config" else ("--batch-config", BATCH)
                with self.subTest(flag=flag):
                    self.assertNotEqual(cli(output, *valid, flag, source).returncode, 0)
                    self.assertEqual(output.read_text(), "prior dashboard")

    def test_true_cli_refuses_inputs_aliases_and_symlink_output(self):
        with tempfile.TemporaryDirectory() as directory:
            batch, evaluation = Path(directory) / "batch.json", Path(directory) / "evaluation.json"
            batch.write_bytes(BATCH.read_bytes())
            evaluation.write_bytes(EVALUATION.read_bytes())
            for output in (batch, evaluation):
                before = output.read_bytes()
                self.assertNotEqual(cli(output, "--batch-config", batch, "--evaluation-config", evaluation).returncode, 0)
                self.assertEqual(output.read_bytes(), before)
            alias = Path(directory) / "alias.html"
            os.link(evaluation, alias)
            self.assertNotEqual(cli(alias, "--evaluation-config", evaluation).returncode, 0)
            target, link = Path(directory) / "target.html", Path(directory) / "link.html"
            target.write_text("keep")
            link.symlink_to(target)
            self.assertNotEqual(cli(link, "--batch-config", batch).returncode, 0)
            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_text(), "keep")


@unittest.skipUnless(importlib.util.find_spec("pdfplumber"), "optional pdfplumber not installed")
class FinancialDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = Path(self.tmp.name) / "private_input_name.pdf"
        self.pdf.write_bytes(synthetic_table_pdf())
        self.config = dict(schema_version="0.1", data_kind="SYNTHETIC", pdf_path=str(self.pdf),
                           symbol="000776.SZ", announcement_date="2026-10-30", pages=[1], annotations=None)

    def test_financial_rows_counts_hashes_scope_and_omitted_rows_are_explicit(self):
        artifact = build_financial_review_artifact(self.pdf, "000776.SZ", "2026-10-30", [1])
        html = build_dashboard(financial_config=self.config, max_financial_rows=1)
        self.assertIn("数值候选<strong>3", html)
        self.assertIn("待记录决定<strong>3", html)
        self.assertIn("显示 1 项，省略 2 项", html)
        self.assertIn(artifact["package"]["candidates"][0]["cell"]["text"], html)
        self.assertIn(artifact["package"]["file_sha256"], html)
        self.assertIn(artifact["validation"]["package_sha256"], html)
        self.assertIn("consolidation_scope", html)
        self.assertIn("未知 · 未核实", html)
        self.assertIn("发布证据接受：否", html)
        self.assertNotIn(str(self.pdf), html)
        self.assertNotIn(self.pdf.name, html)

    def test_bound_annotations_are_escaped_and_do_not_promote_acceptance(self):
        artifact = build_financial_review_artifact(self.pdf, "000776.SZ", "2026-10-30", [1])
        reviewer, note = '<img src="x" onerror="alert(1)">', '</td><script>alert(1)</script>'
        self.config["annotations"] = {"file_sha256": artifact["package"]["file_sha256"],
                                      "package_sha256": artifact["validation"]["package_sha256"],
                                      "decisions": [{"candidate_index": 0, "decision": "accepted_by_reviewer",
                                                     "reviewer": reviewer, "note": note}]}
        html = build_dashboard(financial_config=self.config)
        self.assertIn(escape(reviewer, quote=True), html)
        self.assertIn(escape(note, quote=True), html)
        self.assertIn("待记录决定<strong>2", html)
        self.assertIn("已记录决定<strong>1", html)
        self.assertIn("accepted_by_reviewer", html)
        self.assertIn("发布证据接受：否", html)
        self.assertFalse(set(tag for tag, attrs in Tags(html).tags) & {"script", "img"})

    def test_exact_financial_config_schema_and_bounded_rows_reject_invalid_values(self):
        for key in self.config:
            changed = deepcopy(self.config)
            del changed[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_dashboard(financial_config=changed)
        changed = {**self.config, "package": {"release_evidence_accepted": True}}
        with self.assertRaises(ValueError):
            build_dashboard(financial_config=changed)
        for maximum in (True, 0, -1, 501, 1.5):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                build_dashboard(financial_config=self.config, max_financial_rows=maximum)

    def test_cli_invalid_annotations_cannot_replace_a_prior_page(self):
        self.config["annotations"] = {"file_sha256": "0" * 64, "package_sha256": "1" * 64, "decisions": []}
        source, output = Path(self.tmp.name) / "financial.json", Path(self.tmp.name) / "dashboard.html"
        source.write_text(json.dumps(self.config))
        output.write_text("prior dashboard")
        self.assertNotEqual(cli(output, "--financial-config", source).returncode, 0)
        self.assertEqual(output.read_text(), "prior dashboard")

    def test_no_numeric_candidates_is_not_shown_as_completed_financial_verification(self):
        self.pdf.write_bytes(synthetic_table_pdf([
            ("", "本报告期", "年初至报告期末"),
            ("营业总收入（元）", "-", "-"), ("总资产（元）", "-", "-")]))
        html = build_dashboard(financial_config=self.config)
        self.assertIn("no_numeric_candidates", html)
        self.assertIn("数值候选<strong>0", html)
        self.assertIn("不代表报表没有财务数据或复核已经完成", html)
        self.assertIn("发布证据接受：否", html)
