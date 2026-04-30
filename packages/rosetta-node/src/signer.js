// EIP-3009 transferWithAuthorization signer.
// Produces a SignedAuthorization that hivemorph/proof_validator.py accepts.
//
// Wire shape (matches hivemorph/hive_x402/payment_required.py):
//   {
//     scheme: 'exact',
//     network: 'eip155:8453',
//     payload: {
//       authorization: {
//         from, to, value, validAfter, validBefore, nonce
//       },
//       signature: '0x...'   // 65-byte v||r||s
//     }
//   }
//
// EIP-712 domain mirrors the USDC contract on Base (USD Coin v2). The ABI
// order is non-negotiable: from, to, value, validAfter, validBefore, nonce —
// any reorder produces a different digest and the verifier rejects.

import { keccak_256 } from '@noble/hashes/sha3';
import { secp256k1 } from '@noble/curves/secp256k1';
import { getAddress } from '@ethersproject/address';
import { RosettaError, ErrorCode } from './errors.js';
import { resolveAsset, assertRecipient, assertValidBefore, CAIP2 } from './registry.js';

const TYPED_DATA_PREFIX = Uint8Array.of(0x19, 0x01);

// --- low-level encoders (no ethers / web3 dependency) ---

function pad32(hex) {
  hex = hex.replace(/^0x/, '');
  if (hex.length > 64) throw new Error('pad32: value too long');
  return hex.padStart(64, '0');
}

function bigIntToHex(value) {
  return BigInt(value).toString(16);
}

function nonceToHex(nonce) {
  if (typeof nonce === 'string') {
    if (!/^0x[0-9a-fA-F]{64}$/.test(nonce)) {
      throw new RosettaError(ErrorCode.ERR_MALFORMED_HEADER, 'nonce must be 0x + 64 hex chars (32 bytes)');
    }
    return nonce.slice(2);
  }
  if (nonce instanceof Uint8Array) {
    if (nonce.length !== 32) throw new RosettaError(ErrorCode.ERR_MALFORMED_HEADER, 'nonce Uint8Array must be 32 bytes');
    return Array.from(nonce, b => b.toString(16).padStart(2, '0')).join('');
  }
  throw new RosettaError(ErrorCode.ERR_MALFORMED_HEADER, 'nonce must be 0x-string or Uint8Array(32)');
}

function addressTo32(addr) {
  return pad32(addr.toLowerCase().replace(/^0x/, ''));
}

// --- EIP-712 hashing (TransferWithAuthorization) ---

const TRANSFER_WITH_AUTH_TYPEHASH_HEX = (() => {
  const typeString = 'TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)';
  const enc = new TextEncoder().encode(typeString);
  return Array.from(keccak_256(enc), b => b.toString(16).padStart(2, '0')).join('');
})();

