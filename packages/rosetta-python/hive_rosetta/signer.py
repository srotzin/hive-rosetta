"""
EIP-3009 transferWithAuthorization signer.
Produces a SignedAuthorization that hivemorph/proof_validator.py accepts.

Wire shape (matches hivemorph/hive_x402/payment_required.py):
  {
    scheme: 'exact',
    network: 'eip155:8453',
    payload: {
      authorization: {
        from, to, value, validAfter, validBefore, nonce
      },
      signature: '0x...'   # 65-byte r||s||v
    }
  }

EIP-712 domain mirrors the USDC contract on Base (USD Coin v2). The ABI
order is non-negotiable: from, to, value, validAfter, validBefore, nonce —
any reorder produces a different digest and the verifier rejects.

This implementation is a direct Python port of rosetta-node/src/signer.js.
It implements EIP-712 low-level using eth_keys for signing to guarantee
byte-identical output to the Node implementation. The signature format is
r||s||v where v is 27 or 28 (Ethereum convention), matching Node's:
  '0x' + r + s + v  where v = (recovery === 0 ? 27 : 28)
"""
from __future__ import annotations

import math
import os
import re
import time as _time_module
from typing import Any

from eth_hash.auto import keccak as keccak256
from eth_keys import keys as eth_keys

from .errors import ErrorCode, RosettaError
from .registry import (
    CAIP2,
    assert_recipient,
    assert_valid_before,
    resolve_asset,
)

# --- low-level helpers ---


def _hex_to_bytes(hex_str: str) -> bytes:
    h = hex_str.replace("0x", "").replace("0X", "")
    if len(h) % 2:
        h = "0" + h
    return bytes.fromhex(h)


def _bytes_to_hex(b: bytes) -> str:
    return b.hex()


def _pad32(hex_str: str) -> str:
    """Pad a hex string (without 0x) to 64 hex chars (32 bytes)."""
    h = hex_str.replace("0x", "").replace("0X", "")
    if len(h) > 64:
        raise ValueError(f"pad32: value too long ({len(h)} hex chars)")
    return h.zfill(64)


def _address_to_32(addr: str) -> str:
    """ABI-encode an address as 32-byte padded hex (no 0x prefix)."""
    return _pad32(addr.lower().replace("0x", "").replace("0X", ""))


def _keccak_hex(*hex_parts: str) -> str:
    """Hash the concatenation of hex parts (without 0x). Returns hex without 0x."""
    concat = "".join(p.replace("0x", "").replace("0X", "") for p in hex_parts)
    return keccak256(_hex_to_bytes(concat)).hex()


def _keccak_text(text: str) -> str:
    return keccak256(text.encode("utf-8")).hex()


# --- EIP-712 TransferWithAuthorization typehash ---

_TRANSFER_WITH_AUTH_TYPE_STRING = (
    "TransferWithAuthorization("
    "address from,"
    "address to,"
    "uint256 value,"
    "uint256 validAfter,"
    "uint256 validBefore,"
    "bytes32 nonce"
    ")"
)

TRANSFER_WITH_AUTH_TYPEHASH_HEX: str = _keccak_text(_TRANSFER_WITH_AUTH_TYPE_STRING)


def _domain_separator_hex(
    eip712_name: str,
    eip712_version: str,
    chain_id: int,
    verifying_contract: str,
) -> str:
    """Compute the EIP-712 domain separator as a hex string (no 0x)."""
    name_hash = _keccak_text(eip712_name)
    version_hash = _keccak_text(eip712_version)
    domain_type_hash = _keccak_text(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    )
    return _keccak_hex(
        domain_type_hash,
        name_hash,
        version_hash,
        _pad32(hex(chain_id)[2:]),
        _address_to_32(verifying_contract),
    )


def _nonce_to_hex(nonce: str | bytes) -> str:
    """Convert nonce to 64-hex-char string (no 0x)."""
    if isinstance(nonce, str):
        n = nonce.replace("0x", "").replace("0X", "")
        if not re.match(r"^[0-9a-fA-F]{64}$", n):
            raise RosettaError(
                ErrorCode["ERR_MALFORMED_HEADER"],
                "nonce must be 0x + 64 hex chars (32 bytes)",
            )
        return n
    if isinstance(nonce, (bytes, bytearray)):
        if len(nonce) != 32:
            raise RosettaError(
                ErrorCode["ERR_MALFORMED_HEADER"],
                "nonce bytes must be 32 bytes",
            )
        return bytes(nonce).hex()
    raise RosettaError(
        ErrorCode["ERR_MALFORMED_HEADER"],
        "nonce must be 0x-string or bytes(32)",
    )


def _struct_hash_hex(auth: dict[str, Any]) -> str:
    """Compute EIP-712 struct hash for a TransferWithAuthorization message."""
    return _keccak_hex(
        TRANSFER_WITH_AUTH_TYPEHASH_HEX,
        _address_to_32(auth["from"]),
        _address_to_32(auth["to"]),
        _pad32(hex(int(auth["value"]))[2:]),
        _pad32(hex(int(auth["validAfter"]))[2:]),
        _pad32(hex(int(auth["validBefore"]))[2:]),
        _nonce_to_hex(auth["nonce"]),
    )


def _digest_hex(domain_sep_hex: str, struct_hash_hex_val: str) -> str:
    """Compute final EIP-712 digest: keccak256(0x1901 || domainSep || structHash)."""
    concat = "1901" + domain_sep_hex + struct_hash_hex_val
    return _keccak_hex(concat)


def _caip2_to_chain_id(caip2: str) -> int | None:
    if caip2 == CAIP2["BASE_MAINNET"]:
        return 8453
    if caip2 == CAIP2["BASE_SEPOLIA"]:
        return 84532
    return None


