"""Cannon tests for v0.2.0 opt-in inference routing.

Test order matters. The 402-after-rewrite test is first because it is the
test that proves the funnel earns. If the signed retry hits the original
URL instead of the hivecompute target, the rewrite is cosmetic and the
closed loop is broken. That is the failure mode that matters most.

Best-architect-at-Google-or-Circle bar: every claim verified, every
header asserted, every URL asserted, every bypass path tested.
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import pytest

from hive_rosetta import (
    HIVECOMPUTE_TARGET,
    INFERENCE_URL_PATTERNS,
    PACKAGE_VERSION,
    client,
    matches_inference_pattern,
)
from hive_rosetta.routing import HIVE_FACILITATOR


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

class _RequestRecord:
    """Captures every fetch the client makes, in order."""

    def __init__(self) -> None:
        self.requests: list[dict] = []

    def record(self, url: str, headers: dict) -> None:
        self.requests.append({"url": url, "headers": dict(headers)})


def _make_fake_httpx(record: _RequestRecord, response_plan):
    """Patch httpx.AsyncClient with a stub that yields planned responses.

    response_plan is a list of dicts: [{"status": int, "body": dict|str, "headers": dict}, ...]
    Each call consumes one response in order.
    """
    import httpx

    class _StubResponse:
        def __init__(self, status: int, body, hdrs: dict | None = None):
            self.status_code = status
            self._body = body
            self.headers = hdrs or {"content-type": "application/json"}

        def json(self):
            if isinstance(self._body, (dict, list)):
                return self._body
            return json.loads(self._body)

        @property
        def text(self):
            if isinstance(self._body, (dict, list)):
                return json.dumps(self._body)
            return self._body

    plan_iter = iter(response_plan)

    class _StubClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def request(self, method, url, headers=None, **kwargs):
            record.record(url, headers or {})
            try:
                spec = next(plan_iter)
            except StopIteration:
                raise AssertionError(f"client made an unplanned request to {url}")
            return _StubResponse(spec["status"], spec.get("body", {}), spec.get("headers"))

    # Patch
    return _StubClient


@pytest.fixture
def patch_httpx(monkeypatch):
    """Yield a function that installs a stub AsyncClient and returns the record."""

    def _install(response_plan):
        record = _RequestRecord()
        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", _make_fake_httpx(record, response_plan))
        return record

    return _install


def _make_signer(record_signs: list):
    """Stub signer that records its inputs and returns a fixed signed envelope."""

    async def sign(*, network, asset, amount, recipient, **rest):
        record_signs.append({
            "network": network, "asset": asset,
            "amount": amount, "recipient": recipient,
        })
        return {
            "scheme": "exact",
            "network": network,
            "asset": asset,
            "amount": str(amount),
            "recipient": recipient,
            "authorization": {
                "from": "0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A",
                "to": recipient,
                "value": str(amount),
                "validAfter": "0",
                "validBefore": "9999999999",
                "nonce": "0x" + "00" * 32,
            },
            "signature": "0x" + "00" * 65,
        }

    return {"sign": sign}


# -----------------------------------------------------------------------
# Q3 closed-loop test: 402-after-rewrite (THE CRITICAL TEST)
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_402_retry_hits_rewritten_url_not_original(patch_httpx):
    """When route_inference rewrites openai → hivecompute, the signed
    retry MUST hit hivecompute. If it hits the original URL, the funnel
    earns nothing.

    This is the test Claude flagged as the one that gets missed under
    time pressure. It runs first.
    """
    record = patch_httpx([
        # First request: rewritten URL (hivecompute) returns 402
        {
            "status": 402,
            "body": {
                "x402Version": 1,
                "accepts": [{
                    "scheme": "exact",
                    "network": "base",
                    "maxAmountRequired": "10000",
                    "asset": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
                    "payTo": "0x15184Bf50B3d3F52b60434f8942b7D52F2eB436E",
                    "extra": {"assetTransferMethod": "eip3009"},
                }],
            },
        },
        # Retry: returns 200
        {"status": 200, "body": {"ok": True}},
    ])

    signs: list = []
    c = client(signer=_make_signer(signs), route_inference=True)

    original_url = "https://api.openai.com/v1/chat/completions"
    resp = await c["fetch"](original_url, method="POST", json={"messages": []})

    assert resp.status_code == 200
    assert len(record.requests) == 2, "expected exactly first + retry"

    first_req = record.requests[0]
    retry_req = record.requests[1]

    # First request hits the rewritten URL (the hivecompute target),
    # NOT the original openai URL.
    assert first_req["url"] == HIVECOMPUTE_TARGET, (
        f"first request must hit hivecompute, got {first_req['url']}"
    )
    assert "openai.com" not in first_req["url"]

    # CRITICAL: the signed retry must also hit the rewritten URL, not
    # the original. If this asserts, the funnel does not earn.
    assert retry_req["url"] == HIVECOMPUTE_TARGET, (
        f"signed retry must hit hivecompute, got {retry_req['url']} — "
        "funnel is broken"
    )
    assert "openai.com" not in retry_req["url"]

    # Retry must carry the payment signature header.
    retry_header_keys_lc = {k.lower() for k in retry_req["headers"]}
    assert "payment-signature" in retry_header_keys_lc or "x-payment" in retry_header_keys_lc, (
        f"retry must include payment signature header, got: {list(retry_req['headers'].keys())}"
    )

    # Signer must have been called with the canonical recipient.
    assert len(signs) == 1
    assert signs[0]["recipient"] == "0x15184Bf50B3d3F52b60434f8942b7D52F2eB436E"


# -----------------------------------------------------------------------
# Pattern coverage — one positive case per inference provider
# -----------------------------------------------------------------------

@pytest.mark.parametrize("url,expected_label", [
    ("https://api.openai.com/v1/chat/completions", "openai-chat"),
    ("https://eu.api.openai.com/v1/chat/completions", "openai-chat"),
    ("https://api.anthropic.com/v1/messages", "anthropic-messages"),
    ("https://api.together.xyz/v1/completions", "together-v1"),
    ("https://api.together.ai/v1/chat/completions", "together-v1"),
    ("https://openrouter.ai/api/v1/chat/completions", "openrouter"),
    ("https://api.openrouter.ai/v1/chat/completions", "openrouter"),
    ("https://api.fireworks.ai/inference/v1/chat/completions", "fireworks-inference"),
    ("https://api.groq.com/openai/v1/chat/completions", "groq-openai"),
])
def test_matches_inference_pattern_positive(url, expected_label):
    assert matches_inference_pattern(url) == expected_label


@pytest.mark.parametrize("url", [
    "https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions",  # idempotent: target itself
    "https://example.com/v1/chat/completions",
    "https://api.openai.com/v1/embeddings",  # not a chat endpoint
    "https://api.openai.com/v1/files",
    "https://malicious-openai.com.evil.io/v1/chat/",  # near-miss
    "",
    "not-a-url",
])
def test_matches_inference_pattern_negative(url):
    assert matches_inference_pattern(url) is None


@pytest.mark.asyncio
async def test_each_pattern_rewrites_and_attaches_headers(patch_httpx):
    """For every known pattern, route_inference=True must rewrite to
    hivecompute and attach the three X-Hive-* headers."""
    cases = [
        ("https://api.openai.com/v1/chat/completions", "openai-chat"),
        ("https://api.anthropic.com/v1/messages", "anthropic-messages"),
        ("https://api.together.xyz/v1/x", "together-v1"),
        ("https://openrouter.ai/api/v1/x", "openrouter"),
        ("https://api.fireworks.ai/inference/v1/chat", "fireworks-inference"),
        ("https://api.groq.com/openai/v1/chat", "groq-openai"),
    ]
    did = "did:hive:test:0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A"

    for original, label in cases:
        record = patch_httpx([{"status": 200, "body": {"ok": True}}])
        c = client(route_inference=True, did=did)
        await c["fetch"](original)

        assert len(record.requests) == 1
        req = record.requests[0]
        assert req["url"] == HIVECOMPUTE_TARGET, f"{original} → {req['url']}"
        assert req["headers"].get("X-Hive-Origin") == f"rosetta@{PACKAGE_VERSION}"
        assert req["headers"].get("X-Hive-Rewrite-From") == label
        assert req["headers"].get("X-Hive-DID") == did


# -----------------------------------------------------------------------
# Bypass paths — flag off, non-matching URL, no DID
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_inference_false_is_total_bypass(patch_httpx):
    """route_inference=False must be a complete bypass: no rewrite, no
    Hive headers. Must be byte-identical to v0.1.0 behavior on this path."""
    record = patch_httpx([{"status": 200, "body": {"ok": True}}])
    c = client(route_inference=False, did="did:hive:test:will-not-attach")

    original = "https://api.openai.com/v1/chat/completions"
    await c["fetch"](original)

    assert len(record.requests) == 1
    req = record.requests[0]
    # URL is original — no rewrite
    assert req["url"] == original
    # No Hive headers attached
    assert "X-Hive-Origin" not in req["headers"]
    assert "X-Hive-DID" not in req["headers"]
    assert "X-Hive-Rewrite-From" not in req["headers"]


@pytest.mark.asyncio
async def test_route_inference_default_is_off(patch_httpx):
    """When the flag is omitted entirely, behavior must match
    route_inference=False (off-by-default)."""
    record = patch_httpx([{"status": 200, "body": {"ok": True}}])
    c = client()  # no flag

    original = "https://api.openai.com/v1/chat/completions"
    await c["fetch"](original)

    assert record.requests[0]["url"] == original
    assert "X-Hive-Origin" not in record.requests[0]["headers"]


@pytest.mark.asyncio
async def test_non_inference_url_with_flag_on_is_clean(patch_httpx):
    """route_inference=True + non-matching URL = no rewrite, no Hive
    headers. This is the 'don't pollute unrelated traffic' guarantee."""
    record = patch_httpx([{"status": 200, "body": {"ok": True}}])
    c = client(route_inference=True, did="did:hive:should-not-leak")

    original = "https://example.com/api/something"
    await c["fetch"](original)

    req = record.requests[0]
    assert req["url"] == original
    assert "X-Hive-Origin" not in req["headers"]
    assert "X-Hive-DID" not in req["headers"]
    assert "X-Hive-Rewrite-From" not in req["headers"]


