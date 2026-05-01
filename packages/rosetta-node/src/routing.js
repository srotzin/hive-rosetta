// Inference URL routing — opt-in funnel mechanic for hive-rosetta.
//
// When `routeInference: true` is set on the client, requests to known
// inference endpoints (OpenAI, Anthropic, Together, OpenRouter, Fireworks,
// Groq) are rewritten to the canonical hivecompute target. This is the
// funnel: third-party inference traffic gets settled through hivecompute,
// which is x402-priced and spectral-ZK-ticketed.
//
// The flag defaults to false. When false, this module is inert — no URL
// rewriting, no extra headers, identical behavior to the neutral base
// client. That guarantees upgrades from v0.1.0 are non-breaking.
//
// Mirrors rosetta-python/hive_rosetta/routing.py byte-for-byte.

// Canonical hivecompute target for rewritten inference traffic.
export const HIVECOMPUTE_TARGET = 'https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions';

// Hivemorph facilitator URL (used by server() helper, not by routing).
export const HIVE_FACILITATOR = 'https://hivemorph.onrender.com';

// Inference endpoints that get auto-rewritten to hivecompute when
// routeInference=true. Pattern matched against the full URL string.
// Must stay byte-aligned with rosetta-python/hive_rosetta/routing.py.
export const INFERENCE_URL_PATTERNS = [
  { test: /^https?:\/\/(?:[a-z0-9-]+\.)*openai\.com\/v1\/chat\//i, label: 'openai-chat' },
  { test: /^https?:\/\/(?:[a-z0-9-]+\.)*anthropic\.com\/v1\/messages/i, label: 'anthropic-messages' },
  { test: /^https?:\/\/(?:[a-z0-9-]+\.)*together\.(xyz|ai)\/v1\//i, label: 'together-v1' },
  { test: /^https?:\/\/(?:[a-z0-9-]+\.)*openrouter\.ai\//i, label: 'openrouter' },
  { test: /^https?:\/\/(?:[a-z0-9-]+\.)*fireworks\.ai\/inference\/v1\//i, label: 'fireworks-inference' },
  { test: /^https?:\/\/(?:[a-z0-9-]+\.)*groq\.com\/openai\/v1\//i, label: 'groq-openai' },
];

// Return the label of the first matching inference pattern, or null.
// Returns null for any URL that does not match a known inference endpoint,
// including the hivecompute target itself (so re-routing is idempotent).
export function matchesInferencePattern(url) {
  if (typeof url !== 'string') return null;
  for (const p of INFERENCE_URL_PATTERNS) {
    if (p.test.test(url)) return p.label;
  }
  return null;
}
