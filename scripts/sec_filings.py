"""Normalize SEC submissions filing metadata into auditable source records.

Input must come from SEC's official data.sec.gov submissions JSON; this module
does not fetch or authenticate it. US filings only, not A-share/HK filings.
"""
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo


def filing_records(submissions, *, retrieved_at, cutoff=None):
    """Return filing records for the SEC `filings.recent` parallel arrays.

    `acceptanceDateTime` is SEC's US Eastern local timestamp. Treat it as
    the earliest documented availability time; never use filingDate alone
    to decide whether a historical analysis could have seen the filing.
    """
    if not isinstance(submissions, dict):
        raise ValueError("submissions must be a mapping")
    cik = submissions.get("cik")
    if not isinstance(cik, int) or cik <= 0:
        raise ValueError("SEC submissions require positive integer cik")
    recent = submissions.get("filings", {}).get("recent", {})
    keys = ("accessionNumber", "primaryDocument", "form", "acceptanceDateTime")
    if not isinstance(recent, dict) or any(not isinstance(recent.get(k), list) for k in keys):
        raise ValueError("missing SEC filings.recent arrays")
    length = len(recent["accessionNumber"])
    if any(len(recent[k]) != length for k in keys):
        raise ValueError("SEC filings.recent arrays have mismatched lengths")
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    if cutoff is not None and (cutoff.tzinfo is None or cutoff.utcoffset() is None):
        raise ValueError("cutoff must be timezone-aware")
    eastern = ZoneInfo("America/New_York")
    output = []
    for i in range(length):
        accession = recent["accessionNumber"][i]
        document = recent["primaryDocument"][i]
        form = recent["form"][i]
        accepted = recent["acceptanceDateTime"][i]
        if not all(isinstance(v, str) and v.strip() for v in (accession, document, form, accepted)):
            raise ValueError("incomplete SEC filing entry")
        if not accession.replace("-", "").isdigit() or "/" in document or "\\" in document or document in (".", ".."):
            raise ValueError("invalid SEC accession or document path")
        try:
            accepted_dt = datetime.fromisoformat(accepted)
        except ValueError as exc:
            raise ValueError("invalid SEC acceptanceDateTime") from exc
        if accepted_dt.tzinfo is not None:
            raise ValueError("SEC acceptanceDateTime must be local Eastern time")
        published = accepted_dt.replace(tzinfo=eastern).astimezone(timezone.utc)
        if published > retrieved_at.astimezone(timezone.utc):
            raise ValueError("filing acceptance time is after retrieval")
        if cutoff is not None and published > cutoff.astimezone(timezone.utc):
            continue
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/"
            f"{accession.replace('-', '')}/{quote(document, safe='')}"
        )
        output.append({
            "kind": "filing",
            "provider": "SEC EDGAR",
            "symbol": f"CIK:{cik:010d}",
            "url": url,
            "published_at": published.isoformat(),
            "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat(),
            "form": form,
            "accession_number": accession,
        })
    return output
