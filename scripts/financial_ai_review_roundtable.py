"""Bounded multi-agent roundtable and moderator synthesis for finance reviews.

Each specialist sees the independent findings and prior discussion, then responds
in a fixed round-robin order. A final moderator call synthesizes the record.
All model output remains untrusted; deterministic safeguards preserve dissent
and prevent the moderator from overriding high-severity findings.
"""
import json

from scripts.financial_ai_review_roles import build_specialist_assignments

MAX_ROUNDS = 2
MAX_HISTORY_ITEMS = 20
MAX_TRANSCRIPT_CHARS = 18_000
VERDICTS = {"approve", "request_changes", "uncertain"}
SEVERITIES = {"low", "medium", "high", "critical"}


def _validate_response(response, allowed_files):
    if not isinstance(response, dict) or set(response) != {"verdict", "summary", "findings"}:
        raise ValueError("invalid roundtable response")
    if response["verdict"] not in VERDICTS:
        raise ValueError("invalid roundtable verdict")
    if not isinstance(response["summary"], str) or not response["summary"].strip() or len(response["summary"]) > 3000:
        raise ValueError("invalid roundtable summary")
    findings = response["findings"]
    if not isinstance(findings, list) or len(findings) > 30:
        raise ValueError("invalid roundtable findings")
    clean = []
    for item in findings:
        if not isinstance(item, dict) or set(item) != {"severity", "path", "explanation"}:
            raise ValueError("invalid roundtable finding")
        if item["severity"] not in SEVERITIES or item["path"] not in allowed_files:
            raise ValueError("invalid roundtable finding reference")
        if not isinstance(item["explanation"], str) or not item["explanation"].strip() or len(item["explanation"]) > 2000:
            raise ValueError("invalid roundtable finding explanation")
        clean.append(dict(item))
    return {"verdict": response["verdict"], "summary": response["summary"],
            "findings": clean}


def run_financial_roundtable(*, financial_files, diff_by_file, independent_reviews,
                             reviewer, rounds=2):
    assignments = build_specialist_assignments(financial_files)
    if not 1 <= rounds <= MAX_ROUNDS:
        raise ValueError("round count out of range")
    if not callable(reviewer):
        raise ValueError("reviewer must be callable")
    if not isinstance(independent_reviews, list) or len(independent_reviews) != len(assignments):
        raise ValueError("independent reviews do not match specialist assignments")
    if not isinstance(diff_by_file, dict) or set(diff_by_file) - set(financial_files):
        raise ValueError("invalid roundtable diff map")
    allowed_files = {path for item in assignments for path in item["files"]}
    positions = {}
    for assignment, review in zip(assignments, independent_reviews):
        if not isinstance(review, dict) or review.get("role") != assignment["role"]:
            raise ValueError("independent review role mismatch")
        positions[assignment["role"]] = _validate_response({
            "verdict": review.get("verdict"), "summary": review.get("summary"),
            "findings": review.get("findings"),
        }, set(assignment["files"]))
    history = []
    for round_number in range(1, rounds + 1):
        for assignment in assignments:
            role = assignment["role"]
            role_files = assignment["files"]
            task = {
                "role": role,
                "files": role_files,
                "checks": assignment["checks"],
                "output_requirements": assignment["output_requirements"] + [
                    "Discuss peers' evidence respectfully; identify agreement and disagreement.",
                    "Do not accept a claim without concrete changed-file evidence.",
                    "You may retain or revise your verdict, but explain why.",
                    "Preserve unresolved disagreement and missing evidence.",
                ],
                "diff_by_file": {path: diff_by_file.get(path, "") for path in role_files},
                "discussion_phase": "peer_discussion",
                "discussion_round": round_number,
                "discussion_history": history[-MAX_HISTORY_ITEMS:],
                "initial_reviews": independent_reviews,
                "current_position": positions[role],
                "merge_authorized": False,
            }
            if len(json.dumps(task, ensure_ascii=False)) > MAX_TRANSCRIPT_CHARS:
                raise ValueError("roundtable context too large")
            response = _validate_response(reviewer(task), set(role_files))
            positions[role] = response
            history.append({"round": round_number, "role": role, **response})
            if len(history) > MAX_HISTORY_ITEMS:
                raise ValueError("roundtable history limit exceeded")

    moderator_files = sorted(allowed_files)
    moderator_task = {
        "role": "moderator",
        "files": moderator_files,
        "checks": [
            "Synthesize only claims supported by specialist findings and changed-file evidence.",
            "List agreements, disagreements, unresolved questions and evidence gaps.",
            "Do not erase minority concerns or treat consensus as proof.",
            "Do not override any high or critical finding.",
            "Return one concise unified verdict, summary and findings.",
        ],
        "output_requirements": [
            "Return verdict, summary and findings in the required JSON schema.",
            "Include material dissent and uncertainty in the summary.",
            "Do not claim independent facts not present in the review record.",
        ],
        "diff_by_file": {path: diff_by_file.get(path, "") for path in moderator_files},
        "discussion_phase": "moderator_synthesis",
        "discussion_round": rounds,
        "discussion_history": history[-MAX_HISTORY_ITEMS:],
        "initial_reviews": independent_reviews,
        "current_position": None,
        "moderator_instruction": "Produce the unified conclusion. Preserve dissent and explain unresolved disagreements.",
        "merge_authorized": False,
    }
    if len(json.dumps(moderator_task, ensure_ascii=False)) > MAX_TRANSCRIPT_CHARS:
        raise ValueError("moderator context too large")
    moderator = _validate_response(reviewer(moderator_task), set(moderator_files))
    all_reviews = list(positions.values())
    # Preserve concerns from every stage: a later model cannot erase an earlier finding.
    all_findings = [
        finding
        for item in independent_reviews
        for finding in item["findings"]
    ]
    all_findings += [
        finding
        for item in history
        for finding in item["findings"]
    ]
    all_findings += [finding for item in all_reviews for finding in item["findings"]]
    all_findings += moderator["findings"]

    initial_verdicts = [item["verdict"] for item in independent_reviews]
    final_verdicts = [item["verdict"] for item in all_reviews]
    all_verdicts = initial_verdicts + final_verdicts + [moderator["verdict"]]

    if any(f["severity"] in ("high", "critical") for f in all_findings):
        safe_verdict = "request_changes"
    elif "request_changes" in all_verdicts:
        safe_verdict = "request_changes"
    elif "uncertain" in all_verdicts or len(set(all_verdicts)) > 1:
        safe_verdict = "uncertain"
    else:
        safe_verdict = moderator["verdict"]
    return {
        "independent_reviews": independent_reviews,
        "discussion_rounds": rounds,
        "discussion_transcript": history,
        "specialist_final_positions": [
            {"role": role, **position} for role, position in positions.items()
        ],
        "moderator_synthesis": moderator,
        "overall_verdict": safe_verdict,
        "dissent_preserved": len(set(all_verdicts)) > 1 or any(
            item["verdict"] != moderator["verdict"]
            for item in independent_reviews + all_reviews
        ),
        "unresolved_disagreement": len(set(all_verdicts)) > 1,
        "merge_authorized": False,
        "review_advisory_only": True,
    }
