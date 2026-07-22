"""Security headers are emitted on every response (task #34).

Defence-in-depth for the one-image SPA:
  * Content-Security-Policy — default-src locks every subresource to this origin;
    style-src additionally allows 'unsafe-inline' because the React SPA applies
    inline style attributes; frame-ancestors 'none' blocks clickjacking. Scripts
    stay locked to 'self'.
  * X-Content-Type-Options: nosniff — no MIME sniffing.
  * Referrer-Policy: no-referrer — never leak the command-center URL.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

EXPECTED_CSP = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
)
EXPECTED_HEADERS = {
    "content-security-policy": EXPECTED_CSP,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}


def _assert_security_headers(resp: object) -> None:
    for name, value in EXPECTED_HEADERS.items():
        assert resp.headers[name] == value, name


def test_healthz_carries_security_headers(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    _assert_security_headers(resp)


def test_api_response_carries_security_headers(client: TestClient) -> None:
    # An unauthenticated API call still flows through the middleware.
    resp = client.get("/api/me")
    _assert_security_headers(resp)


def test_csp_locks_scripts_and_frames_but_allows_only_inline_styles() -> None:
    # Guard the exact directives: scripts must NOT be granted 'unsafe-inline',
    # and frame-ancestors must be present (it does not inherit from default-src).
    assert "script-src" not in EXPECTED_CSP  # scripts fall back to default-src 'self'
    default_src, style_src, frame_ancestors = (
        d.strip() for d in EXPECTED_CSP.split(";")
    )
    assert default_src == "default-src 'self'"
    assert style_src == "style-src 'self' 'unsafe-inline'"
    assert frame_ancestors == "frame-ancestors 'none'"
