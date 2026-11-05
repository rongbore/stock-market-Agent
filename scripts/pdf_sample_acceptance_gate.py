"""Conservative acceptance gate for an offline PDF sample bundle and human review."""
import argparse
import json
from pathlib import Path

MAX_JSON_BYTES = 1024 * 1024


def _read(path):
    file = Path(path)
    if not file.is_file() or file.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("missing or oversized JSON")
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def assess_sample(bundle, review):
    """Classify evidence completeness; never infer authenticity from a local file."""
    if not isinstance(bundle, dict) or not isinstance(review, dict):
        raise ValueError("bundle and review must be objects")
    source = bundle.get("source_record")
    manifest = bundle.get("review_manifest")
    if not isinstance(source, dict) or not isinstance(manifest, dict):
        raise ValueError("invalid sample bundle")
    # A matching hash is not enough when the evidence labels disagree.
    # Keep the source claim and the review manifest bound to one filing identity.
    symbol = source.get("symbol")
    claimed_date = source.get("announcement_date_claimed")
    if (not isinstance(symbol, str) or not symbol or
            not isinstance(claimed_date, str) or not claimed_date or
            manifest.get("symbol") != symbol or
            manifest.get("announcement_date_claimed") != claimed_date):
        raise ValueError("source and manifest filing identity mismatch")
    if (source.get("source_file_match_verified") is not False or
            source.get("official_origin_verified") is not False or
            source.get("financial_meaning_verified") is not False or
            manifest.get("official_origin_verified") is not False or
            manifest.get("financial_meaning_verified") is not False):
        raise ValueError("unexpected verified source or manifest claim")
    hashes = (source.get("file_sha256"), manifest.get("file_sha256"),
              review.get("file_sha256"))
    if (any(not isinstance(x, str) or len(x) != 64 or
            any(c not in "0123456789abcdef" for c in x) for x in hashes)
            or len(set(hashes)) != 1):
        raise ValueError("evidence fingerprint mismatch")
    candidates = manifest.get("candidates")
    decisions = review.get("review_decisions")
    if not isinstance(candidates, list) or not isinstance(decisions, list):
        raise ValueError("invalid candidate review records")
    if type(manifest.get("candidate_count")) is not int or manifest["candidate_count"] != len(candidates):
        raise ValueError("candidate count mismatch")
    if len(candidates) > 100 or len(decisions) > 100:
        raise ValueError("too many candidates")
    seen = set()
    for item in decisions:
        if not isinstance(item, dict):
            raise ValueError("invalid review entry")
        i = item.get("candidate_index")
        if type(i) is not int or not 0 <= i < len(candidates) or i in seen:
            raise ValueError("invalid or duplicate review index")
        candidate = candidates[i]
        if (item.get("page") != candidate.get("page") or
                item.get("bbox") != candidate.get("bbox") or
                item.get("review_status") not in (
                    "pending_manual_review", "accepted_by_reviewer", "rejected_by_reviewer")):
            raise ValueError("review does not match candidate")
        seen.add(i)
    computed_complete = bool(candidates) and len(seen) == len(candidates) and all(
        item["review_status"] != "pending_manual_review" for item in decisions)
    if review.get("review_complete") is not computed_complete:
        raise ValueError("review completion flag inconsistent")
    if (bundle.get("official_origin_verified") is not False or
            bundle.get("financial_meaning_verified") is not False or
            review.get("official_origin_verified") is not False or
            review.get("financial_meaning_verified") is not False):
        raise ValueError("unexpected verified provenance or financial claim")
    blockers = []
    if bundle.get("sample_checked_with_real_pdf_parser") is not True:
        blockers.append("real_pdf_parser_not_confirmed")
    if not candidates:
        blockers.append("no_rectangle_candidates")
    if not computed_complete:
        blockers.append("manual_review_incomplete")
    blockers.extend(("official_source_not_verified", "financial_meaning_not_verified"))
    return {
        "file_sha256": hashes[0],
        "candidate_count": len(candidates),
        "review_complete": computed_complete,
        "offline_review_ready": not any(x in blockers for x in (
            "real_pdf_parser_not_confirmed", "no_rectangle_candidates",
            "manual_review_incomplete")),
        "release_evidence_accepted": False,
        "blockers": blockers,
        "note": "A completed geometry review does not verify official origin or financial figures.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    target = Path(args.output)
    if target.resolve() in (Path(args.bundle).resolve(), Path(args.review).resolve()):
        raise ValueError("output cannot overwrite evidence inputs")
    report = assess_sample(_read(args.bundle), _read(args.review))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
