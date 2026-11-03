"""Create an honest, non-sensitive provenance manifest for each analysis run.

This manifest records run-level metadata, NOT verified market-data provenance.
Upstream per-datum citations and publication timestamps are not yet collected.
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def build_manifest(ticker, analysis_date, model, *, generated_at=None, run_id=None):
    """Return serializable metadata without credentials or private holdings."""
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return {
        "schema_version": "0.1",
        "ticker": ticker,
        "analysis_date": analysis_date,
        "generated_at_utc": timestamp.astimezone(timezone.utc).isoformat(),
        "model_id": model,
        "github_run_id": str(run_id) if run_id else None,
        "market_data_sources_verified": False,
        "source_records": [],
        "limitations": [
            "Upstream market-data URLs and publication timestamps have not been verified.",
            "Historical point-in-time correctness has not been established.",
            "This metadata is not a recommendation to trade.",
        ],
    }


def save_manifest(report_dir, manifest):
    path = Path(report_dir) / "run_provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
