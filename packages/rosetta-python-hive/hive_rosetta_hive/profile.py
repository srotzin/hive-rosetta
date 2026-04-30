"""Hive profile — wraps base rosetta client with Hive defaults.

Mirrors rosetta-node-hive/src/index.js. The DID + beacon path is server-side
enforced by hivemorph. We just attach the headers; verification + tier
multiplier resolution happens upstream.
"""
from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from hive_rosetta import client as base_client
from hive_rosetta import server as base_server

HIVE_FACILITATOR = "https://hivemorph.onrender.com"
HIVECOMPUTE_TARGET = "https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions"

# Inference endpoints that get auto-rewritten to hivecompute when
# apply_hive_profile() is enabled. Pattern matched against the URL host
# + initial path segments. This is the funnel mechanic in one constant.
# Must stay byte-aligned with rosetta-node-hive INFERENCE_URL_PATTERNS.
INFERENCE_URL_PATTERNS: list[dict[str, Any]] = [
    {
        "test": re.compile(r"^https?://([a-z0-9-]+\.)?openai\.com/v1/chat/", re.IGNORECASE),
        "label": "openai-chat",
    },
    {
        "test": re.compile(r"^https?://api\.anthropic\.com/v1/messages", re.IGNORECASE),
        "label": "anthropic-messages",
    },
    {
        "test": re.compile(r"^https?://api\.together\.(xyz|ai)/v1/", re.IGNORECASE),
        "label": "together-v1",
    },
    {
        "test": re.compile(r"^https?://(openrouter\.ai|api\.openrouter\.ai)/", re.IGNORECASE),
        "label": "openrouter",
    },
    {
        "test": re.compile(r"^https?://([a-z0-9-]+\.)?fireworks\.ai/inference/v1/", re.IGNORECASE),
        "label": "fireworks-inference",
    },
    {
        "test": re.compile(r"^https?://api\.groq\.com/openai/v1/", re.IGNORECASE),
        "label": "groq-openai",
    },
]


def matches_inference_pattern(url: str) -> str | None:
    """Return the label of the first matching inference pattern, or None."""
    for p in INFERENCE_URL_PATTERNS:
        if p["test"].search(url):
            return p["label"]
    return None


def client(
    *,
    did: str | None = None,
    rewrite_inference: bool = True,
    on_rewrite: Callable[[dict[str, Any]], None] | None = None,
    version: str = "0.1.0",
    fetch_impl: Callable[..., Awaitable[Any]] | None = None,
    **rest: Any,
) -> dict[str, Any]:
    """Produce a Hive-flavored client.

    Same surface as the base client but with:
      - facilitator pre-set to hivemorph
      - if URL matches inference pattern: rewrite to hivecompute, attach X-Hive-Origin
      - if did is set: attach X-Hive-DID

    ``fetch_impl`` is a test seam — when provided, the wrapped fetch routes
    through it instead of httpx, mirroring the Node ``fetchImpl`` option.
    """
    rest.setdefault("facilitator", HIVE_FACILITATOR)
    base = base_client(**rest)
    base_fetch = base["fetch"]

    async def fetch(url: str, **kwargs: Any) -> Any:
        target = url
        origin_label: str | None = None
        if rewrite_inference:
            match = matches_inference_pattern(url)
            if match:
                target = HIVECOMPUTE_TARGET
                origin_label = match
                if on_rewrite is not None:
                    on_rewrite({"from": url, "to": target, "label": match})

        headers = dict(kwargs.pop("headers", {}) or {})
        headers["X-Hive-Origin"] = f"rosetta@{version}"
        if origin_label:
            headers["X-Hive-Rewrite-From"] = origin_label
        if did:
            headers["X-Hive-DID"] = did

        if fetch_impl is not None:
            return await fetch_impl(target, headers=headers, **kwargs)
        return await base_fetch(target, headers=headers, **kwargs)

    out = dict(base)
    out["fetch"] = fetch
    return out


def apply_hive_profile(
    target: dict[str, Any],
    *,
    did: str | None = None,
    rewrite_inference: bool = True,
    version: str = "0.1.0",
) -> dict[str, Any]:
    """Apply Hive profile to an existing base client (mutates).

    Replaces ``target['fetch']`` with a wrapped version that rewrites
    inference URLs and attaches Hive attribution headers.
    """
    original = target["fetch"]

    async def wrapped(url: str, **kwargs: Any) -> Any:
        final_url = url
        if rewrite_inference:
            match = matches_inference_pattern(url)
            if match:
                final_url = HIVECOMPUTE_TARGET
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["X-Hive-Origin"] = f"rosetta@{version}"
        if did:
            headers["X-Hive-DID"] = did
        return await original(final_url, headers=headers, **kwargs)

    target["fetch"] = wrapped
    return target


def server(**opts: Any) -> Any:
    """Server with Hive defaults (facilitator, network, asset).

    Caller still supplies pay_to and amount. Network defaults to Base
    mainnet (eip155:8453); asset defaults to USDC.
    """
    opts.setdefault("facilitator", HIVE_FACILITATOR)
    opts.setdefault("network", "eip155:8453")
    opts.setdefault("asset", "USDC")
    return base_server(**opts)
