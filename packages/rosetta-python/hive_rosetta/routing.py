"""Inference URL routing — opt-in funnel mechanic for hive-rosetta.

When ``route_inference=True`` is set on the client, requests to known
inference endpoints (OpenAI, Anthropic, Together, OpenRouter, Fireworks,
Groq) are rewritten to the canonical hivecompute target. This is the
funnel: third-party inference traffic gets settled through hivecompute,
which is x402-priced and spectral-ZK-ticketed.

The flag defaults to False. When False, this module is inert — no URL
rewriting, no extra headers, identical behavior to the neutral base
client. That guarantees upgrades from v0.1.0 are non-breaking.

Mirrors rosetta-node/src/routing.js byte-for-byte.
"""
from __future__ import annotations

import re
from typing import Any

# Canonical hivecompute target for rewritten inference traffic.
HIVECOMPUTE_TARGET = "https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions"

# Hivemorph facilitator URL (used by server() helper, not by routing).
HIVE_FACILITATOR = "https://hivemorph.onrender.com"

# Inference endpoints that get auto-rewritten to hivecompute when
# route_inference=True. Pattern matched against the full URL string.
# Must stay byte-aligned with rosetta-node/src/routing.js.
INFERENCE_URL_PATTERNS: list[dict[str, Any]] = [
    {
        "test": re.compile(r"^https?://(?:[a-z0-9-]+\.)*openai\.com/v1/chat/", re.IGNORECASE),
        "label": "openai-chat",
    },
    {
        "test": re.compile(r"^https?://(?:[a-z0-9-]+\.)*anthropic\.com/v1/messages", re.IGNORECASE),
        "label": "anthropic-messages",
    },
    {
        "test": re.compile(r"^https?://(?:[a-z0-9-]+\.)*together\.(xyz|ai)/v1/", re.IGNORECASE),
        "label": "together-v1",
    },
    {
        "test": re.compile(r"^https?://(?:[a-z0-9-]+\.)*openrouter\.ai/", re.IGNORECASE),
        "label": "openrouter",
    },
    {
        "test": re.compile(r"^https?://(?:[a-z0-9-]+\.)*fireworks\.ai/inference/v1/", re.IGNORECASE),
        "label": "fireworks-inference",
    },
    {
        "test": re.compile(r"^https?://(?:[a-z0-9-]+\.)*groq\.com/openai/v1/", re.IGNORECASE),
        "label": "groq-openai",
    },
]


def matches_inference_pattern(url: str) -> str | None:
    """Return the label of the first matching inference pattern, or None.

    Returns None for any URL that does not match a known inference endpoint,
    including the hivecompute target itself (so re-routing is idempotent).
    """
    if not isinstance(url, str):
        return None
    for p in INFERENCE_URL_PATTERNS:
        if p["test"].search(url):
            return p["label"]
    return None
