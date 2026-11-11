"""Generate one local read-only HTML dashboard by recomputing explicit raw configs."""
import argparse
import base64
import hashlib
from html import escape
import os
from pathlib import Path
import tempfile

from scripts.offline_batch_pipeline import build_pipeline
from scripts.offline_batch_research_runner import _canonical_json_bytes
from scripts.financial_review_pipeline import build_financial_review_artifact
from scripts.sma_evaluation_cli import _load_config, build_evaluation_artifact

MAX_HTML_BYTES = 2 * 1024 * 1024
CSS = """*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#14243b;font:15px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1160px;margin:auto;padding:36px 24px}header{padding:12px 0 26px}.eyebrow{color:#526784;font-size:13px;letter-spacing:.08em}h1{font-size:32px;line-height:1.3;margin:12px 0}h2{font-size:23px;margin:0 0 12px}h3{font-size:16px;margin:22px 0 8px}p{margin:8px 0}.muted{color:#526784}.pill{display:inline-block;background:#e9efff;color:#284e9c;padding:4px 12px;border-radius:20px;font-size:12px}.panel{background:white;border:1px solid #dce4ee;border-radius:18px;padding:26px;margin:0 0 24px;box-shadow:0 6px 24px #14243b05}.notice{background:#fff5de;border-left:4px solid #d89a20;padding:12px 16px;border-radius:6px;margin:14px 0;color:#684800}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}.stat{padding:14px 18px;background:#f5f8fd;border-radius:12px}.stat strong{font-size:28px;display:block}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left;font-size:14px}th{color:#536883;font-weight:600;white-space:nowrap;background:#f5f8fd}td,th{padding:12px 14px;border-bottom:1px solid #e6ecf3;vertical-align:top}td small{display:block;color:#536883;margin-top:5px;max-width:500px;overflow-wrap:anywhere}.status{font-size:12px;white-space:nowrap;color:#284e9c}.bad{color:#996511}.hash{font:11px/1.6 ui-monospace,monospace;overflow-wrap:anywhere;color:#62738a}details{margin-top:18px}summary{cursor:pointer;color:#365c94}svg{display:block;width:100%;height:auto;margin:12px 0;border-radius:12px;background:#f8fafc}.legend{display:flex;gap:24px;font-size:13px}.sma{color:#2f6bff}.hold{color:#b57717}.numbers{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}footer{padding:0 4px 24px;color:#526784;font-size:13px}@media(max-width:650px){main{padding:22px 14px}h1{font-size:26px}.panel{padding:18px 14px;border-radius:12px}.stats{gap:8px}.stat{padding:10px}.stat strong{font-size:23px}td,th{padding:10px}h2{font-size:20px}}"""
LABELS = {"SYNTHETIC": "合成测试数据 · 不是实际行情或已核实绩效",
          "UNVERIFIED_LOCAL": "本地输入 · 来源与历史可用性未核验"}
STATUSES = {"COMPLETED_UNVERIFIED": "已生成摘要 · 未核验", "MISSING_INPUT": "缺少输入",
            "FAILED_INPUT_VALIDATION": "输入校验失败"}
FINANCIAL_FIELDS = {"schema_version", "data_kind", "pdf_path", "symbol", "announcement_date", "pages", "annotations"}


def _text(value):
    return escape(str(value), quote=True)


def _money(value):
    return f"{value:,.2f}"


def _percent(value):
    return f"{value * 100:,.2f}%"


def _equity_chart(evaluation):
    """Numeric coordinates only; initial cash is an explicit pre-first-mark point."""
    runs = [evaluation["test"], evaluation["benchmark"]]
    series = [[run["initial_cash"]] + [mark["equity"] for mark in run["marks"]] for run in runs]
    low, high = min(min(values) for values in series), max(max(values) for values in series)
    spread = high - low or max(1, high * 0.01)
    plot_high = low + spread
    lines = []
    for values, color in zip(series, ("#2f6bff", "#b57717")):
        points = " ".join(f"{70 + index * 610 / (len(values) - 1):.2f},{210 - (value - low) * 175 / spread:.2f}"
                          for index, value in enumerate(values))
        lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"/>')
    first, last = runs[0]["marks"][0]["date"], runs[0]["marks"][-1]["date"]
    return ('<div class="legend"><span class="sma">━ SMA 测试账户</span><span class="hold">━ 买入持有基准</span></div>'
            '<svg viewBox="0 0 720 260" role="img" aria-label="测试区间假设权益比较，包含初始资金点">'
            '<title>测试区间的假设权益，按观察顺序等距排列</title>'
            '<line x1="70" y1="35" x2="680" y2="35" stroke="#dce4ee"/>'
            '<line x1="70" y1="210" x2="680" y2="210" stroke="#dce4ee"/>'
            f'<text x="8" y="39" font-size="11" fill="#526784">{_text(format(plot_high, ".4g"))}</text>'
            f'<text x="8" y="214" font-size="11" fill="#526784">{_text(format(low, ".4g"))}</text>'
            + "".join(lines) + '<text x="70" y="242" font-size="11" fill="#526784">初始资金</text>'
            f'<text x="680" y="242" text-anchor="end" font-size="11" fill="#526784">{_text(last)}</text></svg>'
            f'<p class="muted">测试区间 {_text(first)} 至 {_text(last)}；横轴按观察顺序等距，不代表完整交易日历。'
            '折线包含首日开盘前的初始资金点，后续为收盘标记权益。</p>')


