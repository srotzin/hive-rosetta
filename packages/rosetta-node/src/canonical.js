// JSON canonicalization (JCS, RFC 8785, simplified).
// Stable key ordering + UTF-8 encoding, suitable for cross-platform signing.
//
// MUST stay byte-identical to hivebank/src/lib/canonical.js — any divergence
// silently breaks Spectral ZK ticket verification.

export function canonicalize(value) {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return '[' + value.map(canonicalize).join(',') + ']';
  }
  const keys = Object.keys(value).sort();
  const parts = [];
  for (const k of keys) {
    if (value[k] === undefined) continue;
    parts.push(JSON.stringify(k) + ':' + canonicalize(value[k]));
  }
  return '{' + parts.join(',') + '}';
}

export function canonicalBytes(value) {
  return Buffer.from(canonicalize(value), 'utf8');
}