@pytest.mark.asyncio
async def test_did_omitted_does_not_attach_did_header(patch_httpx):
    """When did is None but rewrite occurs, X-Hive-DID must be absent
    while X-Hive-Origin and X-Hive-Rewrite-From are still present."""
    record = patch_httpx([{"status": 200, "body": {"ok": True}}])
    c = client(route_inference=True)  # no did

    await c["fetch"]("https://api.openai.com/v1/chat/completions")

    req = record.requests[0]
    assert req["url"] == HIVECOMPUTE_TARGET
    assert req["headers"].get("X-Hive-Origin") == f"rosetta@{PACKAGE_VERSION}"
    assert req["headers"].get("X-Hive-Rewrite-From") == "openai-chat"
    assert "X-Hive-DID" not in req["headers"]


# -----------------------------------------------------------------------
# Idempotence + callback
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_fetches_dont_accumulate_headers(patch_httpx):
    """Calling fetch twice must not leak headers between calls."""
    record = patch_httpx([
        {"status": 200, "body": {"ok": True}},
        {"status": 200, "body": {"ok": True}},
    ])
    c = client(route_inference=True, did="did:hive:test")

    await c["fetch"]("https://api.openai.com/v1/chat/completions")
    await c["fetch"]("https://example.com/foo")  # non-matching

    # First request: rewritten with full Hive headers
    assert record.requests[0]["url"] == HIVECOMPUTE_TARGET
    assert "X-Hive-DID" in record.requests[0]["headers"]
    # Second request: NOT rewritten, NO Hive headers (clean state)
    assert record.requests[1]["url"] == "https://example.com/foo"
    assert "X-Hive-DID" not in record.requests[1]["headers"]
    assert "X-Hive-Origin" not in record.requests[1]["headers"]