def _batch_panel(config):
    artifact = build_pipeline(config)
    bundle = artifact["bundle"]
    rows = []
    for item in bundle["results"]:
        brief = item["brief"]
        detail = brief["research_stance"] if brief else "需要补齐输入或修正数据后重新生成。"
        report = config["reports"].get(item["symbol"])
        note = report.get("fixture_notice") if isinstance(report, dict) else None
        if isinstance(note, str) and note:
            detail += " 输入说明（调用方声明）：" + note[:800]
        status_class = "status" if brief else "status bad"
        rows.append(f'<tr><td>{_text(item["symbol"])}</td><td class="{status_class}">{_text(STATUSES[item["status"]])}'
                    f'<small>{_text(item["status"])}</small></td><td>{_text(detail)}</td></tr>')
    return (f'<section class="panel"><h2>批量研究任务</h2><p class="muted">研究截止日 {_text(bundle["analysis_date"])}'
            ' · 仅汇总本地历史数据，不生成选股排名。</p>'
            f'<div class="notice">{_text(LABELS[config["data_kind"]])}</div>'
            f'<div class="stats"><div class="stat">任务总数<strong>{bundle["job_count"]}</strong></div>'
            f'<div class="stat">生成摘要<strong>{bundle["succeeded_count"]}</strong></div>'
            f'<div class="stat">缺失或失败<strong>{bundle["failed_count"]}</strong></div></div>'
            '<div class="scroll"><table><thead><tr><th>股票代码</th><th>任务状态</th><th>研究边界与输入说明</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div><details><summary>查看输入与结果指纹</summary>'
            f'<p class="hash">配置 SHA-256：{artifact["pipeline_input_sha256"]}<br>'
            f'结果载荷 SHA-256：{artifact["artifact_payload_sha256"]}</p></details></section>')


def _evaluation_panel(config):
    artifact = build_evaluation_artifact(config)
    evaluation = artifact["evaluation"]
    rows = []
    for key, label in (("train", "训练区间 · 诊断"), ("test", "测试区间 · SMA"), ("benchmark", "测试区间 · 买入持有")):
        run, metrics = evaluation[key], evaluation["metrics"][key]
        fees = run["total_commission"] + run["total_sell_tax"]
        rows.append(f'<tr><td>{label}<small>{_text(metrics["start_date"])} 至 {_text(metrics["end_date"])}</small></td>'
                    f'<td class="numbers">{_money(run["final_marked_equity"])}</td>'
                    f'<td class="numbers">{_percent(metrics["observed_period_return"])}</td>'
                    f'<td class="numbers">{_percent(metrics["max_drawdown_fraction"])}</td>'
                    f'<td class="numbers">{_money(fees)}</td><td class="numbers">{len(run["fills"])}</td></tr>')
    settings = artifact["settings"]
    assumption_rows = "".join(f'<tr><th>{_text(label)}</th><td>{_text(settings[key])}</td></tr>' for key, label in (
        ("initial_cash", "独立账户初始资金（元）"), ("board_lot_size", "每手股数"),
        ("commission_bps", "佣金（基点）"), ("minimum_fee", "最低佣金（元）"),
        ("sell_tax_bps", "卖出税（基点）"), ("slippage_bps", "滑点（基点）"),
        ("evidence_as_of", "证据截止时刻"), ("expected_adjustment", "价格口径")))
    difference = evaluation["comparison"]["arithmetic_return_difference"] * 100
    return (f'<section class="panel"><h2>样本外纸面评估</h2><p class="muted">{_text(evaluation["symbol"])}'
            f' · 固定 SMA 窗口 {_text(evaluation["fixed_window"])} · 训练止于 {_text(evaluation["train_end"])}'
            f' · 测试始于 {_text(evaluation["test_start"])}</p>'
            f'<div class="notice">{_text(LABELS[config["data_kind"]])}。收益为假设计算，不代表可实现的盈利。</div>'
            '<div class="scroll"><table><thead><tr><th>账户与观察区间</th><th>期末权益（元）</th><th>区间收益</th>'
            f'<th>最大回撤</th><th>佣金与税（元）</th><th>成交次数</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'<p>SMA 测试收益 − 基准收益：<strong>{difference:,.2f} 个百分点</strong>。'
            '这是算术差值，不是相对收益率、年化收益或超额收益能力证明。</p><h3>测试账户权益比较</h3>'
            + _equity_chart(evaluation) + '<p class="muted">训练与测试账户资金独立；训练数据只用于预热。'
            '手续费已扣除，滑点已计入成交价；期末持仓按收盘价标记，不强制卖出。最大回撤包含初始资金峰值。</p>'
            f'<details><summary>查看实验假设与数据指纹</summary><div class="scroll"><table>{assumption_rows}</table></div>'
            f'<p>版本元数据（未认证）：{_text(config["snapshot"]["akshare_version"])}</p>'
            f'<p class="hash">配置 SHA-256：{artifact["config_input_sha256"]}<br>'
            f'结果载荷 SHA-256：{artifact["artifact_payload_sha256"]}</p></details></section>')


