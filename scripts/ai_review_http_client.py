"""Isolated, opt-in AI review API transport (stdlib only).

Provider-neutral OpenAI-compatible chat-completions request. Never grants merge.
No invocation unless an endpoint and token are explicitly supplied by caller.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
import ipaddress

from scripts.ai_review_evidence_binding import attach_review

MAX_RESPONSE_BYTES = 65_536


def _validate_endpoint(endpoint, allowed_hosts=None):
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        raise ValueError("invalid endpoint")
    parsed = urllib.parse.urlsplit(endpoint)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("HTTPS endpoint without credentials or fragment required")
    if parsed.query or parsed.port not in (None, 443):
        raise ValueError("endpoint query and nonstandard ports forbidden")
    try:
        ipaddress.ip_address(host)
        raise ValueError("IP literal endpoints forbidden")
    except ValueError as exc:
        if str(exc) == "IP literal endpoints forbidden":
            raise
    if not isinstance(allowed_hosts, (list, tuple, set)) or not allowed_hosts:
        raise ValueError("provider host allowlist required")
    normalized = {str(item).lower() for item in allowed_hosts}
    if host not in normalized:
        raise ValueError("provider host not allowlisted")
    return endpoint


def invoke_review(*, prepared, expected_head_sha, expected_digest, endpoint, token,
                  model, timeout=60, opener=None, allowed_hosts=None):
    _validate_endpoint(endpoint, allowed_hosts=allowed_hosts)
    if not isinstance(token, str) or not token.strip() or len(token) > 4096:
        raise ValueError("missing API credential")
    if not isinstance(model, str) or not model.strip() or len(model) > 128:
        raise ValueError("invalid model")
    if type(timeout) not in (int, float) or not 1 <= timeout <= 60:
        raise ValueError("invalid timeout")
    # Validate SHA/digest and immutable request BEFORE any network request.
    request = prepared.get("request") if isinstance(prepared, dict) else None
    if not isinstance(request, dict):
        raise ValueError("missing prepared request")
    from scripts.ai_review_evidence_binding import _digest
    if (request.get("head_sha") != expected_head_sha or
            prepared.get("head_sha") != expected_head_sha or
            prepared.get("request_digest") != expected_digest or
            _digest(request) != expected_digest):
        raise ValueError("stale or modified request")
    payload = {
        "model": model,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": 3000,
        "messages": [
            {"role": "system", "content": request["system_instructions"]},
            {"role": "user", "content": request["untrusted_pr_data"]},
        ],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = urllib.request.Request(
        endpoint, data=body,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    # Redirects are disabled to avoid sending bearer credentials to a new host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError("redirect forbidden")
    transport = opener if opener is not None else urllib.request.build_opener(NoRedirect())
    try:
        with transport.open(http_request, timeout=timeout) as response:
            if getattr(response, "status", 200) != 200:
                raise ValueError("provider_http_unexpected_status")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # Do not print provider response bodies: they may contain sensitive details.
        raise ValueError("provider_http_" + str(exc.code)) from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError):
            raise ValueError("provider_timeout") from None
        raise ValueError("provider_network_error") from None
    except (OSError, TimeoutError):
        raise ValueError("provider_network_error") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("model response too large")
    try:
        envelope = json.loads(raw.decode("utf-8"))
        content = envelope["choices"][0]["message"]["content"]
    except (UnicodeError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ValueError("invalid provider response") from exc
    result = attach_review(prepared=prepared, response=content,
                           expected_head_sha=expected_head_sha,
                           expected_digest=expected_digest)
    result["model_invoked"] = True
    return result
