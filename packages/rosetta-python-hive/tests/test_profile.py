"""Test the Hive profile — mirrors rosetta-node-hive/test/profile.test.js."""
from __future__ import annotations

import asyncio
import re

import pytest

from hive_rosetta_hive import (
    HIVE_FACILITATOR,
    HIVECOMPUTE_TARGET,
    INFERENCE_URL_PATTERNS,
    apply_hive_profile,
    client,
    matches_inference_pattern,
    server,
)


def test_matches_inference_pattern_openai():
    assert matches_inference_pattern("https://api.openai.com/v1/chat/completions") == "openai-chat"


def test_matches_inference_pattern_anthropic():
    assert matches_inference_pattern("https://api.anthropic.com/v1/messages") == "anthropic-messages"


def test_matches_inference_pattern_openrouter():
    assert matches_inference_pattern("https://openrouter.ai/api/v1/chat/completions") == "openrouter"


def test_matches_inference_pattern_groq():
    assert matches_inference_pattern("https://api.groq.com/openai/v1/chat/completions") == "groq-openai"


def test_matches_inference_pattern_together():
    assert matches_inference_pattern("https://api.together.xyz/v1/chat/completions") == "together-v1"
    assert matches_inference_pattern("https://api.together.ai/v1/chat/completions") == "together-v1"


def test_matches_inference_pattern_fireworks():
    assert matches_inference_pattern("https://api.fireworks.ai/inference/v1/chat/completions") == "fireworks-inference"


def test_matches_inference_pattern_returns_none_for_non_inference():
    assert matches_inference_pattern("https://thehiveryiq.com/v1/icc-es/lookup") is None
    assert matches_inference_pattern("https://example.com/api") is None


def test_hive_facilitator_constant():
    assert HIVE_FACILITATOR == "https://hivemorph.onrender.com"


def test_hivecompute_target_constant():
    assert HIVECOMPUTE_TARGET == "https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions"


def test_inference_url_patterns_shape():
    assert isinstance(INFERENCE_URL_PATTERNS, list)
    assert len(INFERENCE_URL_PATTERNS) >= 5
    for p in INFERENCE_URL_PATTERNS:
        assert isinstance(p["test"], re.Pattern)
        assert isinstance(p["label"], str)


@pytest.mark.asyncio
async def test_client_fetch_rewrites_openai_to_hivecompute():
    calls: list[dict] = []

    async def fake_fetch(url, **kwargs):
        calls.append({"url": url, "headers": dict(kwargs.get("headers") or {})})
        return {"status": 200, "body": "ok"}

    c = client(fetch_impl=fake_fetch)
    res = await c["fetch"]("https://api.openai.com/v1/chat/completions", method="POST", body="{}")
    assert res["status"] == 200
    assert calls[0]["url"] == HIVECOMPUTE_TARGET
    assert calls[0]["headers"]["X-Hive-Origin"] == "rosetta@0.1.0"
    assert calls[0]["headers"]["X-Hive-Rewrite-From"] == "openai-chat"


@pytest.mark.asyncio
async def test_client_fetch_attaches_did_when_configured():
    calls: list[dict] = []

    async def fake_fetch(url, **kwargs):
        calls.append({"url": url, "headers": dict(kwargs.get("headers") or {})})
        return {"status": 200}

    c = client(fetch_impl=fake_fetch, did="did:hive:agent:test123")
    await c["fetch"]("https://api.openai.com/v1/chat/completions")
    assert calls[0]["headers"]["X-Hive-DID"] == "did:hive:agent:test123"


@pytest.mark.asyncio
async def test_client_fetch_leaves_non_inference_urls_alone():
    calls: list[dict] = []

    async def fake_fetch(url, **kwargs):
        calls.append({"url": url})
        return {"status": 200}

    c = client(fetch_impl=fake_fetch)
    await c["fetch"]("https://thehiveryiq.com/v1/hive/alpha/free")
    assert calls[0]["url"] == "https://thehiveryiq.com/v1/hive/alpha/free"


@pytest.mark.asyncio
async def test_rewrite_inference_false_disables_rewrite():
    calls: list[dict] = []

    async def fake_fetch(url, **kwargs):
        calls.append({"url": url})
        return {"status": 200}

    c = client(fetch_impl=fake_fetch, rewrite_inference=False)
    await c["fetch"]("https://api.openai.com/v1/chat/completions")
    assert calls[0]["url"] == "https://api.openai.com/v1/chat/completions"


def test_server_inherits_hive_defaults():
    s = server(
        pay_to="0x15184bf50b3d3f52b60434f8942b7d52f2eb436e",
        amount="5000",
    )
    # Should have produced a server dict with a fastapi factory
    assert callable(s["fastapi"])


@pytest.mark.asyncio
async def test_apply_hive_profile_mutates_target():
    """apply_hive_profile should replace fetch on an existing client dict."""
    calls: list[dict] = []

    async def original(url, **kwargs):
        calls.append({"url": url, "headers": dict(kwargs.get("headers") or {})})
        return {"status": 200}

    target = {"fetch": original, "preview": None}
    apply_hive_profile(target, did="did:hive:agent:abc")
    await target["fetch"]("https://api.openai.com/v1/chat/completions")
    assert calls[0]["url"] == HIVECOMPUTE_TARGET
    assert calls[0]["headers"]["X-Hive-Origin"] == "rosetta@0.1.0"
    assert calls[0]["headers"]["X-Hive-DID"] == "did:hive:agent:abc"
