// Cannon tests for v0.2.0 opt-in inference routing.
//
// Test order matters. The 402-after-rewrite test is first because it is
// the test that proves the funnel earns. If the signed retry hits the
// original URL instead of the hivecompute target, the rewrite is
// cosmetic and the closed loop is broken. That is the failure mode
// that matters most.
//
// Best-architect-at-Google-or-Circle bar: every claim verified, every
// header asserted, every URL asserted, every bypass path tested.

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  client,
  matchesInferencePattern,
  HIVECOMPUTE_TARGET,
  HIVE_FACILITATOR,
  INFERENCE_URL_PATTERNS,
  PACKAGE_VERSION,
} from '../src/index.js';

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

function makeFetchRecorder(plan) {
  // plan: array of { status, body, headers? }
  const requests = [];
  let i = 0;
  const fetchImpl = async (url, init = {}) => {
    const headers = init.headers ? Object.fromEntries(new Headers(init.headers).entries()) : {};
    requests.push({ url, headers, init });
    if (i >= plan.length) {
      throw new Error(`unplanned fetch to ${url} (call #${i + 1})`);
    }
    const spec = plan[i++];
    const body = typeof spec.body === 'string' ? spec.body : JSON.stringify(spec.body ?? {});
    const respHeaders = new Headers(spec.headers || { 'content-type': 'application/json' });
    return {
      status: spec.status,
      headers: respHeaders,
      async json() { return JSON.parse(body); },
      async text() { return body; },
    };
  };
  return { fetchImpl, requests };
}

function makeSigner(record) {
  return {
    async sign({ network, asset, amount, recipient }) {
      record.push({ network, asset, amount, recipient });
      return {
        scheme: 'exact',
        network, asset,
        amount: String(amount),
        recipient,
        authorization: {
          from: '0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A',
          to: recipient,
          value: String(amount),
          validAfter: '0',
          validBefore: '9999999999',
          nonce: '0x' + '00'.repeat(32),
        },
        signature: '0x' + '00'.repeat(65),
      };
    },
  };
}

// -----------------------------------------------------------------------
// THE CRITICAL TEST: 402-after-rewrite
// -----------------------------------------------------------------------

test('402 retry hits rewritten URL not original (funnel earns)', async () => {
  const { fetchImpl, requests } = makeFetchRecorder([
    {
      status: 402,
      body: {
        x402Version: 1,
        accepts: [{
          scheme: 'exact',
          network: 'base',
          maxAmountRequired: '10000',
          asset: '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913',
          payTo: '0x15184Bf50B3d3F52b60434f8942b7D52F2eB436E',
          extra: { assetTransferMethod: 'eip3009' },
        }],
      },
    },
    { status: 200, body: { ok: true } },
  ]);

  const signs = [];
  const c = client({
    fetchImpl,
    signer: makeSigner(signs),
    routeInference: true,
  });

  const original = 'https://api.openai.com/v1/chat/completions';
  const resp = await c.fetch(original, { method: 'POST' });

  assert.equal(resp.status, 200);
  assert.equal(requests.length, 2, 'expected exactly first + retry');

  // First request hits hivecompute, NOT openai
  assert.equal(requests[0].url, HIVECOMPUTE_TARGET);
  assert.ok(!requests[0].url.includes('openai.com'));

  // CRITICAL: signed retry must hit hivecompute, not original openai URL
  assert.equal(
    requests[1].url, HIVECOMPUTE_TARGET,
    `signed retry must hit hivecompute, got ${requests[1].url} — funnel is broken`
  );
  assert.ok(!requests[1].url.includes('openai.com'));

  // Retry carries payment signature header
  const retryHeaderKeys = Object.keys(requests[1].headers).map(k => k.toLowerCase());
  const hasPaymentHeader =
    retryHeaderKeys.includes('payment-signature') || retryHeaderKeys.includes('x-payment');
  assert.ok(hasPaymentHeader,
    `retry must include payment header, got: ${Object.keys(requests[1].headers).join(',')}`);

  // Signer was called with canonical recipient
  assert.equal(signs.length, 1);
  assert.equal(signs[0].recipient, '0x15184Bf50B3d3F52b60434f8942b7D52F2eB436E');
});

