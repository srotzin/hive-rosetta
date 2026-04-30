// End-to-end: hit the LIVE hivecompute 402 endpoint, parse the envelope,
// build + sign a transferWithAuthorization for it, verify the signature is
// recoverable and shape-correct against ASSET_CHAIN_REGISTRY in production.
//
// We do NOT broadcast the signed payment (no real money spent). We only
// validate the SDK can produce a payload that matches what hivemorph's
// proof_validator.py expects.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  client, eip3009Signer,
  readPaymentRequired,
  HIVE_TREASURY_BASE,
} from '../src/index.js';
import { normalizeNetwork } from '../src/client.js';
import { __internal as signerInternal } from '../src/signer.js';

const SKIP_LIVE = process.env.SKIP_LIVE_TESTS === '1';
const TEST_PK = '0x' + '11'.repeat(32);

test('e2e: hivecompute returns a 402 with valid x402 envelope', { skip: SKIP_LIVE }, async () => {
  const res = await fetch(
    'https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions',
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4o-mini', messages: [{ role: 'user', content: 'ping' }] }),
    },
  );
  assert.equal(res.status, 402, `expected 402, got ${res.status}`);

  const body = await res.json();
  assert.ok(Array.isArray(body.accepts), 'accepts is array');
  assert.ok(body.accepts.length >= 1, 'at least one accepts entry');

  const choice = body.accepts[0];
  assert.equal(choice.scheme, 'exact');
  assert.equal(choice.payTo.toLowerCase(), HIVE_TREASURY_BASE.toLowerCase(), 'payTo == Hive treasury');
  assert.ok(choice.maxAmountRequired, 'has maxAmountRequired');
  assert.ok(choice.asset, 'has asset (contract address)');
  assert.equal(choice.extra?.assetTransferMethod, 'eip3009', 'eip3009 method declared');

  // Header form too (PAYMENT-REQUIRED present per spec).
  const headerVal = res.headers.get('payment-required');
  if (headerVal) {
    const decoded = readPaymentRequired(res.headers);
    assert.ok(Array.isArray(decoded?.accepts), 'PAYMENT-REQUIRED header decodes to envelope');
  }
});

test('e2e: SDK can sign a payment matching the hivecompute 402', { skip: SKIP_LIVE }, async () => {
  const res = await fetch(
    'https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions',
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4o-mini', messages: [{ role: 'user', content: 'ping' }] }),
    },
  );
  assert.equal(res.status, 402);
  const body = await res.json();
  const choice = body.accepts[0];

  const signer = eip3009Signer(TEST_PK);
  const network = normalizeNetwork(choice.network);
  const eip712Override = choice.extra && (choice.extra.name || choice.extra.version)
    ? { name: choice.extra.name, version: choice.extra.version }
    : undefined;

  const signed = await signer.sign({
    network,
    asset: choice.asset,
    amount: choice.maxAmountRequired,
    recipient: choice.payTo,
    eip712Override,
    validBefore: 9999999999,
    nonce: '0x' + 'bb'.repeat(32),
  });

  // Wire shape matches what hivemorph proof_validator expects.
  assert.equal(signed.scheme, 'exact');
  assert.equal(signed.network, 'eip155:8453');
  assert.equal(signed.payload.authorization.from.toLowerCase(), signer.address.toLowerCase());
  assert.equal(signed.payload.authorization.to.toLowerCase(), choice.payTo.toLowerCase());
  assert.equal(signed.payload.authorization.value, choice.maxAmountRequired);
  assert.equal(signed.payload.signature.length, 132); // 0x + 65*2

  // Recover address — full EIP-712 round-trip including production overrides.
  const ds = signerInternal.domainSeparatorHex(
    eip712Override?.name ?? 'USD Coin',
    eip712Override?.version ?? '2',
    8453,
    choice.asset,
  );
  const sh = signerInternal.structHashHex(signed.payload.authorization);
  const digest = signerInternal.digestHex(ds, sh);

  const { secp256k1 } = await import('@noble/curves/secp256k1');
  const { keccak_256 } = await import('@noble/hashes/sha3');
  const sigHex = signed.payload.signature.slice(2);
  const r = BigInt('0x' + sigHex.slice(0, 64));
  const s = BigInt('0x' + sigHex.slice(64, 128));
  const v = parseInt(sigHex.slice(128, 130), 16);
  const recovery = v - 27;
  const sig = new secp256k1.Signature(r, s).addRecoveryBit(recovery);
  const digestBytes = Uint8Array.from(Buffer.from(digest, 'hex'));
  const pub = sig.recoverPublicKey(digestBytes).toRawBytes(false);
  const recovered = '0x' + Array.from(keccak_256(pub.slice(1)).slice(-20), b => b.toString(16).padStart(2, '0')).join('');
  assert.equal(recovered.toLowerCase(), signer.address.toLowerCase(),
    'signature recovers to signer address using production EIP-712 domain');
});

test('normalizeNetwork: production names', () => {
  assert.equal(normalizeNetwork('base'), 'eip155:8453');
  assert.equal(normalizeNetwork('base-sepolia'), 'eip155:84532');
  assert.equal(normalizeNetwork('eip155:8453'), 'eip155:8453');
  assert.equal(normalizeNetwork('BASE'), 'eip155:8453');
});
