"""Deterministic specialist routing for financial code review.

Roles provide independent review checklists, not separate model calls. The caller
may later dispatch them to isolated agents; this module is offline and advisory.
"""
MAX_FILES = 200
ROLE_CHECKS = {
    "market_data": (
        "Identify the authoritative source, instrument identifiers, retrieval timestamp and source publication timestamp.",
        "Check trading calendar, timezone, stale quotes, suspensions, duplicates, missing bars and outliers.",
        "Check corporate actions, adjusted versus raw prices, currency and unit consistency.",
        "Verify that historical decisions use only data available at that decision timestamp.",
    ),
    "fundamental": (
        "Verify filing period, publication timestamp, restatements and point-in-time availability.",
        "Check currency, scale, accounting units, consolidated versus parent scope and TTM versus fiscal-year definitions.",
        "Recompute ratios from cited source values and state denominator/negative-earnings edge cases.",
        "Separate reported facts, derived metrics, assumptions and forward estimates.",
    ),
    "technical_indicators": (
        "Verify each indicator formula, initialization, warm-up period, window alignment and missing-data behavior.",
        "Compare calculations against an independent deterministic reference implementation and known fixtures.",
        "Check adjusted-price convention and ensure signals are not shifted using future observations.",
        "State parameter choices and avoid treating an indicator signal as a guaranteed forecast.",
    ),
    "quant_backtest": (
        "Check point-in-time universe membership, delisted securities and survivorship bias.",
        "Check look-ahead leakage, train/test separation, walk-forward design and parameter selection leakage.",
        "Include commissions, taxes, spread, slippage, liquidity limits and realistic execution timing.",
        "Verify reproducibility: data snapshot, code revision, parameters, random seed and benchmark.",
    ),
    "risk": (
        "Check exposure, concentration, leverage, liquidity, drawdown and volatility definitions.",
        "Verify risk metrics' sampling frequency, lookback, annualization and benchmark.",
        "Test missing data, extreme observations, market gaps and stressed scenarios.",
        "Do not convert model confidence into a probability of profit or a guaranteed loss limit.",
    ),
}
FINANCE_FALLBACK_MARKERS = ("financial", "finance", "market", "行情", "财务", "投资", "估值")
ROLE_PATHS = {
    "market_data": ("market_data", "quote", "行情", "price_feed"),
    "fundamental": ("fundamental", "financial_statement", "财务", "balance_sheet", "income_statement"),
    "technical_indicators": ("indicator", "technical", "指标", "macd", "rsi"),
    "quant_backtest": ("backtest", "factor", "qlib", "回测", "因子"),
    "risk": ("risk", "portfolio", "position", "drawdown", "风控", "仓位"),
}


def build_specialist_assignments(financial_files):
    if not isinstance(financial_files, list) or len(financial_files) > MAX_FILES:
        raise ValueError("invalid financial file list")
    if any(not isinstance(path, str) or not path or len(path) > 500 for path in financial_files):
        raise ValueError("invalid financial file path")
    if len(set(financial_files)) != len(financial_files):
        raise ValueError("duplicate financial file path")
    if not financial_files or not any(
        marker in path.lower()
        for path in financial_files
        for marker in FINANCE_FALLBACK_MARKERS
    ):
        return []

    matched_by_role = {
        role: [
            path for path in financial_files
            if any(marker in path.lower() for marker in markers)
        ]
        for role, markers in ROLE_PATHS.items()
    }
    covered = {path for paths in matched_by_role.values() for path in paths}
    unmatched = [path for path in financial_files if path not in covered]

    assignments = []
    for role, markers in ROLE_PATHS.items():
        # Always dispatch all five specialist roles for a financial review.
        # If a role has no direct filename match, it receives the complete
        # financial scope and applies its own checklist as an independent lens.
        matched = matched_by_role[role] or list(financial_files)
        if role == "risk" and unmatched:
            matched = list(dict.fromkeys(matched + unmatched))
        assignments.append({
            "role": role,
            "files": matched,
            "checks": list(ROLE_CHECKS[role]),
            "output_requirements": [
                "verdict: approve, request_changes or uncertain",
                "cite exact file and changed-line evidence",
                "separate fact, inference and missing evidence",
                "include validation method and confidence rationale",
            ],
        })
    return assignments
