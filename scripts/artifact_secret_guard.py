"""Pre-upload safety checks for generated report artifacts.

Exact-match checking for configured secrets is defense-in-depth, not a
replacement for upstream secret handling or a comprehensive DLP scanner.
"""
import os
from pathlib import Path

TEXT_SUFFIXES = {".html", ".htm", ".md", ".txt", ".json", ".csv", ".xml"}
MAX_TEXT_FILE_BYTES = 20 * 1024 * 1024


def validate_artifact_secrets(root, *, secrets=None):
    """Return generic errors without ever printing or storing secret values."""
    root = Path(root)
    if not root.is_dir():
        return ["report artifact directory is missing"]
    if secrets is None:
        secrets = [os.environ.get("DEEPSEEK_API_KEY", "")]
    values = [value for value in secrets if isinstance(value, str) and len(value) >= 8]
    errors = []
    for path in root.rglob("*"):
        if path.is_symlink():
            errors.append(f"{path}: symlink is not allowed in report artifacts")
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.stat().st_size > MAX_TEXT_FILE_BYTES:
            errors.append(f"{path}: text artifact exceeds safety scan size limit")
            continue
        try:
            data = path.read_bytes()
        except OSError:
            errors.append(f"{path}: cannot read report artifact")
            continue
        for value in values:
            if value.encode("utf-8") in data:
                errors.append(f"{path}: configured secret detected; upload blocked")
                break
    return errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Block uploads with exposed secrets")
    parser.add_argument("reports_root", nargs="?", default="results/reports")
    args = parser.parse_args()
    errors = validate_artifact_secrets(args.reports_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Artifact secret guard passed")


if __name__ == "__main__":
    main()
