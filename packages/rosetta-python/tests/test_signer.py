"""
Conformance: EIP-3009 signer correctness.
Critical: the produced signature must be recoverable to the signer's address
using the canonical EIP-712 digest. Any byte change in domain, types, or
message ABI order causes recovery to a different address.

Mirrors rosetta-node/test/signer.test.js (8 tests).

Cross-language conformance: the canonical signature for (pk=0x11*32,
nonce=0xaa*32, network=eip155:8453, asset=USDC, amount=5000,
recipient=HIVE_TREASURY_BASE, validBefore=9999999999) MUST equal:
0x43330c6691f142b470983b858eadc933f28f8e58b750ce89f321235396641dfa324cd74718ae31528f7685dc38e851c5739a092e002223c50e161df2aa95a4a81b
"""
import re

import pytest
from eth_keys import keys as eth_keys_module

from hive_rosetta import HIVE_TREASURY_BASE, eip3009_signer, random_nonce
from hive_rosetta.errors import RosettaError
from hive_rosetta.signer import (
    TRANSFER_WITH_AUTH_TYPEHASH_HEX,
    _digest_hex,
    _domain_separator_hex,
    _internal,
    _struct_hash_hex,
)

TEST_PK = "0x" + "11" * 32

# The canonical cross-language conformance signature.
CANONICAL_SIGNATURE = (
    "0x43330c6691f142b470983b858eadc933f28f8e58b750ce89f321235396641dfa"
    "324cd74718ae31528f7685dc38e851c5739a092e002223c50e161df2aa95a4a81b"
)


def _recover_address(digest_hex: str, sig_hex: str) -> str:
    """Recover EVM address from a raw digest + r||s||v signature."""
    sig_no_prefix = sig_hex.replace("0x", "")
    r = int(sig_no_prefix[:64], 16)
    s = int(sig_no_prefix[64:128], 16)
    v = int(sig_no_prefix[128:130], 16)
    recovery = v - 27

    digest_bytes = bytes.fromhex(digest_hex.replace("0x", ""))

    from eth_hash.auto import keccak
    from eth_keys import keys

    # Reconstruct the recoverable signature
    sig_bytes = bytes.fromhex(sig_no_prefix[:128])
    pk = keys.Signature(vrs=(recovery, r, s)).recover_public_key_from_msg_hash(digest_bytes)
    pub_bytes = pk.to_bytes()  # 64 bytes (no prefix)
    addr_bytes = keccak(pub_bytes)[-20:]
    return "0x" + addr_bytes.hex()


@pytest.mark.asyncio
async def test_produces_recoverable_eip3009_signature_on_base_usdc():
    signer = eip3009_signer(TEST_PK)
    out = await signer["sign"](
        network="eip155:8453",
        asset="USDC",
        amount="5000",
        recipient=HIVE_TREASURY_BASE,
        validBefore=9999999999,
        nonce="0x" + "aa" * 32,
    )
    assert out["scheme"] == "exact"
    assert out["network"] == "eip155:8453"
    assert out["payload"]["authorization"]["from"] == signer["address"]
    assert out["payload"]["authorization"]["to"] == HIVE_TREASURY_BASE
    assert out["payload"]["authorization"]["value"] == "5000"
    assert len(out["payload"]["signature"]) == 132  # 0x + 65*2

    # Recover address from signature
    ds = _domain_separator_hex("USD Coin", "2", 8453, "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913")
    sh = _struct_hash_hex(out["payload"]["authorization"])
    digest = _digest_hex(ds, sh)
    recovered = _recover_address(digest, out["payload"]["signature"])
    assert recovered.lower() == signer["address"].lower()


@pytest.mark.asyncio
async def test_validates_recipient():
    signer = eip3009_signer(TEST_PK)
    with pytest.raises(RosettaError, match="INVALID_RECIPIENT"):
        await signer["sign"](
            network="eip155:8453",
            asset="USDC",
            amount="5000",
            recipient="not-an-address",
            validBefore=9999999999,
        )


@pytest.mark.asyncio
async def test_rejects_validbefore_in_past():
    signer = eip3009_signer(TEST_PK)
    with pytest.raises(RosettaError, match="VALIDBEFORE_TOO_LOW"):
        await signer["sign"](
            network="eip155:8453",
            asset="USDC",
            amount="5000",
            recipient=HIVE_TREASURY_BASE,
            validBefore=1,
        )


@pytest.mark.asyncio
async def test_accepts_validbefore_sentinel():
    signer = eip3009_signer(TEST_PK)
    out = await signer["sign"](
        network="eip155:8453",
        asset="USDC",
        amount="1",
        recipient=HIVE_TREASURY_BASE,
        validBefore=9999999999,
        nonce="0x" + "ff" * 32,
    )
    assert out["payload"]["authorization"]["validBefore"] == "9999999999"


def test_rejects_bad_private_key():
    with pytest.raises(RosettaError, match="INVALID_PRIVATE_KEY"):
        eip3009_signer("not-a-key")
    with pytest.raises(RosettaError, match="INVALID_PRIVATE_KEY"):
        eip3009_signer("0x123")


def test_random_nonce_produces_32_byte_hex():
    n = random_nonce()
    assert re.match(r"^0x[0-9a-f]{64}$", n)


def test_typehash_matches_eip3009_canonical_value():
    """The TransferWithAuthorization typehash is invariant across all USDC contracts.
    If this drifts, every signature breaks.
    keccak256("TransferWithAuthorization(address from,address to,uint256 value,
               uint256 validAfter,uint256 validBefore,bytes32 nonce)")
    """
    assert (
        TRANSFER_WITH_AUTH_TYPEHASH_HEX
        == "7c7c6cdb67a18743f49ec6fa9b35f50d52ed05cbed4cc592e13b44501c1a2267"
    )


@pytest.mark.asyncio
async def test_signs_deterministically_given_fixed_inputs():
    a = eip3009_signer(TEST_PK)
    b = eip3009_signer(TEST_PK)
    params = dict(
        network="eip155:8453",
        asset="USDC",
        amount="5000",
        recipient=HIVE_TREASURY_BASE,
        validBefore=9999999999,
        nonce="0x" + "cc" * 32,
    )
    sig1 = await a["sign"](**params)
    sig2 = await b["sign"](**params)
    assert sig1["payload"]["signature"] == sig2["payload"]["signature"]


@pytest.mark.asyncio
async def test_cross_language_conformance_signature():
    """The canonical cross-language conformance test.

    For identical inputs (private key, network, asset, amount, recipient,
    validBefore, nonce), Python must produce the EXACT same byte sequence
    as Node. This is the most important test in the entire package.

    Expected signature (from Node's signer.test.js canonical vector):
    0x43330c6691f142b470983b858eadc933f28f8e58b750ce89f321235396641dfa
      324cd74718ae31528f7685dc38e851c5739a092e002223c50e161df2aa95a4a81b
    """
    signer = eip3009_signer(TEST_PK)
    out = await signer["sign"](
        network="eip155:8453",
        asset="USDC",
        amount="5000",
        recipient=HIVE_TREASURY_BASE,
        validBefore=9999999999,
        nonce="0x" + "aa" * 32,
        validAfter=0,
    )
    assert out["payload"]["signature"] == CANONICAL_SIGNATURE, (
        f"Cross-language conformance FAILED.\n"
        f"Got:      {out['payload']['signature']}\n"
        f"Expected: {CANONICAL_SIGNATURE}"
    )
