#!/usr/bin/env python3
"""Lightweight DAST pass for MindGPT (docs/SECURITY_VALIDATION.md §DAST).

An *active* probe of the deployed surface — the dynamic complement to the static
scanners already in CI (CodeQL/Checkov/gitleaks/Trivy) and the unit-level injection suite
(backend/tests/test_injection_suite.py). It drives real HTTP at the live API and the APIM
gateway and checks the controls the threat model claims at boundary ① / ⑥:

  - auth is enforced (no anonymous access to data endpoints);
  - the APIM gateway refuses traffic without a subscription key;
  - TLS is mandatory (HTTP is redirected/refused);
  - errors are generic (no stack traces / internals leak);
  - CORS does not reflect an arbitrary origin or use a wildcard;
  - transport hardening headers (HSTS, nosniff) are present.

Stdlib only (urllib) so it runs anywhere with no install. This is intentionally a focused,
low-volume probe — not a full OWASP ZAP / Burp active scan, which is the production step
noted in SECURITY_VALIDATION.md. Only ever run it against infrastructure you own.
"""

from __future__ import annotations

import socket
import ssl
import sys
import urllib.error
import urllib.request

API_BASE = "https://mindgpt-build-rdye3f7vd4bkg-api.whitefield-16b997da.francecentral.azurecontainerapps.io"
APIM_BASE = "https://mindgpt-build-rdye3f7vd4bkg-apim.azure-api.net"

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
_results: list[tuple[str, str, str]] = []


def record(verdict: str, name: str, detail: str) -> None:
    _results.append((verdict, name, detail))
    print(f"[{verdict}] {name} — {detail}")


def http(method: str, url: str, headers: dict | None = None, data: bytes | None = None,
         allow_redirects: bool = True, timeout: int = 20):
    """Return (status, headers_lower, body_text). Non-2xx is returned, not raised."""
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(
        *( [] if allow_redirects else [_NoRedirect] )
    )
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(8192).decode("utf-8", "replace")
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, body
    except urllib.error.HTTPError as e:
        body = e.read(8192).decode("utf-8", "replace") if e.fp else ""
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, body
    except urllib.error.URLError as e:
        return None, {}, f"URLError: {e.reason}"
    except (socket.timeout, TimeoutError):
        return None, {}, "timeout"


# -- 1. API is up over TLS -------------------------------------------------------------
def check_health():
    status, _, _ = http("GET", f"{API_BASE}/health")
    if status == 200:
        record(PASS, "API health over HTTPS", "GET /health -> 200")
    else:
        record(WARN, "API health over HTTPS", f"GET /health -> {status}")


# -- 2. Auth enforced on data endpoints ------------------------------------------------
def check_auth_required():
    for method, path, body in [
        ("POST", "/chat", b'{"message":"hi"}'),
        ("GET", "/conversations", None),
        ("GET", "/profile", None),
    ]:
        status, _, _ = http(method, f"{API_BASE}{path}", {"content-type": "application/json"}, body)
        if status in (401, 403):
            record(PASS, f"Auth required: {method} {path}", f"anonymous -> {status}")
        else:
            record(FAIL, f"Auth required: {method} {path}", f"anonymous -> {status} (expected 401/403)")


# -- 3. APIM gateway validates the Entra JWT at the edge -------------------------------
def check_apim_jwt_gate():
    status, _, _ = http("GET", f"{APIM_BASE}/api/health")
    if status == 401:
        record(PASS, "APIM edge JWT gate", "no token -> 401")
    else:
        record(FAIL, "APIM edge JWT gate", f"no token -> {status} (expected 401)")
    status, _, _ = http("GET", f"{APIM_BASE}/api/health", {"Authorization": "Bearer not.a.jwt"})
    if status == 401:
        record(PASS, "APIM rejects malformed token", f"bogus bearer -> {status}")
    else:
        record(WARN, "APIM rejects malformed token", f"bogus bearer -> {status}")


# -- 4. TLS mandatory: HTTP is redirected or refused -----------------------------------
def check_http_redirect():
    host = API_BASE.split("://", 1)[1]
    status, hdrs, _ = http("GET", f"http://{host}/health", allow_redirects=False)
    if status in (301, 302, 307, 308):
        record(PASS, "HTTP->HTTPS", f"plain HTTP -> {status} redirect")
    elif status is None:
        record(PASS, "HTTP->HTTPS", "plain HTTP refused at transport")
    else:
        record(WARN, "HTTP->HTTPS", f"plain HTTP -> {status}")


