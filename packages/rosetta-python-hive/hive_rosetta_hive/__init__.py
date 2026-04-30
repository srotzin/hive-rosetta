"""hive-rosetta-hive — Hive-flavored profile for hive-rosetta.

Wraps the base rosetta client with Hive defaults:
  - facilitator = hivemorph
  - inference URL rewrites → hivecompute (the funnel mechanic)
  - emits X-Hive-Origin attribution header
  - emits X-Hive-DID header when DID is set

Free forever. No license check. No tier check. Zero friction.

Mirrors @hive-civilization/rosetta-hive (Node).
"""
from __future__ import annotations

from .profile import (
    HIVE_FACILITATOR,
    HIVECOMPUTE_TARGET,
    INFERENCE_URL_PATTERNS,
    apply_hive_profile,
    client,
    matches_inference_pattern,
    server,
)

__version__ = "0.1.0"

__all__ = [
    "HIVE_FACILITATOR",
    "HIVECOMPUTE_TARGET",
    "INFERENCE_URL_PATTERNS",
    "apply_hive_profile",
    "client",
    "matches_inference_pattern",
    "server",
]
