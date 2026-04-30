// Conformance: header read/write across v1↔v2 with case tolerance.
// Constraint #14: middleware.py reads X-Payment / x-payment / X-PAYMENT.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  readPaymentSignature, writePaymentSignature,
  readPaymentRequired, writePaymentRequired,
  readPaymentResponse, writePaymentResponse,
  HEADER_PAYMENT_SIGNATURE, HEADER_PAYMENT_RESPONSE,
} from '../src/index.js';

const sample = { scheme: 'exact', network: 'eip155:8453', payload: { test: true } };

test('headers: read v2 PAYMENT-SIGNATURE', () => {
  const headers = new Headers();
  writePaymentSignature(headers, sample, { protocolVersion: 2 });
  const back = readPaymentSignature(headers);
  assert.deepEqual(back, sample);
});

test('headers: read v1 X-Payment', () => {
  const headers = new Headers();
  writePaymentSignature(headers, sample, { protocolVersion: 1 });
  const back = readPaymentSignature(headers);
  assert.deepEqual(back, sample);
});

test('headers: dual emit produces both v1 and v2', () => {
  const headers = new Headers();
  writePaymentSignature(headers, sample, { protocolVersion: 'both' });
  assert.ok(headers.get('x-payment'), 'v1 header missing');
  assert.ok(headers.get(HEADER_PAYMENT_SIGNATURE.toLowerCase()), 'v2 header missing');
});

test('headers: read tolerates X-PAYMENT (uppercase)', () => {
  const obj = { 'X-PAYMENT': Buffer.from(JSON.stringify(sample)).toString('base64') };
  const back = readPaymentSignature(obj);
  assert.deepEqual(back, sample);
});

test('headers: read tolerates x-payment (lowercase)', () => {
  const obj = { 'x-payment': Buffer.from(JSON.stringify(sample)).toString('base64') };
  const back = readPaymentSignature(obj);
  assert.deepEqual(back, sample);
});

test('headers: read tolerates X-Payment (mixed)', () => {
  const obj = { 'X-Payment': Buffer.from(JSON.stringify(sample)).toString('base64') };
  const back = readPaymentSignature(obj);
  assert.deepEqual(back, sample);
});

test('headers: invalid base64 throws ERR_MALFORMED_HEADER', () => {
  const obj = { 'X-Payment': 'not-valid-base64-json###' };
  assert.throws(() => readPaymentSignature(obj), /ERR_MALFORMED_HEADER|not valid Base64/i);
});

test('headers: PAYMENT-REQUIRED roundtrip', () => {
  const headers = new Headers();
  const required = { x402Version: 2, accepts: [{ scheme: 'exact', network: 'eip155:8453' }] };
  writePaymentRequired(headers, required);
  const back = readPaymentRequired(headers);
  assert.deepEqual(back, required);
});

test('headers: PAYMENT-RESPONSE roundtrip', () => {
  const headers = new Headers();
  const settlement = { success: true, txHash: '0xabc', network: 'eip155:8453' };
  writePaymentResponse(headers, settlement);
  const back = readPaymentResponse(headers);
  assert.deepEqual(back, settlement);
});
