"""Validate independently supplied research evidence before writing a bundle.

This is an offline contract. It never fetches sources and never marks
upstream market data as verified merely because metadata is well-formed.
"""
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

if __package__:
    from .source_records import validate_source_record
else:
    from source_records import validate_source_record


def validate_evidence_bundle(records, *, analysis_date, cutoff=None):
    """Validate provenance metadata and reject duplicate evidence identifiers.

    Default historical cutoff is end-of-day Asia/Shanghai (UTC+08:00).
    A stricter intraday cutoff can be supplied as an ISO-8601 timestamp.
    """
    if not isinstance(records, list):
        raise ValueError("evidence records must be a list")
    if not isinstance(analysis_date, str):
        raise ValueError("analysis_date must be YYYY-MM-DD")
    try:
        day = date.fromisoformat(analysis_date)
    except ValueError as exc:
        raise ValueError("analysis_date must be YYYY-MM-DD") from exc
    if day.isoformat() != analysis_date:
        raise ValueError("analysis_date must be YYYY-MM-DD")
    day_end = datetime.combine(day + timedelta(days=1), time.min,
                               tzinfo=timezone(timedelta(hours=8))) - timedelta(microseconds=1)
    if cutoff is None:
        cutoff_dt = day_end
        cutoff = cutoff_dt.isoformat()
    else:
        if not isinstance(cutoff, str):
            raise ValueError("cutoff must be an ISO-8601 timestamp")
        try:
            cutoff_dt = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("cutoff must be an ISO-8601 timestamp") from exc
        if cutoff_dt.tzinfo is None or cutoff_dt.utcoffset() is None:
            raise ValueError("cutoff requires timezone")
        if cutoff_dt > day_end:
            raise ValueError("cutoff cannot exceed the analysis date")
    seen = set()
    for record in records:
        validate_source_record(record, analysis_cutoff=cutoff)
        identifier = (record["kind"], record["symbol"], record["url"], record["published_at"])
        if identifier in seen:
            raise ValueError("duplicate evidence record")
        seen.add(identifier)
    return {
        "schema_version": "0.1",
        "analysis_date": day.isoformat(),
        "analysis_cutoff": cutoff,
        "records": records,
        "metadata_validated": True,
        "source_content_verified": False,
        "historical_point_in_time_verified": False,
        "limitations": [
            "Metadata validation does not verify the source content or its authenticity.",
            "Retrieval after the analysis date does not prove historical availability.",
        ],
    }


def save_evidence_bundle(directory, bundle):
    """Write a separately labeled JSON evidence metadata bundle."""
    path = Path(directory) / "evidence_bundle.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path