def _validate_financial_config(config):
    _canonical_json_bytes(config)
    if type(config) is not dict or set(config) != FINANCIAL_FIELDS:
        raise ValueError("financial config requires exact explicit fields")
    if (config["schema_version"] != "0.1" or type(config["data_kind"]) is not str
            or config["data_kind"] not in LABELS):
        raise ValueError("unsupported financial config version or data_kind")
    path = config["pdf_path"]
    if type(path) is not str or not path.strip() or len(path) > 4096 or "\x00" in path:
        raise ValueError("financial pdf_path must be an explicit bounded path")
    if (type(config["pages"]) is not list or not 1 <= len(config["pages"]) <= 20
            or any(type(page) is not int or not 1 <= page <= 10000 for page in config["pages"])
            or len(set(config["pages"])) != len(config["pages"])):
        raise ValueError("invalid financial pages")
    if config["annotations"] is not None and type(config["annotations"]) is not dict:
        raise ValueError("financial annotations must be an object or null")


def _financial_panel(config, max_rows):
    _validate_financial_config(config)
    artifact = build_financial_review_artifact(
        config["pdf_path"], config["symbol"], config["announcement_date"], config["pages"],
        annotations=config["annotations"], max_rows=max_rows)
    package, review, validation = artifact["package"], artifact["review_record"], artifact["validation"]
    rows = []
    for index, candidate in enumerate(package["candidates"][:max_rows]):
        cell, decision = candidate["cell"], review["decisions"][index]
        position = "/".join(str(cell[key]) for key in ("page", "table_index", "row_index", "column_index"))
        status = {"pending_manual_review": "待记录复核决定", "accepted_by_reviewer": "调用方记录接受",
                  "rejected_by_reviewer": "调用方记录拒绝"}[decision["decision"]]
        note = ""
        if decision.get("reviewer"):
            note = f'<small>审核人声明：{_text(decision["reviewer"])}；备注：{_text(decision["note"])}</small>'
        hints = [candidate[key + "_hint_unverified"] for key in ("metric", "unit", "period")]
        hint_cells = "".join(f'<td>{_text(value if value is not None else "未知")}</td>' for value in hints)
        rows.append(f'<tr><td>{index}</td><td>{_text(cell["text"])}</td><td>{_text(position)}</td>'
                    + hint_cells + '<td>未知 · 未核实</td>'
                    f'<td>{_text(", ".join(candidate["review_blockers"]))}</td><td>{_text(status)}'
                    f'<small>{_text(decision["decision"])}</small>{note}</td></tr>')
    omitted = package["candidate_count"] - len(rows)
    no_numeric = ('<p class="notice">未提取到数值候选：no_numeric_candidates。暂无可复核数值证据，'
                  '不代表报表没有财务数据或复核已经完成。</p>') if not package["candidate_count"] else ""
    return (f'<section class="panel"><h2>财报证据复核</h2><p class="muted">{_text(package["symbol"])}'
            f' · 公告日期（调用方声明）{_text(package["announcement_date_supplied_unverified"])}</p>'
            f'<div class="notice">{_text(LABELS[config["data_kind"]])}。仅供查看原始 PDF 与表格证据；'
            '结构校验通过不代表数值、来源、期间或合并口径已核实。</div>'
            f'<div class="stats"><div class="stat">数值候选<strong>{package["candidate_count"]}</strong></div>'
            f'<div class="stat">待记录决定<strong>{review["pending_count"]}</strong></div>'
            f'<div class="stat">已记录决定<strong>{review["decided_count"]}</strong></div></div>'
            + no_numeric + '<p>合并口径始终未知；原始阻断项全部保留。审核人身份未经认证，接受记录不构成核验或发布授权。</p>'
            f'<p class="muted">结构状态：{_text("通过（仅结构）" if validation["structure_valid"] else "未通过")}；'
            f'财务核验：未完成；发布证据接受：否。包级阻断项：{_text(", ".join(package["review_blockers"]))}。</p>'
            '<div class="scroll"><table><thead><tr><th>候选</th><th>原始数值</th><th>页/表/行/列</th>'
            '<th>指标提示</th><th>单位提示</th><th>期间提示</th><th>合并口径</th><th>阻断项</th><th>复核记录</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'<p class="muted">显示 {len(rows)} 项，省略 {omitted} 项；总数与待记录数量包含所有候选。'
            '页码从 1 开始，表/行/列从 0 开始。</p>'
            f'<details><summary>查看 PDF 与复核包指纹</summary><p class="hash">PDF SHA-256：{package["file_sha256"]}'
            f'<br>复核包 SHA-256：{validation["package_sha256"]}</p></details></section>')


