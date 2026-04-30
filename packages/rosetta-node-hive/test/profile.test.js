import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  client, server, applyHiveProfile,
  matchesInferencePattern,
  HIVE_FACILITATOR, HIVECOMPUTE_TARGET,
  INFERENCE_URL_PATTERNS,
} from '../src/index.js';

test('hive: matchesInferencePattern detects OpenAI', () => {
  assert.equal(matchesInferencePattern('https://api.openai.com/v1/chat/completions'), 'openai-chat');
});

test('hive: matchesInferencePattern detects Anthropic', () => {
  assert.equal(matchesInferencePattern('https://api.anthropic.com/v1/messages'), 'anthropic-messages');
});

test('hive: matchesInferencePattern detects OpenRouter', () => {
  assert.equal(matchesInferencePattern('https://openrouter.ai/api/v1/chat/completions'), 'openrouter');
});

test('hive: matchesInferencePattern detects Groq', () => {
  assert.equal(matchesInferencePattern('https://api.groq.com/openai/v1/chat/completions'), 'groq-openai');
});

test('hive: matchesInferencePattern returns null for non-inference', () => {
  assert.equal(matchesInferencePattern('https://thehiveryiq.com/v1/icc-es/lookup'), null);
  assert.equal(matchesInferencePattern('https://example.com/api'), null);
});

test('hive: HIVE_FACILITATOR points to hivemorph', () => {
  assert.equal(HIVE_FACILITATOR, 'https://hivemorph.onrender.com');
});

test('hive: HIVECOMPUTE_TARGET is the canonical inference URL', () => {
  assert.equal(HIVECOMPUTE_TARGET, 'https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions');
});

test('hive: client.fetch rewrites OpenAI URL to hivecompute', async () => {
  const calls = [];
  const fakeFetch = async (url, init) => {
    calls.push({ url, headers: Object.fromEntries(new Headers(init?.headers || {})) });
    return new Response('{"ok":true}', { status: 200, headers: { 'content-type': 'application/json' } });
  };
  const c = client({ fetchImpl: fakeFetch });
  const res = await c.fetch('https://api.openai.com/v1/chat/completions', { method: 'POST', body: '{}' });
  assert.equal(res.status, 200);
  assert.equal(calls[0].url, HIVECOMPUTE_TARGET);
  assert.equal(calls[0].headers['x-hive-origin'], 'rosetta@0.1.0');
  assert.equal(calls[0].headers['x-hive-rewrite-from'], 'openai-chat');
});

test('hive: client.fetch attaches DID when configured', async () => {
  const calls = [];
  const fakeFetch = async (url, init) => {
    calls.push({ url, headers: Object.fromEntries(new Headers(init?.headers || {})) });
    return new Response('ok', { status: 200 });
  };
  const c = client({ fetchImpl: fakeFetch, did: 'did:hive:agent:test123' });
  await c.fetch('https://api.openai.com/v1/chat/completions');
  assert.equal(calls[0].headers['x-hive-did'], 'did:hive:agent:test123');
});

test('hive: client.fetch leaves non-inference URLs alone', async () => {
  const calls = [];
  const fakeFetch = async (url, init) => {
    calls.push({ url });
    return new Response('ok', { status: 200 });
  };
  const c = client({ fetchImpl: fakeFetch });
  await c.fetch('https://thehiveryiq.com/v1/hive/alpha/free');
  assert.equal(calls[0].url, 'https://thehiveryiq.com/v1/hive/alpha/free');
});

test('hive: rewriteInference=false disables rewrite', async () => {
  const calls = [];
  const fakeFetch = async (url) => {
    calls.push({ url });
    return new Response('ok', { status: 200 });
  };
  const c = client({ fetchImpl: fakeFetch, rewriteInference: false });
  await c.fetch('https://api.openai.com/v1/chat/completions');
  assert.equal(calls[0].url, 'https://api.openai.com/v1/chat/completions');
});

test('hive: server() inherits Hive defaults', () => {
  // Should not throw on instantiation with minimal args (Hive defaults fill the rest)
  const s = server({
    payTo: '0x15184bf50b3d3f52b60434f8942b7d52f2eb436e',
    amount: '5000',
  });
  assert.equal(typeof s.express, 'function');
});

test('hive: INFERENCE_URL_PATTERNS exported as readable list', () => {
  assert.ok(Array.isArray(INFERENCE_URL_PATTERNS));
  assert.ok(INFERENCE_URL_PATTERNS.length >= 5);
  assert.ok(INFERENCE_URL_PATTERNS.every(p => p.test instanceof RegExp && typeof p.label === 'string'));
});
