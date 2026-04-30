"""
hive-rosetta protocol version constants.
Mirrors rosetta-node/src/version.js exactly.
"""
from __future__ import annotations

# Protocol version numbers
X402_V1: int = 1
X402_V2: int = 2

# Header names — v2 (canonical wire format).
HEADER_PAYMENT_REQUIRED: str = "PAYMENT-REQUIRED"
HEADER_PAYMENT_SIGNATURE: str = "PAYMENT-SIGNATURE"
HEADER_PAYMENT_RESPONSE: str = "PAYMENT-RESPONSE"

# Header names — v1 (legacy read tolerance).
# Hive constraint #14: middleware.py reads X-Payment / x-payment / X-PAYMENT.
# Rosetta accepts all three on input, emits v2 names on output by default.
HEADER_V1_INPUT_VARIANTS: tuple[str, ...] = ("X-Payment", "x-payment", "X-PAYMENT")
HEADER_V1_DEFAULT_OUTPUT: str = "X-Payment"

PACKAGE_VERSION: str = "0.1.0"
