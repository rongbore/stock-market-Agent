"""Deterministic finance-domain preflight for AI-assisted PR review.

This module identifies financial-risk surfaces and emits review prompts/evidence.
It does not validate strategy profitability, provide investment advice, or authorize merges.
"""
import re
from pathlib import PurePosixPath

MAX_FILES = 200
MAX_DIFF_CHARS = 500_000

_FINANCE_PATH = re.compile(
    r"(market|finance|financial|fundamental|technical|indicator|"
    r"backtest|portfolio|position|risk|pricing|valuation|"
    r"quote|行情|财务|指标|回测|投资|估值|风控)",
    re.IGNORECASE,
)
_CORE_PATH = re.compile(
    r"(backtest|portfolio|position|risk|execution|order|"
    r"pricing|valuation|indicator|adjust|corporate_action|"
    r"行情|回测|仓位|交易|复权|估值|风控)",
    re.IGNORECASE,
)
_RULES = (
    ("future_data_access", re.compile(r"\b(shift\s*\(\s*-\d+|\.iloc\s*\[\s*[-]?[0-9]+\s*:\s*\]|"
                                      r"merge_asof\s*\()", re.IGNORECASE),
     "检查是否使用了决策时点之后才可获得的数据；核对公告发布时间、交易日和可用时间。"),
    ("silent_missing_value_fill", re.compile(r"\b(fillna\s*\(\s*0\s*\)|nan_to_num\s*\([^)]*\))", re.IGNORECASE),
     "检查缺失行情/财务值是否被静默替换为零；确认零值有业务含义且有来源依据。"),
    ("unadjusted_price_mix", re.compile(r"(qfq|hfq|复权|adjust).{0,100}(close|收盘)|"
                                        r"(close|收盘).{0,100}(qfq|hfq|复权|adjust)", re.IGNORECASE),
     "检查前复权、后复权和未复权价格是否混用；确认指标、收益率和基准使用一致口径。"),
    ("lookahead_or_survivorship_backtest", re.compile(r"(look.?ahead|survivorship|未来函数|幸存者偏差)", re.IGNORECASE),
     "检查回测是否存在未来函数、幸存者偏差、成分股历史偏差及数据修订泄漏。"),
    ("unbounded_position_or_leverage", re.compile(r"(leverage|杠杆|position_size|仓位).{0,100}(?:unbounded|无限|all.?in|满仓)", re.IGNORECASE),
     "检查仓位、杠杆、单标的集中度、流动性和最大回撤约束是否明确。"),
)
_SENSITIVE = re.compile(r"(\.github/workflows/|secrets?|token|credential|auth|permission|"
                        r"broker|券商|交易接口|order|execution)", re.IGNORECASE)


def _safe_path(path):
    if not isinstance(path, str) or not path or len(path) > 500:
        raise ValueError("invalid changed file path")
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or "\\" in path:
        raise ValueError("unsafe changed file path")
    return path


def assess_financial_pr(changed_files, diffs=None):
    """Return deterministic finance scope, risk tier, and bounded review checks."""
    if not isinstance(changed_files, list) or len(changed_files) > MAX_FILES:
        raise ValueError("changed files must be a bounded list")
    if diffs is None:
        diffs = {}
    if not isinstance(diffs, dict):
        raise ValueError("diffs must be an object keyed by path")
    paths = [_safe_path(p) for p in changed_files]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate changed file path")
    unknown_diff_paths = set(diffs) - set(paths)
    if unknown_diff_paths:
        raise ValueError("diff contains an unlisted file")
    financial = [p for p in paths if _FINANCE_PATH.search(p)]
    core = [p for p in financial if _CORE_PATH.search(p)]
    sensitive = [p for p in paths if _SENSITIVE.search(p)]
    findings = []
    for path, diff in diffs.items():
        if not isinstance(diff, str) or len(diff) > MAX_DIFF_CHARS:
            raise ValueError("invalid or oversized diff")
        for code, pattern, guidance in _RULES:
            if pattern.search(diff):
                findings.append({"code": code, "file": path, "severity": "review_required",
                                 "guidance": guidance})
    if sensitive:
        tier = "restricted_security_review"
    elif core:
        tier = "core_financial_logic_review"
    elif financial:
        tier = "financial_domain_review"
    else:
        tier = "general_review"
    checks = [
        "行情/财务数据来源、抓取时间、发布时间及历史可得时间是否可追溯",
        "缺失值、重复值、异常值、停牌和交易日历是否显式处理",
        "币种、单位、复权方式、财报期间及同比/环比口径是否一致",
        "指标公式、窗口边界、精度及样本不足时的降级行为是否有测试",
        "回测是否避免未来函数、幸存者偏差、前视偏差及交易成本遗漏",
        "风险指标是否明确样本区间、计算口径、极端行情和失败边界",
        "输出是否区分事实、推断、不确定性，且不承诺收益或确定性目标价",
    ] if financial else []
    if core:
        checks.extend([
            "核心金融逻辑是否有独立基准样例、边界测试和可复现结果",
            "任何交易/券商接口、副作用或凭据权限变化是否经过单独安全审查",
        ])
    return {
        "schema_version": "1.0",
        "scope": tier,
        "financial_files": financial,
        "core_financial_files": core,
        "sensitive_files": sensitive,
        "findings": findings,
        "required_review_checks": checks,
        "merge_authorized": False,
        "ai_review_is_advisory": True,
    }
