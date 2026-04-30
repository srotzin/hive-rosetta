"""
JSON canonicalization (JCS, RFC 8785, simplified).
Stable key ordering + UTF-8 encoding, suitable for cross-platform signing.

MUST stay byte-identical to hive-rosetta/packages/rosetta-node/src/canonical.js
and to hivetrust/src/lib/canonical.js — any divergence silently breaks
Spectral ZK ticket verification.

Cross-language semantic note:
  Node drops keys whose value is `undefined`. Python has no `undefined`;
  the deliberate equivalent is to drop keys whose value is `None`. This is
  documented here as an intentional cross-language semantic mapping so that
  Python callers can rely on the same drop-on-null behaviour.
"""
from __future__ import annotations

import json


def canonicalize(value: object) -> str:
    """Return a JCS-canonical JSON string for *value*.

    Key ordering: lexicographic (same as JS Object.keys().sort()).
    Arrays: order preserved.
    Primitives (str, int, float, bool, None): serialised with json.dumps.
    None-valued keys are dropped (mirrors Node undefined-key drop).
    """
    if value is None or not isinstance(value, (dict, list)):
        # Primitive: let json.dumps handle escaping.
        # ensure_ascii=False keeps non-ASCII chars as-is (same as JSON.stringify).
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, list):
        parts = [canonicalize(item) for item in value]
        return "[" + ",".join(parts) + "]"

    # dict: sort keys lexicographically, drop None-valued entries.
    keys = sorted(value.keys())
    parts: list[str] = []
    for k in keys:
        v = value[k]
        if v is None:
            # Drop None (mirrors JS undefined drop). See module docstring.
            continue
        key_json = json.dumps(k, ensure_ascii=False)
        parts.append(key_json + ":" + canonicalize(v))
    return "{" + ",".join(parts) + "}"


def canonical_bytes(value: object) -> bytes:
    """Return UTF-8 encoded canonical JSON bytes."""
    return canonicalize(value).encode("utf-8")
