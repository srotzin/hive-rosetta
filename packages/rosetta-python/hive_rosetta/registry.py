"""
Chain + asset registry. v0.1 ships Base mainnet and Base Sepolia only.
Adding chains is opt-in; never silently extended.

Aligned with hivemorph/hive_x402/payment_required.py ASSET_CHAIN_REGISTRY
and the EIP-712 domains that hivemorph/broadcast/evm.py enforces.

Mirrors rosetta-node/src/registry.js exactly.
"""
from __future__ import annotations

import math
import re
import time
from types import MappingProxyType
from typing import Any

from .errors import ErrorCode, RosettaError


# CAIP-2 chain identifiers
CAIP2 = MappingProxyType({
    "BASE_MAINNET": "eip155:8453",
    "BASE_SEPOLIA": "eip155:84532",
})

# Hive treasury (EVM). REQUIRED_EVM_RECIPIENT in broadcast/evm.py.
HIVE_TREASURY_BASE: str = "0x15184bf50b3d3f52b60434f8942b7d52f2eb436e"

# Asset registry. v0.1: Base mainnet (USDC + USDT) + Base Sepolia (USDC only).
ASSETS: MappingProxyType = MappingProxyType({
    # Base mainnet
    "eip155:8453": MappingProxyType({
        "USDC": MappingProxyType({
            "address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
            "decimals": 6,
            "eip712": MappingProxyType({"name": "USD Coin", "version": "2"}),
        }),
        "USDT": MappingProxyType({
            "address": "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2",
            "decimals": 6,
            "eip712": MappingProxyType({"name": "Tether USD", "version": "1"}),
        }),
    }),
    # Base Sepolia
    "eip155:84532": MappingProxyType({
        "USDC": MappingProxyType({
            "address": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            "decimals": 6,
            "eip712": MappingProxyType({"name": "USDC", "version": "2"}),
        }),
    }),
})


def resolve_asset(network: str, symbol_or_address: str) -> dict[str, Any]:
    """Return asset metadata + symbol for *network* + *symbol_or_address*.

    Raises RosettaError on unsupported network or asset.
    """
    chain = ASSETS.get(network)
    if chain is None:
        raise RosettaError(
            ErrorCode["ERR_UNSUPPORTED_NETWORK"],
            f"Network not supported in v0.1: {network}",
            {"network": network, "supported": list(ASSETS.keys())},
            "v0.1 supports Base mainnet (eip155:8453) and Base Sepolia (eip155:84532).",
        )

    # Symbol lookup
    if symbol_or_address in chain:
        meta = dict(chain[symbol_or_address])
        meta["eip712"] = dict(chain[symbol_or_address]["eip712"])
        meta["symbol"] = symbol_or_address
        return meta

    # Address lookup (case-insensitive)
    lower = str(symbol_or_address).lower()
    for sym, meta_proxy in chain.items():
        if meta_proxy["address"].lower() == lower:
            meta = dict(meta_proxy)
            meta["eip712"] = dict(meta_proxy["eip712"])
            meta["symbol"] = sym
            return meta

    raise RosettaError(
        ErrorCode["ERR_UNSUPPORTED_ASSET"],
        f"Asset not registered for {network}: {symbol_or_address}",
        {"network": network, "asset": symbol_or_address},
    )


# validBefore floor — Hive constraint: validBefore=9_999_999_999 sentinel
# is the canonical "no expiry" value used in production. Any value below
# (now + minimum lifetime) signals replay-window pressure and we reject.
VALIDBEFORE_SENTINEL: int = 9_999_999_999
VALIDBEFORE_MIN_LIFETIME_SECONDS: int = 30


def assert_valid_before(
    valid_before: int,
    now_seconds: int | None = None,
) -> None:
    """Raise RosettaError if *valid_before* is too low.

    Accepts the sentinel 9_999_999_999 unconditionally.
    """
    if now_seconds is None:
        now_seconds = math.floor(time.time())

    if valid_before == VALIDBEFORE_SENTINEL:
        return  # accepted sentinel

    minimum = now_seconds + VALIDBEFORE_MIN_LIFETIME_SECONDS
    if valid_before < minimum:
        raise RosettaError(
            ErrorCode["ERR_VALIDBEFORE_TOO_LOW"],
            f"validBefore ({valid_before}) is below minimum lifetime floor",
            {
                "validBefore": valid_before,
                "now": now_seconds,
                "minimum": minimum,
            },
            f"Set validBefore to at least {VALIDBEFORE_MIN_LIFETIME_SECONDS}s in the future, "
            f"or use the sentinel {VALIDBEFORE_SENTINEL}.",
        )


_EVM_ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def assert_recipient(addr: object) -> None:
    """Raise RosettaError if *addr* is not a valid 0x-prefixed 40-hex EVM address."""
    if not isinstance(addr, str) or not _EVM_ADDR_RE.match(addr):
        raise RosettaError(
            ErrorCode["ERR_INVALID_RECIPIENT"],
            "Recipient must be 0x-prefixed 40-hex EVM address",
            {"address": addr},
        )


# Backwards-compatible alias used by test mirrors
assertValidBefore = assert_valid_before  # noqa: N816
assertRecipient = assert_recipient  # noqa: N816