// -----------------------------------------------------------------------
// Pattern coverage
// -----------------------------------------------------------------------

test('matchesInferencePattern positive cases', () => {
  const cases = [
    ['https://api.openai.com/v1/chat/completions', 'openai-chat'],
    ['https://eu.api.openai.com/v1/chat/completions', 'openai-chat'],
    ['https://api.anthropic.com/v1/messages', 'anthropic-messages'],
    ['https://api.together.xyz/v1/completions', 'together-v1'],
    ['https://api.together.ai/v1/chat/completions', 'together-v1'],
    ['https://openrouter.ai/api/v1/chat/completions', 'openrouter'],
    ['https://api.openrouter.ai/v1/chat/completions', 'openrouter'],
    ['https://api.fireworks.ai/inference/v1/chat/completions', 'fireworks-inference'],
    ['https://api.groq.com/openai/v1/chat/completions', 'groq-openai'],
  ];
  for (const [url, label] of cases) {
    assert.equal(matchesInferencePattern(url), label, `expected ${label} for ${url}`);
  }
});

test('matchesInferencePattern negative cases', () => {
  const cases = [
    'https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions',
    'https://example.com/v1/chat/completions',
    'https://api.openai.com/v1/embeddings',
    'https://api.openai.com/v1/files',
    'https://malicious-openai.com.evil.io/v1/chat/',
    '',
    'not-a-url',
  ];
  for (const url of cases) {
    assert.equal(matchesInferencePattern(url), null, `expected null for ${url}`);
  }
});

test('every pattern rewrites and attaches headers', async () => {
  const cases = [
    ['https://api.openai.com/v1/chat/completions', 'openai-chat'],
    ['https://api.anthropic.com/v1/messages', 'anthropic-messages'],
    ['https://api.together.xyz/v1/x', 'together-v1'],
    ['https://openrouter.ai/api/v1/x', 'openrouter'],
    ['https://api.fireworks.ai/inference/v1/chat', 'fireworks-inference'],
    ['https://api.groq.com/openai/v1/chat', 'groq-openai'],
  ];
  const did = 'did:hive:test:0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A';

  for (const [original, label] of cases) {
    const { fetchImpl, requests } = makeFetchRecorder([{ status: 200, body: { ok: true } }]);
    const c = client({ fetchImpl, routeInference: true, did });
    await c.fetch(original);

    assert.equal(requests.length, 1);
    assert.equal(requests[0].url, HIVECOMPUTE_TARGET, `${original} → ${requests[0].url}`);
    assert.equal(requests[0].headers['x-hive-origin'], `rosetta@${PACKAGE_VERSION}`);
    assert.equal(requests[0].headers['x-hive-rewrite-from'], label);
    assert.equal(requests[0].headers['x-hive-did'], did);
  }
});

// -----------------------------------------------------------------------
// Bypass paths
// -----------------------------------------------------------------------

test('routeInference: false is total bypass', async () => {
  const { fetchImpl, requests } = makeFetchRecorder([{ status: 200, body: { ok: true } }]);
  const c = client({ fetchImpl, routeInference: false, did: 'did:hive:test:will-not-attach' });

  const original = 'https://api.openai.com/v1/chat/completions';
  await c.fetch(original);

  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, original);
  assert.equal(requests[0].headers['x-hive-origin'], undefined);
  assert.equal(requests[0].headers['x-hive-did'], undefined);
  assert.equal(requests[0].headers['x-hive-rewrite-from'], undefined);
});

