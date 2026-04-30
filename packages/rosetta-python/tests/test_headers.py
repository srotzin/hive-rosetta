"""
Conformance: header read/write across v1↔v2 with case tolerance.
Constraint #14: middleware.py reads X-Payment / x-payment / X-PAYMENT.
Mirrors rosetta-node/test/headers.test.js (9 tests).
"""
import base64
import json

import pytest

from hive_rosetta import (
    HEADER_PAYMENT_RESPONSE,
    HEADER_PAYMENT_SIGNATURE,
    read_payment_required,
    read_payment_response,
    read_payment_signature,
    write_payment_required,
    write_payment_response,
    write_payment_signature,
)
from hive_rosetta.errors import RosettaError

SAMPLE = {"scheme": "exact", "network": "eip155:8453", "payload": {"test": True}}


def _b64(obj) -> str:
    return base64.b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode()


def test_read_v2_payment_signature():
    headers = {}
    write_payment_signature(headers, SAMPLE, {"protocol_version": 2})
    back = read_payment_signature(headers)
    assert back == SAMPLE


def test_read_v1_x_payment():
    headers = {}
    write_payment_signature(headers, SAMPLE, {"protocol_version": 1})
    back = read_payment_signature(headers)
    assert back == SAMPLE


def test_dual_emit_produces_both_v1_and_v2():
    headers = {}
    write_payment_signature(headers, SAMPLE, {"protocol_version": "both"})
    # v1 header present
    assert "X-Payment" in headers
    # v2 header present
    assert HEADER_PAYMENT_SIGNATURE in headers


def test_read_tolerates_x_payment_uppercase():
    obj = {"X-PAYMENT": _b64(SAMPLE)}
    back = read_payment_signature(obj)
    assert back == SAMPLE


def test_read_tolerates_x_payment_lowercase():
    obj = {"x-payment": _b64(SAMPLE)}
    back = read_payment_signature(obj)
    assert back == SAMPLE


def test_read_tolerates_x_payment_mixed():
    obj = {"X-Payment": _b64(SAMPLE)}
    back = read_payment_signature(obj)
    assert back == SAMPLE


def test_invalid_base64_throws_err_malformed_header():
    obj = {"X-Payment": "not-valid-base64-json###"}
    with pytest.raises(RosettaError, match="ERR_MALFORMED_HEADER"):
        read_payment_signature(obj)


def test_payment_required_roundtrip():
    headers = {}
    required = {"x402Version": 2, "accepts": [{"scheme": "exact", "network": "eip155:8453"}]}
    write_payment_required(headers, required)
    back = read_payment_required(headers)
    assert back == required


def test_payment_response_roundtrip():
    headers = {}
    settlement = {"success": True, "txHash": "0xabc", "network": "eip155:8453"}
    write_payment_response(headers, settlement)
    back = read_payment_response(headers)
    assert back == settlement