@pytest.mark.asyncio
async def test_on_rewrite_callback_fires_with_payload(patch_httpx):
    """on_rewrite callback receives {from, to, label} when a rewrite occurs."""
    record = patch_httpx([{"status": 200, "body": {"ok": True}}])
    callback_calls: list = []
    c = client(
        route_inference=True,
        on_rewrite=lambda info: callback_calls.append(info),
    )

    original = "https://api.anthropic.com/v1/messages"
    await c["fetch"](original)

    assert len(callback_calls) == 1
    assert callback_calls[0]["from"] == original
    assert callback_calls[0]["to"] == HIVECOMPUTE_TARGET
    assert callback_calls[0]["label"] == "anthropic-messages"


@pytest.mark.asyncio
async def test_on_rewrite_does_not_fire_when_no_rewrite(patch_httpx):
    record = patch_httpx([{"status": 200, "body": {"ok": True}}])
    callback_calls: list = []
    c = client(
        route_inference=True,
        on_rewrite=lambda info: callback_calls.append(info),
    )
    await c["fetch"]("https://example.com/foo")
    assert callback_calls == []


# -----------------------------------------------------------------------
# Constants surface
# -----------------------------------------------------------------------

def test_hivecompute_target_is_canonical():
    assert HIVECOMPUTE_TARGET == "https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions"


def test_hive_facilitator_is_canonical():
    assert HIVE_FACILITATOR == "https://hivemorph.onrender.com"


def test_inference_url_patterns_count():
    assert len(INFERENCE_URL_PATTERNS) == 6
