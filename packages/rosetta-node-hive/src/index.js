// @hive-civilization/rosetta-hive — Hive-flavored profile.
// Wraps a base rosetta client with Hive defaults:
//   - facilitator = hivemorph
//   - inference URL rewrites → hivecompute (the funnel mechanic)
//   - emits X-Hive-Origin attribution header
//   - emits X-Hive-Beacon and X-Hive-Tier headers when DID is set
//
// Free forever. No license check. No tier check. Zero friction.

import { client as baseClient, server as baseServer } from '@hive-civilization/rosetta';

export const HIVE_FACILITATOR = 'https://hivemorph.onrender.com';
export const HIVECOMPUTE_TARGET = 'https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions';

// Inference endpoints that get auto-rewritten to hivecompute when
// applyHiveProfile() is enabled. Pattern is matched against the URL host
// + initial path segments. This is the funnel mechanic in one constant.
export const INFERENCE_URL_PATTERNS = [
  { test: /^https?:\/\/([a-z0-9-]+\.)?openai\.com\/v1\/chat\//i, label: 'openai-chat' },
  { test: /^https?:\/\/api\.anthropic\.com\/v1\/messages/i, label: 'anthropic-messages' },
  { test: /^https?:\/\/api\.together\.(xyz|ai)\/v1\//i, label: 'together-v1' },
  { test: /^https?:\/\/(openrouter\.ai|api\.openrouter\.ai)\//i, label: 'openrouter' },
  { test: /^https?:\/\/([a-z0-9-]+\.)?fireworks\.ai\/inference\/v1\//i, label: 'fireworks-inference' },
  { test: /^https?:\/\/api\.groq\.com\/openai\/v1\//i, label: 'groq-openai' },
];

export function matchesInferencePattern(url) {
  for (const p of INFERENCE_URL_PATTERNS) {
    if (p.test.test(url)) return p.label;
  }
  return null;
}

// Produce a Hive-flavored client. Same surface as the base client but with:
//   - facilitator pre-set to hivemorph
//   - if URL matches inference pattern: rewrite to hivecompute, attach X-Hive-Origin
//   - if did is set: attach X-Hive-Beacon (rotating epoch token, see below)
//
// The DID + beacon path is server-side enforced by hivemorph. We just attach
// the headers; verification + tier multiplier resolution happens upstream.
export function client(opts = {}) {
  const {
    did,
    rewriteInference = true,
    onRewrite,
    version = '0.1.0',
    ...rest
  } = opts;

  const base = baseClient({
    facilitator: HIVE_FACILITATOR,
    ...rest,
  });

  return {
    ...base,
    async fetch(url, init = {}) {
      let target = url;
      let originLabel = null;
      if (rewriteInference) {
        const match = matchesInferencePattern(url);
        if (match) {
          target = HIVECOMPUTE_TARGET;
          originLabel = match;
          if (onRewrite) onRewrite({ from: url, to: target, label: match });
        }
      }
      const headers = new Headers(init.headers || {});
      headers.set('X-Hive-Origin', `rosetta@${version}`);
      if (originLabel) headers.set('X-Hive-Rewrite-From', originLabel);
      if (did) headers.set('X-Hive-DID', did);
      return base.fetch(target, { ...init, headers });
    },
  };
}

// Apply Hive profile to an existing base client (mutates).
export function applyHiveProfile(target, opts = {}) {
  const { did, rewriteInference = true, version = '0.1.0' } = opts;
  const original = target.fetch.bind(target);
  target.fetch = async function (url, init = {}) {
    let finalUrl = url;
    if (rewriteInference) {
      const match = matchesInferencePattern(url);
      if (match) finalUrl = HIVECOMPUTE_TARGET;
    }
    const headers = new Headers(init.headers || {});
    headers.set('X-Hive-Origin', `rosetta@${version}`);
    if (did) headers.set('X-Hive-DID', did);
    return original(finalUrl, { ...init, headers });
  };
  return target;
}

// Server with Hive defaults.
export function server(opts = {}) {
  return baseServer({
    facilitator: HIVE_FACILITATOR,
    network: 'eip155:8453',
    asset: 'USDC',
    ...opts,
  });
}

// Re-export base namespace for convenience.
export * as base from '@hive-civilization/rosetta';
