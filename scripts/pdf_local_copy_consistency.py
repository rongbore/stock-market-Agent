"""Compare two locally supplied PDF copies without claiming official provenance."""
import argparse
import hashlib
import json
from pathlib import Path

MAX_FILE_BYTES = 100 * 1024 * 1024


def _hash_pdf(path):
    file = Path(path)
    if not file.is_file():
        raise ValueError("PDF file not found")
    size = file.stat().st_size
    if size < 8 or size > MAX_FILE_BYTES:
        raise ValueError("PDF file size out of range")
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("invalid PDF header")
        stream.seek(0)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if file.stat().st_size != size:
        raise ValueError("PDF changed during hashing")
    return {"sha256": digest.hexdigest(), "size_bytes": size}


def compare_local_pdf_copies(first, second):
    """Hash two local PDFs; equality alone cannot establish official origin."""
    a = _hash_pdf(first)
    b = _hash_pdf(second)
    return {
        "first": a,
        "second": b,
        "byte_identical_by_sha256": a["sha256"] == b["sha256"]
        and a["size_bytes"] == b["size_bytes"],
        "official_origin_verified": False,
        "financial_meaning_verified": False,
        "warning": "Matching local copies do not prove that either copy came from an official disclosure website.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", required=True)
    parser.add_argument("--second", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    target = Path(args.output)
    if target.resolve() in (Path(args.first).resolve(), Path(args.second).resolve()):
        raise ValueError("output cannot overwrite PDF input")
    result = compare_local_pdf_copies(args.first, args.second)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
