// Conformance: EIP-3009 signer correctness.
// Critical: the produced signature must be recoverable to the signer's address
// using the canonical EIP-712 digest. Any byte change in domain, types, or
// message ABI order causes recovery to a different address.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { eip3009Signer, randomNonce, HIVE_TREASURY_BASE } from '../src/index.js';
import { __internal as signerInternal } from '../src/signer.js';
import { secp256k1 } from '@noble/curves/secp256k1';
import { keccak_256 } from '@noble/hashes/sha3';

const TEST_PK = '0x' + '11'.repeat(32);

function recoverAddress(digestHex, sigHex) {
  const r = BigInt('0x' + sigHex.slice(2, 66));
  const s = BigInt('0x' + sigHex.slice(66, 130));
  const v = parseInt(sigHex.slice(130, 132), 16);
  const recovery = v - 27;
  const sig = new secp256k1.Signature(r, s).addRecoveryBit(recovery);
  const digestBytes = Uint8Array.from(Buffer.from(digestHex.replace(/^0x/, ''), 'hex'));
  const pub = sig.recoverPublicKey(digestBytes).toRawBytes(false);
  return '0x' + Array.from(keccak_256(pub.slice(1)).slice(-20), b => b.toString(16).padStart(2, '0')).join('');
}

test('signer: produces recoverable EIP-3009 signature on Base USDC', async () => {
  const signer = eip3009Signer(TEST_PK);
  const out = await signer.sign({
    network: 'eip155:8453',
    asset: 'USDC',
    amount: '5000',
    recipient: HIVE_TREASURY_BASE,
    validBefore: 9999999999,
    nonce: '0x' + 'aa'.repeat(32),
  });
  assert.equal(out.scheme, 'exact');
  assert.equal(out.network, 'eip155:8453');
  assert.equal(out.payload.authorization.from, signer.address);
  assert.equal(out.payload.authorization.to, HIVE_TREASURY_BASE);
  assert.equal(out.payload.authorization.value, '5000');
  assert.equal(out.payload.signature.length, 132); // 0x + 65*2

  // Recover address from signature
  const ds = signerInternal.domainSeparatorHex('USD Coin', '2', 8453, '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913');
  const sh = signerInternal.structHashHex(out.payload.authorization);
  const digest = signerInternal.digestHex(ds, sh);
  const recovered = recoverAddress('0x' + digest, out.payload.signature);
  assert.equal(recovered.toLowerCase(), signer.address.toLowerCase());
});

test('signer: validates recipient', async () => {
  const signer = eip3009Signer(TEST_PK);
  await assert.rejects(
    () => signer.sign({
      network: 'eip155:8453',
      asset: 'USDC',
      amount: '5000',
      recipient: 'not-an-address',
      validBefore: 9999999999,
    }),
    /INVALID_RECIPIENT|ERR_INVALID_RECIPIENT/i,
  );
});

test('signer: rejects validBefore in past', async () => {
  const signer = eip3009Signer(TEST_PK);
  await assert.rejects(
    () => signer.sign({
      network: 'eip155:8453',
      asset: 'USDC',
      amount: '5000',
      recipient: HIVE_TREASURY_BASE,
      validBefore: 1, // ancient
    }),
    /VALIDBEFORE_TOO_LOW/,
  );
});

test('signer: accepts validBefore sentinel 9_999_999_999', async () => {
  const signer = eip3009Signer(TEST_PK);
  const out = await signer.sign({
    network: 'eip155:8453',
    asset: 'USDC',
    amount: '1',
    recipient: HIVE_TREASURY_BASE,
    validBefore: 9999999999,
    nonce: '0x' + 'ff'.repeat(32),
  });
  assert.equal(out.payload.authorization.validBefore, '9999999999');
});

test('signer: rejects bad private key', () => {
  assert.throws(() => eip3009Signer('not-a-key'), /INVALID_PRIVATE_KEY/);
  assert.throws(() => eip3009Signer('0x123'), /INVALID_PRIVATE_KEY/);
});

test('signer: randomNonce produces 32-byte hex', () => {
  const n = randomNonce();
  assert.match(n, /^0x[0-9a-f]{64}$/);
});

test('signer: typehash matches EIP-3009 canonical value', () => {
  // The TransferWithAuthorization typehash is invariant across all USDC
  // contracts. If this drifts, every signature breaks.
  // keccak256("TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)")
  assert.equal(
    signerInternal.TRANSFER_WITH_AUTH_TYPEHASH_HEX,
    '7c7c6cdb67a18743f49ec6fa9b35f50d52ed05cbed4cc592e13b44501c1a2267',
  );
});

test('signer: signs deterministically given fixed inputs', async () => {
  const a = eip3009Signer(TEST_PK);
  const b = eip3009Signer(TEST_PK);
  const params = {
    network: 'eip155:8453',
    asset: 'USDC',
    amount: '5000',
    recipient: HIVE_TREASURY_BASE,
    validBefore: 9999999999,
    nonce: '0x' + 'cc'.repeat(32),
  };
  const sig1 = await a.sign(params);
  const sig2 = await b.sign(params);
  assert.equal(sig1.payload.signature, sig2.payload.signature);
});
