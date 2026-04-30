// Conformance: chain + asset registry, validBefore floor, recipient shape.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  resolveAsset, assertRecipient, assertValidBefore,
  CAIP2, ASSETS, HIVE_TREASURY_BASE, VALIDBEFORE_SENTINEL,
} from '../src/index.js';

test('registry: Hive treasury constant', () => {
  assert.equal(HIVE_TREASURY_BASE, '0x15184bf50b3d3f52b60434f8942b7d52f2eb436e');
});

test('registry: Base mainnet USDC by symbol', () => {
  const meta = resolveAsset(CAIP2.BASE_MAINNET, 'USDC');
  assert.equal(meta.address, '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913');
  assert.equal(meta.decimals, 6);
  assert.equal(meta.eip712.name, 'USD Coin');
  assert.equal(meta.eip712.version, '2');
});

test('registry: Base mainnet USDT by symbol', () => {
  const meta = resolveAsset(CAIP2.BASE_MAINNET, 'USDT');
  assert.equal(meta.eip712.name, 'Tether USD');
  assert.equal(meta.eip712.version, '1');
});

test('registry: Base Sepolia USDC', () => {
  const meta = resolveAsset(CAIP2.BASE_SEPOLIA, 'USDC');
  assert.equal(meta.address, '0x036CbD53842c5426634e7929541eC2318f3dCF7e');
});

test('registry: lookup by address', () => {
  const meta = resolveAsset(CAIP2.BASE_MAINNET, '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913');
  assert.equal(meta.symbol, 'USDC');
});

test('registry: unsupported network throws', () => {
  assert.throws(() => resolveAsset('eip155:1', 'USDC'), /UNSUPPORTED_NETWORK/);
});

test('registry: unsupported asset throws', () => {
  assert.throws(() => resolveAsset(CAIP2.BASE_MAINNET, 'UNICORN'), /UNSUPPORTED_ASSET/);
});

test('registry: assertRecipient accepts canonical Hive address', () => {
  assertRecipient(HIVE_TREASURY_BASE);
});

test('registry: assertRecipient rejects bad input', () => {
  assert.throws(() => assertRecipient('not-an-address'), /INVALID_RECIPIENT/);
  assert.throws(() => assertRecipient('0x123'), /INVALID_RECIPIENT/);
  assert.throws(() => assertRecipient(null), /INVALID_RECIPIENT/);
});

test('registry: validBefore sentinel accepted', () => {
  assertValidBefore(VALIDBEFORE_SENTINEL);
});

test('registry: validBefore in past rejected', () => {
  assert.throws(() => assertValidBefore(1, 1700000000), /VALIDBEFORE_TOO_LOW/);
});

test('registry: validBefore well in future accepted', () => {
  const now = 1700000000;
  assertValidBefore(now + 600, now);
});
