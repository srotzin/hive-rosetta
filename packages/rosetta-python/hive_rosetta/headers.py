"""
Header read/write helpers covering v1↔v2 compatibility surface.
Hive constraint #14: middleware.py reads X-Payment / x-payment / X-PAYMENT.
Rosetta accepts all three on input, and emits v2 names on output by default.
In dual-emit mode (protocol_version='both') we emit BOTH v1 and v2 names.

Mirrors rosetta-node/src/headers.js exactly.
"""
from __future__ import annotations

import base64
import json
from typing import Any, Union

from .errors import ErrorCode, RosettaError
from .version import (
    HEADER_PAYMENT_REQUIRED,
    HEADER_PAYMENT_RESPONSE,
    HEADER_PAYMENT_SIGNATURE,
    HEADER_V1_DEFAULT_OUTPUT,
    HEADER_V1_INPUT_VARIANTS,
)

# Type alias for header sources accepted by read helpers.
# Accepts: dict, any object with .get() (httpx.Headers, starlette Headers, etc.),
# or any Mapping.
HeaderSource = Any


def _read_raw(source: HeaderSource, candidates: list[str]) -> str | None:
    """Case-insensitive header lookup across dict/Headers-like/Mapping objects.

    Tries each candidate name (and its lowercase variant) in order.
    Returns the first value found, or None.
    """
    if source is None:
        return None

    # Objects with a .get() method (httpx.Headers, starlette Headers, Werkzeug, etc.)
    if hasattr(source, "get") and callable(source.get):
        for name in candidates:
            v = source.get(name)
            if v is not None:
                return v
            v = source.get(name.lower())
            if v is not None:
                return v
        return None

    # Plain dict — build a case-folded lookup map once.
    if isinstance(source, dict):
        lower_map: dict[str, str] = {k.lower(): v for k, v in source.items()}
        for name in candidates:
            v = lower_map.get(name.lower())
            if v is not None:
                return v
        return None

    # Fallback: try dict-style access via items() if available
    try:
        lower_map = {k.lower(): v for k, v in source.items()}
        for name in candidates:
            v = lower_map.get(name.lower())
            if v is not None:
                return v
    except (AttributeError, TypeError):
        pass

    return None


def _decode_base64_json(b64: str) -> Any:
    """Decode a Base64-encoded JSON header value.

    Raises RosettaError(ERR_MALFORMED_HEADER) on failure.
    """
    if b64 is None:
        return None
    try:
        raw = base64.b64decode(str(b64)).decode("utf-8")
        return json.loads(raw)
    except Exception:
        raise RosettaError(
            ErrorCode["ERR_MALFORMED_HEADER"],
            "Header value is not valid Base64-encoded JSON",
            {"sample": str(b64)[:64]},
        )


def _encode_base64_json(value: Any) -> str:
    """Encode a Python object to Base64-encoded JSON (UTF-8)."""
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _set_header(target: Any, name: str, value: str) -> None:
    """Set a header on *target* (dict, Headers-like, or Mapping)."""
    if target is None:
        raise RosettaError(ErrorCode["ERR_MISSING_HEADER"], "header target is null")

    if hasattr(target, "__setitem__"):
        target[name] = value
    elif hasattr(target, "set") and callable(target.set):
        target.set(name, value)
    else:
        raise RosettaError(
            ErrorCode["ERR_MISSING_HEADER"],
            "header target does not support item assignment",
        )


# ---------------------------------------------------------------------------
# PAYMENT-REQUIRED
# ---------------------------------------------------------------------------

def read_payment_required(headers_or_obj: HeaderSource) -> Any | None:
    """Read and decode the PAYMENT-REQUIRED header from *headers_or_obj*."""
    raw = _read_raw(headers_or_obj, [HEADER_PAYMENT_REQUIRED])
    if raw is None:
        return None
    return _decode_base64_json(raw)


def write_payment_required(target: Any, value: Any) -> None:
    """Encode *value* as Base64 JSON and set the PAYMENT-REQUIRED header on *target*."""
    _set_header(target, HEADER_PAYMENT_REQUIRED, _encode_base64_json(value))


# ---------------------------------------------------------------------------
# PAYMENT-SIGNATURE
# ---------------------------------------------------------------------------

def read_payment_signature(headers_or_obj: HeaderSource) -> Any | None:
    """Read and decode the payment signature header.

    Accepts PAYMENT-SIGNATURE (v2), X-Payment / x-payment / X-PAYMENT (v1).
    Returns the decoded object or None.
    """
    candidates = [HEADER_PAYMENT_SIGNATURE, *HEADER_V1_INPUT_VARIANTS]
    raw = _read_raw(headers_or_obj, candidates)
    if raw is None:
        return None
    return _decode_base64_json(raw)


def write_payment_signature(
    target: Any,
    value: Any,
    opts: dict[str, Any] | None = None,
    *,
    protocol_version: int | str | None = None,
) -> None:
    """Encode *value* and write the payment signature header.

    *opts* dict or *protocol_version* kwarg select v1, v2, or 'both'.
    Defaults to v2.
    """
    if opts is None:
        opts = {}

    pv: int | str = protocol_version if protocol_version is not None else opts.get("protocol_version", opts.get("protocolVersion", 2))

    encoded = _encode_base64_json(value)
    if pv == 1:
        _set_header(target, HEADER_V1_DEFAULT_OUTPUT, encoded)
    elif pv == 2:
        _set_header(target, HEADER_PAYMENT_SIGNATURE, encoded)
    elif pv == "both":
        _set_header(target, HEADER_V1_DEFAULT_OUTPUT, encoded)
        _set_header(target, HEADER_PAYMENT_SIGNATURE, encoded)
    else:
        raise RosettaError(
            ErrorCode["ERR_INVALID_VERSION"],
            "protocol_version must be 1, 2, or 'both'",
            {"value": pv},
        )


# ---------------------------------------------------------------------------
# PAYMENT-RESPONSE
# ---------------------------------------------------------------------------

def read_payment_response(headers_or_obj: HeaderSource) -> Any | None:
    """Read and decode the PAYMENT-RESPONSE header from *headers_or_obj*."""
    raw = _read_raw(headers_or_obj, [HEADER_PAYMENT_RESPONSE])
    if raw is None:
        return None
    return _decode_base64_json(raw)


def write_payment_response(target: Any, value: Any) -> None:
    """Encode *value* as Base64 JSON and set the PAYMENT-RESPONSE header on *target*."""
    _set_header(target, HEADER_PAYMENT_RESPONSE, _encode_base64_json(value))


# Exposed for tests + tooling (mirrors Node __internal).
_internal = {
    "decode_base64_json": _decode_base64_json,
    "encode_base64_json": _encode_base64_json,
}
