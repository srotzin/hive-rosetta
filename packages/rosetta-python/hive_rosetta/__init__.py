"""
hive-rosetta — open x402 v2 SDK for Python.
v0.2: Base mainnet + Sepolia, EIP-3009, scheme=exact, opt-in inference routing.

Public exports mirror @hive-civilization/rosetta (Node) index.js exactly.
"""
from __future__ import annotations

from .canonical import canonical_bytes, canonicalize
from .client import client
from .errors import ErrorCode, RosettaError
from .headers import (
    read_payment_required,
    read_payment_response,
    read_payment_signature,
    write_payment_required,
    write_payment_response,
    write_payment_signature,
)
from .registry import (
    ASSETS,
    CAIP2,
    HIVE_TREASURY_BASE,
    VALIDBEFORE_SENTINEL,
    assert_recipient,
    assert_valid_before,
    resolve_asset,
)
from .routing import (
    HIVE_FACILITATOR,
    HIVECOMPUTE_TARGET,
    INFERENCE_URL_PATTERNS,
    matches_inference_pattern,
)
from .server import server
from .signer import eip3009_signer, random_nonce
from .version import (
    HEADER_PAYMENT_REQUIRED,
    HEADER_PAYMENT_RESPONSE,
    HEADER_PAYMENT_SIGNATURE,
    PACKAGE_VERSION,
    X402_V1,
    X402_V2,
)

__all__ = [
    # canonical
    "canonicalize",
    "canonical_bytes",
    # errors
    "RosettaError",
    "ErrorCode",
    # version constants
    "X402_V1",
    "X402_V2",
    "HEADER_PAYMENT_REQUIRED",
    "HEADER_PAYMENT_SIGNATURE",
    "HEADER_PAYMENT_RESPONSE",
    "PACKAGE_VERSION",
    # registry
    "CAIP2",
    "ASSETS",
    "HIVE_TREASURY_BASE",
    "resolve_asset",
    "assert_recipient",
    "assert_valid_before",
    "VALIDBEFORE_SENTINEL",
    # headers
    "read_payment_required",
    "write_payment_required",
    "read_payment_signature",
    "write_payment_signature",
    "read_payment_response",
    "write_payment_response",
    # signer
    "eip3009_signer",
    "random_nonce",
    # routing (v0.2.0)
    "HIVE_FACILITATOR",
    "HIVECOMPUTE_TARGET",
    "INFERENCE_URL_PATTERNS",
    "matches_inference_pattern",
    # high-level
    "client",
    "server",
]
