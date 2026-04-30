// Header read/write helpers covering v1↔v2 compatibility surface.
// Hive constraint #14: middleware.py reads X-Payment / x-payment / X-PAYMENT.
// Rosetta accepts all three on input, and emits v2 names on output by default.
// In dual-emit mode (protocolVersion === 'both') we emit BOTH v1 and v2 names.

import {
  HEADER_PAYMENT_REQUIRED,
  HEADER_PAYMENT_SIGNATURE,
  HEADER_PAYMENT_RESPONSE,
  HEADER_V1_INPUT_VARIANTS,
  HEADER_V1_DEFAULT_OUTPUT,
} from './version.js';
import { RosettaError, ErrorCode } from './errors.js';

const DECODER = typeof TextDecoder !== 'undefined' ? new TextDecoder() : null;

// Case-insensitive header read across a Headers, plain object, or Map.
function readRaw(source, candidates) {
  if (!source) return null;
  // Headers (Web Fetch)
  if (typeof source.get === 'function') {
    for (const name of candidates) {
      const v = source.get(name) ?? source.get(name.toLowerCase());
      if (v != null) return v;
    }
    return null;
  }
  // Map
  if (source instanceof Map) {
    for (const name of candidates) {
      if (source.has(name)) return source.get(name);
      if (source.has(name.toLowerCase())) return source.get(name.toLowerCase());
    }
    return null;
  }
  // Plain object
  const lowerMap = {};
  for (const k of Object.keys(source)) lowerMap[k.toLowerCase()] = source[k];
  for (const name of candidates) {
    if (lowerMap[name.toLowerCase()] != null) return lowerMap[name.toLowerCase()];
  }
  return null;
}

function decodeBase64Json(b64) {
  if (b64 == null) return null;
  // Node Buffer or browser atob — prefer Buffer where available (no atob in some Node modes).
  let raw;
  if (typeof Buffer !== 'undefined') {
    raw = Buffer.from(String(b64), 'base64').toString('utf8');
  } else {
    raw = DECODER.decode(Uint8Array.from(atob(String(b64)), c => c.charCodeAt(0)));
  }
  try {
    return JSON.parse(raw);
  } catch (e) {
    throw new RosettaError(
      ErrorCode.ERR_MALFORMED_HEADER,
      `Header value is not valid Base64-encoded JSON`,
      { sample: String(b64).slice(0, 64) },
    );
  }
}

function encodeBase64Json(value) {
  const json = JSON.stringify(value);
  if (typeof Buffer !== 'undefined') return Buffer.from(json, 'utf8').toString('base64');
  // browser
  return btoa(unescape(encodeURIComponent(json)));
}

// PAYMENT-REQUIRED: v2 = Base64-encoded JSON. v1 was sent as raw JSON in the
// 402 body (not a header), but we accept it here too if a caller pipes it in.
export function readPaymentRequired(headersOrObj) {
  const v2 = readRaw(headersOrObj, [HEADER_PAYMENT_REQUIRED]);
  if (v2) return decodeBase64Json(v2);
  return null;
}

export function writePaymentRequired(target, value) {
  setHeader(target, HEADER_PAYMENT_REQUIRED, encodeBase64Json(value));
}

// PAYMENT-SIGNATURE: v2 = Base64-encoded JSON. v1 = X-Payment (raw or Base64).
// We accept all three names on input. Spec says v2 is Base64-JSON; v1 in the
// wild was Base64-JSON since x402 v1.0 — so the decode path is identical.
export function readPaymentSignature(headersOrObj) {
  const candidates = [HEADER_PAYMENT_SIGNATURE, ...HEADER_V1_INPUT_VARIANTS];
  const raw = readRaw(headersOrObj, candidates);
  if (raw == null) return null;
  return decodeBase64Json(raw);
}

export function writePaymentSignature(target, value, opts = {}) {
  const protocolVersion = opts.protocolVersion ?? 2;
  const encoded = encodeBase64Json(value);
  if (protocolVersion === 1) {
    setHeader(target, HEADER_V1_DEFAULT_OUTPUT, encoded);
  } else if (protocolVersion === 2) {
    setHeader(target, HEADER_PAYMENT_SIGNATURE, encoded);
  } else if (protocolVersion === 'both') {
    setHeader(target, HEADER_V1_DEFAULT_OUTPUT, encoded);
    setHeader(target, HEADER_PAYMENT_SIGNATURE, encoded);
  } else {
    throw new RosettaError(
      ErrorCode.ERR_INVALID_VERSION,
      `protocolVersion must be 1, 2, or 'both'`,
      { value: protocolVersion },
    );
  }
}

// PAYMENT-RESPONSE: v2 = Base64-encoded JSON of settlement result.
export function readPaymentResponse(headersOrObj) {
  const raw = readRaw(headersOrObj, [HEADER_PAYMENT_RESPONSE]);
  return raw == null ? null : decodeBase64Json(raw);
}

export function writePaymentResponse(target, value) {
  setHeader(target, HEADER_PAYMENT_RESPONSE, encodeBase64Json(value));
}

function setHeader(target, name, value) {
  if (target == null) throw new RosettaError(ErrorCode.ERR_MISSING_HEADER, 'header target is null');
  if (typeof target.set === 'function') {
    target.set(name, value);
    return;
  }
  if (target instanceof Map) {
    target.set(name, value);
    return;
  }
  // plain object
  target[name] = value;
}

// Used in tests + tooling.
export const __internal = { decodeBase64Json, encodeBase64Json };
