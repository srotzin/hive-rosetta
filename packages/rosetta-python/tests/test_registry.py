"""
Conformance: chain + asset registry, validBefore floor, recipient shape.
Mirrors rosetta-node/test/registry.test.js (12 tests).
"""
import pytest

from hive_rosetta import (
    ASSETS,
    CAIP2,
    HIVE_TREASURY_BASE,
    VALIDBEFORE_SENTINEL,
    assert_recipient,
    assert_valid_before,
    resolve_asset,
)
from hive_rosetta.errors import RosettaError


def test_hive_treasury_constant():
    assert HIVE_TREASURY_BASE == "0x15184bf50b3d3f52b60434f8942b7d52f2eb436e"


def test_base_mainnet_usdc_by_symbol():
    meta = resolve_asset(CAIP2["BASE_MAINNET"], "USDC")
    assert meta["address"] == "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
    assert meta["decimals"] == 6
    assert meta["eip712"]["name"] == "USD Coin"
    assert meta["eip712"]["version"] == "2"


def test_base_mainnet_usdt_by_symbol():
    meta = resolve_asset(CAIP2["BASE_MAINNET"], "USDT")
    assert meta["eip712"]["name"] == "Tether USD"
    assert meta["eip712"]["version"] == "1"


def test_base_sepolia_usdc():
    meta = resolve_asset(CAIP2["BASE_SEPOLIA"], "USDC")
    assert meta["address"] == "0x036CbD53842c5426634e7929541eC2318f3dCF7e"


def test_lookup_by_address():
    meta = resolve_asset(CAIP2["BASE_MAINNET"], "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913")
    assert meta["symbol"] == "USDC"


def test_unsupported_network_throws():
    with pytest.raises(RosettaError, match="UNSUPPORTED_NETWORK"):
        resolve_asset("eip155:1", "USDC")


def test_unsupported_asset_throws():
    with pytest.raises(RosettaError, match="UNSUPPORTED_ASSET"):
        resolve_asset(CAIP2["BASE_MAINNET"], "UNICORN")


def test_assert_recipient_accepts_canonical_hive_address():
    assert_recipient(HIVE_TREASURY_BASE)  # should not raise


def test_assert_recipient_rejects_bad_input():
    with pytest.raises(RosettaError, match="INVALID_RECIPIENT"):
        assert_recipient("not-an-address")
    with pytest.raises(RosettaError, match="INVALID_RECIPIENT"):
        assert_recipient("0x123")
    with pytest.raises(RosettaError, match="INVALID_RECIPIENT"):
        assert_recipient(None)


def test_validbefore_sentinel_accepted():
    assert_valid_before(VALIDBEFORE_SENTINEL)  # should not raise


def test_validbefore_in_past_rejected():
    with pytest.raises(RosettaError, match="VALIDBEFORE_TOO_LOW"):
        assert_valid_before(1, 1700000000)


def test_validbefore_well_in_future_accepted():
    now = 1700000000
    assert_valid_before(now + 600, now)  # should not raise