def random_nonce() -> str:
    """Generate a cryptographically random 32-byte nonce as a 0x-prefixed hex string."""
    return "0x" + os.urandom(32).hex()


# --- signer factory ---

def eip3009_signer(private_key_hex: str) -> dict[str, Any]:
    """Create an EIP-3009 signer from a private key.

    Returns a dict with keys:
      - type: 'eip3009'
      - address: checksummed EVM address derived from the private key
      - sign(network, asset, amount, recipient, validAfter, validBefore, nonce) -> coroutine

    Raises RosettaError(ERR_INVALID_PRIVATE_KEY) if the key is malformed.

    The sign method returns a dict identical in shape to the Node signer output:
      {scheme, network, payload: {authorization, signature}}
    The signature is 0x-prefixed, 132 hex chars: r (64) + s (64) + v (2)
    where v is 27 or 28 (Ethereum convention). This matches Node's:
      '0x' + r + s + (recovery === 0 ? 27 : 28).toString(16).padStart(2, '0')
    """
    pk_str = str(private_key_hex or "").replace("0x", "").replace("0X", "")
    if not re.match(r"^[0-9a-fA-F]{64}$", pk_str):
        raise RosettaError(
            ErrorCode["ERR_INVALID_PRIVATE_KEY"],
            "privateKey must be 0x + 64 hex chars",
        )

    pk_bytes = bytes.fromhex(pk_str)

    # Use eth_keys to derive address + sign
    private_key = eth_keys.PrivateKey(pk_bytes)
    # eth_keys gives a checksummed address via .public_key.to_checksum_address()
    address: str = private_key.public_key.to_checksum_address()

    async def sign(
        *,
        network: str,
        asset: str,
        amount: str | int,
        recipient: str,
        valid_after: int = 0,
        valid_before: int | None = None,
        nonce: str | bytes | None = None,
        eip712_override: dict[str, str] | None = None,
        # Node-style camelCase aliases for cross-language ergonomics
        validAfter: int | None = None,  # noqa: N803
        validBefore: int | None = None,  # noqa: N803
        eip712Override: dict[str, str] | None = None,  # noqa: N803
    ) -> dict[str, Any]:
        # Resolve Node-style camelCase kwargs
        _valid_after = validAfter if validAfter is not None else valid_after
        _valid_before_raw = validBefore if validBefore is not None else valid_before
        _eip712_override = eip712Override if eip712Override is not None else eip712_override

        assert_recipient(recipient)
        meta = resolve_asset(network, asset)
        eip712 = (
            _eip712_override
            if _eip712_override and _eip712_override.get("name") and _eip712_override.get("version")
            else meta["eip712"]
        )
        chain_id = _caip2_to_chain_id(network)
        if chain_id is None:
            raise RosettaError(
                ErrorCode["ERR_UNSUPPORTED_NETWORK"],
                f"Cannot derive chainId from CAIP-2: {network}",
            )

        _vb: int = int(_valid_before_raw) if _valid_before_raw is not None else (
            math.floor(_time_module.time()) + 600
        )
        assert_valid_before(_vb)

        _nonce: str = nonce if nonce is not None else random_nonce()

        # Build the wire authorization object.
        # Values are decimal strings — matches Node's BigInt.toString() output.
        auth = {
            "from": address,
            "to": recipient,
            "value": str(int(amount)),
            "validAfter": str(int(_valid_after)),
            "validBefore": str(_vb),
            "nonce": (_nonce if isinstance(_nonce, str) else ("0x" + _nonce_to_hex(_nonce))),
        }

        domain_sep = _domain_separator_hex(
            eip712["name"],
            eip712["version"],
            chain_id,
            meta["address"],
        )
        sh = _struct_hash_hex(auth)
        digest = _digest_hex(domain_sep, sh)

        # Sign the raw 32-byte EIP-712 digest with eth_keys (RFC 6979, lowS).
        # This is equivalent to secp256k1.sign(digestBytes, pkBytes, {lowS:true})
        # in the Node implementation.
        digest_bytes = bytes.fromhex(digest)
        sig = private_key.sign_msg_hash(digest_bytes)

        # Encode as r||s||v where v = 27 + recovery_bit (matches Node).
        r_hex = hex(sig.r)[2:].zfill(64)
        s_hex = hex(sig.s)[2:].zfill(64)
        v = sig.v + 27  # sig.v is 0 or 1; Ethereum convention is 27 or 28
        v_hex = hex(v)[2:].zfill(2)
        signature = "0x" + r_hex + s_hex + v_hex

        return {
            "scheme": "exact",
            "network": network,
            "payload": {
                "authorization": auth,
                "signature": signature,
            },
        }

    # Wrap the signer in a SimpleNamespace so users can write either
    # `signer.sign(...)` (Node parity) or `signer['sign'](...)` (dict access).
    # Both API styles point at the same coroutine. The .__getitem__ shim makes
    # the object behave as a dict for code that previously used dict access.
    class _Signer:
        type = "eip3009"

        def __init__(self, addr: str, sign_fn) -> None:
            self.address = addr
            self.sign = sign_fn

        def __getitem__(self, key: str):
            return getattr(self, key)

        def keys(self):
            return ["type", "address", "sign"]

    obj = _Signer(address, sign)
    return obj


# Exposed for tests + tooling (mirrors Node __internal)
_internal = {
    "domain_separator_hex": _domain_separator_hex,
    "struct_hash_hex": _struct_hash_hex,
    "digest_hex": _digest_hex,
    "caip2_to_chain_id": _caip2_to_chain_id,
    "TRANSFER_WITH_AUTH_TYPEHASH_HEX": TRANSFER_WITH_AUTH_TYPEHASH_HEX,
}