def build_dashboard(*, batch_config=None, evaluation_config=None, financial_config=None, max_financial_rows=20):
    """Accept raw configs only, rebuilding all selected sections with existing validators."""
    if batch_config is None and evaluation_config is None and financial_config is None:
        raise ValueError("at least one raw batch, evaluation or financial config is required")
    if type(max_financial_rows) is not int or not 1 <= max_financial_rows <= 500:
        raise ValueError("max_financial_rows must be from 1 to 500")
    sections = []
    if batch_config is not None:
        sections.append(_batch_panel(batch_config))
    if evaluation_config is not None:
        sections.append(_evaluation_panel(evaluation_config))
    if financial_config is not None:
        sections.append(_financial_panel(financial_config, max_financial_rows))
    style_hash = base64.b64encode(hashlib.sha256(CSS.encode()).digest()).decode("ascii")
    policy = (f"default-src 'none'; style-src 'sha256-{style_hash}'; script-src 'none'; "
              "object-src 'none'; base-uri 'none'; form-action 'none'; font-src 'none'; connect-src 'none'")
    html = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{_text(policy)}">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>股票辅脑 · 离线研究面板</title>'
            f'<style>{CSS}</style></head><body><main><header><div class="eyebrow">股票辅脑 / RESEARCH WORKSPACE</div>'
            '<h1>研究任务、评估与财报复核</h1><span class="pill">本地只读 · 无网络请求</span>'
            '<p class="muted">从原始配置重新校验与计算；展示历史研究材料和实验性纸面结果。</p></header>'
            + "".join(sections) + '<footer><strong>核验边界：</strong>来源、历史时点与绩效均未核验。'
            '未建模交易日历缺口、公司行动、涨跌停、停牌、流动性或真实成交约束。'
            '本页不连接实盘，不构成投资建议。图表不代表收益承诺。</footer></main></body></html>\n')
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("dashboard HTML exceeds limit")
    return html


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-config")
    parser.add_argument("--evaluation-config")
    parser.add_argument("--financial-config")
    parser.add_argument("--max-financial-rows", type=int, default=20)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if not args.batch_config and not args.evaluation_config and not args.financial_config:
        parser.error("at least one section config is required")
    sources = [Path(value) for value in (args.batch_config, args.evaluation_config, args.financial_config) if value]
    output = Path(args.output)
    if output.is_symlink() or any(output.resolve() == source.resolve()
            or (output.exists() and os.path.samefile(source, output)) for source in sources):
        raise ValueError("dashboard cannot overwrite an input or target a symbolic link")
    batch = _load_config(args.batch_config) if args.batch_config else None
    evaluation = _load_config(args.evaluation_config) if args.evaluation_config else None
    for selected, config in ((args.batch_config, batch), (args.evaluation_config, evaluation)):
        if selected and type(config) is not dict:
            raise ValueError("selected section config must be an object, not null")
    financial = _load_config(args.financial_config) if args.financial_config else None
    if args.financial_config:
        _validate_financial_config(financial)
        pdf = Path(financial["pdf_path"])
        if not pdf.is_absolute():
            pdf = Path(args.financial_config).resolve().parent / pdf
        financial = {**financial, "pdf_path": str(pdf)}
        if output.resolve() == pdf.resolve() or (output.exists() and os.path.samefile(pdf, output)):
            raise ValueError("dashboard cannot overwrite its financial PDF")
    html = build_dashboard(batch_config=batch, evaluation_config=evaluation,
                           financial_config=financial, max_financial_rows=args.max_financial_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(html)
        if output.is_symlink():
            raise ValueError("dashboard output became a symbolic link")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