function hexToBytes(hex) {
  hex = hex.replace(/^0x/, '');
  if (hex.length % 2) hex = '0' + hex;
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

function bytesToHex(bytes) {
  return Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
}

function keccakHex(...hexParts) {
  const concat = hexParts.map(h => h.replace(/^0x/, '')).join('');
  return bytesToHex(keccak_256(hexToBytes(concat)));
}

function domainSeparatorHex(eip712Name, eip712Version, chainId, verifyingContract) {
  const nameHash = bytesToHex(keccak_256(new TextEncoder().encode(eip712Name)));
  const versionHash = bytesToHex(keccak_256(new TextEncoder().encode(eip712Version)));
  const eip712DomainTypeHash = bytesToHex(keccak_256(new TextEncoder().encode(
    'EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)'
  )));
  return keccakHex(
    eip712DomainTypeHash,
    nameHash,
    versionHash,
    pad32(BigInt(chainId).toString(16)),
    addressTo32(verifyingContract),
  );
}

function structHashHex(auth) {
  return keccakHex(
    TRANSFER_WITH_AUTH_TYPEHASH_HEX,
    addressTo32(auth.from),
    addressTo32(auth.to),
    pad32(BigInt(auth.value).toString(16)),
    pad32(BigInt(auth.validAfter).toString(16)),
    pad32(BigInt(auth.validBefore).toString(16)),
    nonceToHex(auth.nonce),
  );
}

function digestHex(domainSepHex, structHashHex_) {
  const concat = '1901' + domainSepHex + structHashHex_;
  return bytesToHex(keccak_256(hexToBytes(concat)));
}

// --- signer factory ---

export function eip3009Signer(privateKeyHex) {
  const pk = String(privateKeyHex || '').replace(/^0x/, '');
  if (!/^[0-9a-fA-F]{64}$/.test(pk)) {
    throw new RosettaError(ErrorCode.ERR_INVALID_PRIVATE_KEY, 'privateKey must be 0x + 64 hex chars');
  }
  const pkBytes = hexToBytes(pk);
  const pubKey = secp256k1.getPublicKey(pkBytes, false); // uncompressed
  const addrBytes = keccak_256(pubKey.slice(1)).slice(-20);
  const address = getAddress('0x' + bytesToHex(addrBytes));

  return {
    type: 'eip3009',
    address,

    // Build + sign in one call. Caller passes the PaymentRequirements.
    // eip712Override lets the caller specify a domain {name, version} when
    // the 402 envelope ships them in `extra` (production hivemorph does this).
    async sign({ network, asset, amount, recipient, validAfter = 0, validBefore, nonce, eip712Override }) {
      assertRecipient(recipient);
      const meta = resolveAsset(network, asset);
      const eip712 = eip712Override && eip712Override.name && eip712Override.version
        ? eip712Override
        : meta.eip712;
      const chainId = caip2ToChainId(network);
      if (chainId == null) {
        throw new RosettaError(ErrorCode.ERR_UNSUPPORTED_NETWORK, `Cannot derive chainId from CAIP-2: ${network}`);
      }
      const _validBefore = validBefore ?? (Math.floor(Date.now() / 1000) + 600);
      assertValidBefore(_validBefore);
      const _nonce = nonce ?? randomNonce();

      const auth = {
        from: address,
        to: recipient,
        value: BigInt(amount).toString(),
        validAfter: BigInt(validAfter).toString(),
        validBefore: BigInt(_validBefore).toString(),
        nonce: typeof _nonce === 'string' ? _nonce : '0x' + nonceToHex(_nonce),
      };

      const domainSep = domainSeparatorHex(eip712.name, eip712.version, chainId, meta.address);
      const sh = structHashHex(auth);
      const digest = digestHex(domainSep, sh);

      const sig = secp256k1.sign(hexToBytes(digest), pkBytes, { lowS: true });
      const r = sig.r.toString(16).padStart(64, '0');
      const s = sig.s.toString(16).padStart(64, '0');
      const v = (sig.recovery === 0 ? 27 : 28).toString(16).padStart(2, '0');

      return {
        scheme: 'exact',
        network,
        payload: {
          authorization: auth,
          signature: '0x' + r + s + v,
        },
      };
    },
  };
}

function caip2ToChainId(caip2) {
  if (caip2 === CAIP2.BASE_MAINNET) return 8453;
  if (caip2 === CAIP2.BASE_SEPOLIA) return 84532;
  return null;
}

export function randomNonce() {
  const buf = new Uint8Array(32);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(buf);
  } else {
    // Node fallback
    // eslint-disable-next-line global-require
    const { randomBytes } = require('crypto');
    buf.set(randomBytes(32));
  }
  return '0x' + bytesToHex(buf);
}

// Exposed for tests + hive-flavored package.
export const __internal = {
  domainSeparatorHex,
  structHashHex,
  digestHex,
  caip2ToChainId,
  TRANSFER_WITH_AUTH_TYPEHASH_HEX,
};