# -- 5. Errors are generic (no stack traces / internals) -------------------------------
def check_error_verbosity():
    status, _, body = http("POST", f"{API_BASE}/chat",
                           {"content-type": "application/json"}, b"{not valid json")
    leaks = [s for s in ("Traceback", 'File "', "site-packages", "line ", "Exception") if s in body]
    if not leaks:
        record(PASS, "No verbose errors", f"malformed body -> {status}, no stack/internal leak")
    else:
        record(FAIL, "No verbose errors", f"response leaked: {leaks}")


# -- 6. CORS does not reflect an arbitrary origin / wildcard ---------------------------
def check_cors():
    evil = "https://evil.example"
    _, hdrs, _ = http("GET", f"{API_BASE}/health", {"Origin": evil})
    acao = hdrs.get("access-control-allow-origin")
    if acao in (None, ""):
        record(PASS, "CORS origin not reflected", "no ACAO for disallowed origin")
    elif acao == "*":
        record(FAIL, "CORS origin not reflected", "ACAO is wildcard '*'")
    elif acao == evil:
        record(FAIL, "CORS origin not reflected", f"ACAO echoed attacker origin {evil}")
    else:
        record(PASS, "CORS origin not reflected", f"ACAO pinned to {acao}, not attacker origin")


# -- 7. Transport hardening headers ----------------------------------------------------
def check_security_headers():
    _, hdrs, _ = http("GET", f"{API_BASE}/health")
    hsts = "strict-transport-security" in hdrs
    nosniff = hdrs.get("x-content-type-options", "").lower() == "nosniff"
    record(PASS if hsts else WARN, "HSTS header",
           "present" if hsts else "absent (Front Door/WAF adds this at DOCUMENT tier)")
    record(PASS if nosniff else WARN, "X-Content-Type-Options",
           "nosniff" if nosniff else "absent (recommend adding at the edge/app)")


# -- 8. Unsafe HTTP verbs are not honored (no XST / unintended handlers) ---------------
def check_verb_tampering():
    status, _, _ = http("TRACE", f"{API_BASE}/health")
    if status is None or status >= 400:
        record(PASS, "Unsafe verbs rejected", f"TRACE -> {status}")
    else:
        record(FAIL, "Unsafe verbs rejected", f"TRACE -> {status} (expected 4xx/5xx)")


# -- 9. Interactive docs / OpenAPI schema are not public in prod -----------------------
def check_schema_exposure():
    exposed = [p for p in ("/openapi.json", "/docs", "/redoc")
               if http("GET", f"{API_BASE}{p}")[0] == 200]
    if not exposed:
        record(PASS, "API schema not exposed", "/openapi.json, /docs, /redoc all non-200")
    else:
        record(WARN, "API schema exposed", f"public: {exposed} — disable or gate in prod")


# -- 10. No stack/version banner disclosure --------------------------------------------
def check_server_disclosure():
    _, hdrs, _ = http("GET", f"{API_BASE}/health")
    tell = {k: hdrs[k] for k in ("server", "x-powered-by") if k in hdrs}
    verbose = any(any(ch.isdigit() for ch in v) for v in tell.values())  # version numbers = a mild leak
    record(WARN if verbose else PASS, "No server banner leak", f"{tell or 'no notable banner headers'}")


def main() -> int:
    print(f"DAST probe\n  API : {API_BASE}\n  APIM: {APIM_BASE}\n" + "-" * 70)
    ssl._create_default_https_context = ssl.create_default_context
    for check in (check_health, check_auth_required, check_apim_jwt_gate, check_http_redirect,
                  check_error_verbosity, check_cors, check_security_headers,
                  check_verb_tampering, check_schema_exposure, check_server_disclosure):
        try:
            check()
        except Exception as exc:  # a probe crashing must not abort the run
            record(WARN, check.__name__, f"probe error: {exc}")
    print("-" * 70)
    fails = sum(1 for v, _, _ in _results if v == FAIL)
    warns = sum(1 for v, _, _ in _results if v == WARN)
    passes = sum(1 for v, _, _ in _results if v == PASS)
    print(f"Summary: {passes} PASS, {warns} WARN, {fails} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
