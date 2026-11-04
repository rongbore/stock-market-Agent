"""Read-only dual-upstream smoke check with safe, provider-specific diagnostics."""
import argparse
import json
import time
from pathlib import Path

from scripts.akshare_provider import fetch_a_share_daily
from scripts.akshare_sina_provider import fetch_sina_daily
from scripts.akshare_crosscheck import compare


FETCH_ERRORS = (ValueError, TypeError, KeyError, RuntimeError,
                ConnectionError, TimeoutError, OSError)


def _write(folder, filename, data):
    (folder / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _safe_error(exc):
    """Return fixed labels only: no exception message, URL or remote response."""
    # Requests' ConnectionError/ProxyError inherit OSError in some versions.
    # The previous broad OSError handler hid this distinction entirely.
    request_types = {cls.__name__ for cls in type(exc).__mro__
                     if cls.__module__ == "requests.exceptions"}
    if "ProxyError" in request_types:
        return "operating_system_or_network", "proxy"
    if "SSLError" in request_types:
        return "operating_system_or_network", "tls"
    if request_types.intersection({"ConnectTimeout", "ReadTimeout", "Timeout"}):
        return "connection_or_timeout", "request_timeout"
    if "ConnectionError" in request_types:
        return "operating_system_or_network", "request_connection"
    if "HTTPError" in request_types:
        return "operating_system_or_network", "http"
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return "connection_or_timeout", "connection_or_timeout"
    if isinstance(exc, (TypeError, KeyError, ValueError)):
        return "response_or_validation", "response_or_validation"
    if isinstance(exc, OSError):
        return "operating_system_or_network", "other_os_error"
    return "runtime_or_dependency", "runtime_or_dependency"


def _failure(diag, provider, exc):
    category, kind = _safe_error(exc)
    diag[f"{provider}_status"] = "failed"
    diag[f"{provider}_error_kind"] = kind
    if diag["error_category"] is None:
        diag["error_category"] = category
        diag["stage"] = provider


def run(symbol, start_date, end_date, folder, *, eastmoney=fetch_a_share_daily,
        sina=fetch_sina_daily, sleep=time.sleep):
    """Attempt both independent read-only upstreams even if one fails."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    diag = {"schema_version": "0.2", "symbol": symbol,
            "start_date": start_date, "end_date": end_date,
            "status": "failed", "stage": "eastmoney",
            "eastmoney_record_count": 0, "sina_record_count": 0,
            "eastmoney_attempts": 0, "sina_attempts": 0,
            "eastmoney_status": "not_attempted", "sina_status": "not_attempted",
            "eastmoney_error_kind": None, "sina_error_kind": None,
            "error_category": None,
            "cross_source_numerical_agreement": False,
            "independent_source_verified": False}
    try:
        snapshots = {}
        for provider, fetch, name in (
            ("eastmoney", eastmoney, "eastmoney_daily_unverified.json"),
            ("sina", sina, "sina_daily_unverified.json"),
        ):
            diag[f"{provider}_status"] = "running"
            # Only retry transient transport failures; never retry invalid data.
            for attempt in range(1, 4):
                diag[f"{provider}_attempts"] = attempt
                try:
                    snapshot = fetch(symbol, start_date, end_date)
                    if not isinstance(snapshot, dict) or not snapshot.get("records"):
                        raise ValueError("empty or invalid snapshot")
                    _write(folder, name, snapshot)
                    diag[f"{provider}_record_count"] = len(snapshot["records"])
                    diag[f"{provider}_status"] = "success"
                    snapshots[provider] = snapshot
                    break
                except FETCH_ERRORS as exc:
                    category, kind = _safe_error(exc)
                    transient = (category == "connection_or_timeout" or kind in
                                 ("request_connection", "proxy", "http", "other_os_error"))
                    if not transient or attempt == 3:
                        _failure(diag, provider, exc)
                        break
                    sleep(attempt)  # At most 1 + 2 seconds of backoff per provider.
        if len(snapshots) != 2:
            return 1
        diag["stage"] = "compare"
        try:
            result = compare(snapshots["eastmoney"], snapshots["sina"])
            _write(folder, "daily_crosscheck_report.json", result)
            diag["cross_source_numerical_agreement"] = result["cross_source_numerical_agreement"]
            diag["status"] = "success" if result["status"] == "passed" else "mismatch"
            diag["stage"] = "complete"
            return 0 if result["status"] == "passed" else 1
        except FETCH_ERRORS as exc:
            diag["error_category"], diag["compare_error_kind"] = _safe_error(exc)
            return 1
    finally:
        _write(folder, "dual_upstream_diagnostics.json", diag)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="000776.SZ")
    parser.add_argument("--start-date", default="2026-10-01")
    parser.add_argument("--end-date", default="2026-10-30")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args(argv)
    return run(args.symbol, args.start_date, args.end_date, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