test('routeInference defaults to off', async () => {
  const { fetchImpl, requests } = makeFetchRecorder([{ status: 200, body: { ok: true } }]);
  const c = client({ fetchImpl }); // no flag
  const original = 'https://api.openai.com/v1/chat/completions';
  await c.fetch(original);
  assert.equal(requests[0].url, original);
  assert.equal(requests[0].headers['x-hive-origin'], undefined);
});

test('non-inference URL with flag on is clean', async () => {
  const { fetchImpl, requests } = makeFetchRecorder([{ status: 200, body: { ok: true } }]);
  const c = client({ fetchImpl, routeInference: true, did: 'did:hive:should-not-leak' });
  const original = 'https://example.com/api/something';
  await c.fetch(original);
  assert.equal(requests[0].url, original);
  assert.equal(requests[0].headers['x-hive-origin'], undefined);
  assert.equal(requests[0].headers['x-hive-did'], undefined);
  assert.equal(requests[0].headers['x-hive-rewrite-from'], undefined);
});

test('did omitted does not attach DID header', async () => {
  const { fetchImpl, requests } = makeFetchRecorder([{ status: 200, body: { ok: true } }]);
  const c = client({ fetchImpl, routeInference: true });
  await c.fetch('https://api.openai.com/v1/chat/completions');

  assert.equal(requests[0].url, HIVECOMPUTE_TARGET);
  assert.equal(requests[0].headers['x-hive-origin'], `rosetta@${PACKAGE_VERSION}`);
  assert.equal(requests[0].headers['x-hive-rewrite-from'], 'openai-chat');
  assert.equal(requests[0].headers['x-hive-did'], undefined);
});

// -----------------------------------------------------------------------
// Idempotence + callback
// -----------------------------------------------------------------------

test('two fetches do not accumulate headers', async () => {
  const { fetchImpl, requests } = makeFetchRecorder([
    { status: 200, body: { ok: true } },
    { status: 200, body: { ok: true } },
  ]);
  const c = client({ fetchImpl, routeInference: true, did: 'did:hive:test' });

  await c.fetch('https://api.openai.com/v1/chat/completions');
  await c.fetch('https://example.com/foo');

  assert.equal(requests[0].url, HIVECOMPUTE_TARGET);
  assert.equal(requests[0].headers['x-hive-did'], 'did:hive:test');

  assert.equal(requests[1].url, 'https://example.com/foo');
  assert.equal(requests[1].headers['x-hive-did'], undefined);
  assert.equal(requests[1].headers['x-hive-origin'], undefined);
});

test('onRewrite callback fires with payload', async () => {
  const { fetchImpl } = makeFetchRecorder([{ status: 200, body: { ok: true } }]);
  const calls = [];
  const c = client({
    fetchImpl, routeInference: true,
    onRewrite: (info) => calls.push(info),
  });

  const original = 'https://api.anthropic.com/v1/messages';
  await c.fetch(original);

  assert.equal(calls.length, 1);
  assert.equal(calls[0].from, original);
  assert.equal(calls[0].to, HIVECOMPUTE_TARGET);
  assert.equal(calls[0].label, 'anthropic-messages');
});

test('onRewrite does not fire when no rewrite', async () => {
  const { fetchImpl } = makeFetchRecorder([{ status: 200, body: { ok: true } }]);
  const calls = [];
  const c = client({
    fetchImpl, routeInference: true,
    onRewrite: (info) => calls.push(info),
  });
  await c.fetch('https://example.com/foo');
  assert.equal(calls.length, 0);
});

// -----------------------------------------------------------------------
// Constants surface
// -----------------------------------------------------------------------

test('HIVECOMPUTE_TARGET is canonical', () => {
  assert.equal(HIVECOMPUTE_TARGET, 'https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions');
});

test('HIVE_FACILITATOR is canonical', () => {
  assert.equal(HIVE_FACILITATOR, 'https://hivemorph.onrender.com');
});

test('INFERENCE_URL_PATTERNS has 6 entries', () => {
  assert.equal(INFERENCE_URL_PATTERNS.length, 6);
});
