// High-level client. Drop-in fetch wrapper that handles 402 → sign → retry.
//
// Defaults to v2 headers on emit, accepts v1 + v2 on read. In dual mode
// emits both for Hive-internal traffic during the rollover.
//
// v0.2.0 adds opt-in inference routing. When `routeInference: true`,
// requests to known inference endpoints (openai/anthropic/together/
// openrouter/fireworks/groq) are rewritten to the canonical hivecompute
// target before the first request, and the 402 retry hits the rewritten
// URL. When `routeInference: false` (default), behavior is identical
// to v0.1.0 — neutral signing utility, no rewriting, no Hive headers.

import { readPaymentSignature, writePaymentSignature, readPaymentResponse } from './headers.js';
import { RosettaError, ErrorCode } from './errors.js';
import { canonicalize } from './canonical.js';
import { HIVECOMPUTE_TARGET, matchesInferencePattern } from './routing.js';
import { PACKAGE_VERSION } from './version.js';

export function client(opts = {}) {
  const {
    signer,
    facilitator,
    fetchImpl = (typeof fetch !== 'undefined' ? fetch : null),
    protocolVersion = 2,
    onSign,
    onSettle,
    routeInference = false,
    did,
    onRewrite,
  } = opts;

  if (!fetchImpl) {
    throw new RosettaError(ErrorCode.ERR_INTERNAL ?? 'ERR_INTERNAL', 'No fetch implementation available; pass opts.fetchImpl');
  }

  return {
    async fetch(url, init = {}) {
      // ---- Phase 1: rewrite (opt-in only) ----
      let targetUrl = url;
      let rewriteLabel = null;
      if (routeInference) {
        const label = matchesInferencePattern(url);
        if (label !== null) {
          targetUrl = HIVECOMPUTE_TARGET;
          rewriteLabel = label;
          if (typeof onRewrite === 'function') {
            onRewrite({ from: url, to: targetUrl, label });
          }
        }
      }

      // Hive attribution headers attach only when routing is on AND a
      // rewrite actually happened. A non-matching URL with the flag on
      // gets no extra headers — clean bypass.
      const headers = new Headers(init.headers || {});
      if (rewriteLabel !== null) {
        headers.set('X-Hive-Origin', `rosetta@${PACKAGE_VERSION}`);
        headers.set('X-Hive-Rewrite-From', rewriteLabel);
        if (did) headers.set('X-Hive-DID', did);
      }

      const firstInit = { ...init, headers };
      const first = await fetchImpl(targetUrl, firstInit);
      if (first.status !== 402) return first;

      // Read the 402 body for accepts; spec puts requirements either in
      // PaymentRequired body or PAYMENT-REQUIRED header.
      const payload = await parse402Body(first);
      const accepts = payload?.accepts ?? [];
      if (accepts.length === 0) {
        throw new RosettaError(
          ErrorCode.ERR_NO_ACCEPTABLE_PAYMENT,
          '402 response had no accepts list',
          { url: targetUrl, status: first.status },
        );
      }

      // v0.1 negotiation: pick first 'exact' on a network we support.
      const choice = accepts.find(a => a.scheme === 'exact');
      if (!choice) {
        throw new RosettaError(
          ErrorCode.ERR_NO_ACCEPTABLE_PAYMENT,
          `No 'exact' scheme in 402 accepts (v0.1 supports exact only)`,
          { schemes: accepts.map(a => a.scheme) },
        );
      }

      if (!signer) {
        throw new RosettaError(
          ErrorCode.ERR_SIGNER_FAILED ?? 'ERR_SIGNER_FAILED',
          'Got 402 but no signer configured on client',
          { url: targetUrl },
        );
      }

      // Production envelope normalization. The hivemorph 402 emits
      // network='base' and asset=<contract address>; the spec also allows
      // network='eip155:8453'. We accept both and let the signer resolve.
      const network = normalizeNetwork(choice.network);
      const asset = choice.asset; // address or symbol; signer.sign() resolves
      const eip712Override = choice.extra && (choice.extra.name || choice.extra.version)
        ? { name: choice.extra.name, version: choice.extra.version }
        : undefined;

      const signed = await signer.sign({
        network,
        asset,
        amount: choice.maxAmountRequired ?? choice.amount,
        recipient: choice.payTo,
        eip712Override,
      });
      if (onSign) await onSign(signed);

      // Retry with payment header — CRITICAL: retry hits targetUrl
      // (the rewritten URL), not the original. This is the closed loop.
      // If routeInference rewrote openai → hivecompute, the signed retry
      // must hit hivecompute or the funnel earns nothing.
      const retryHeaders = new Headers(headers);
      writePaymentSignature(retryHeaders, signed, { protocolVersion });
      const retried = await fetchImpl(targetUrl, { ...init, headers: retryHeaders });

      const settlement = readPaymentResponse(retried.headers);
      if (settlement && onSettle) await onSettle(settlement);

      return retried;
    },

    async preview(required) {
      // Inspect what would be signed without actually signing.
      const accepts = required?.accepts ?? [];
      const choice = accepts.find(a => a.scheme === 'exact');
      if (!choice) return { acceptable: false, reason: 'no exact scheme available' };
      return {
        acceptable: true,
        scheme: 'exact',
        network: choice.network,
        amount: choice.maxAmountRequired ?? choice.amount,
        recipient: choice.payTo,
        canonical: canonicalize(choice),
      };
    },
  };
}

// Map common shorthand names to CAIP-2. The hivemorph production envelope
// uses 'base' / 'base-sepolia' (matches the public x402 v1 spec); CAIP-2 is
// the v2 form. We normalize on input so signer.sign always sees CAIP-2.
export function normalizeNetwork(net) {
  if (typeof net !== 'string') return net;
  const map = {
    'base': 'eip155:8453',
    'base-mainnet': 'eip155:8453',
    'base-sepolia': 'eip155:84532',
    'sepolia-base': 'eip155:84532',
  };
  if (map[net.toLowerCase()]) return map[net.toLowerCase()];
  return net; // already CAIP-2 or unknown
}

async function parse402Body(response) {
  // Try JSON first; some servers return the requirements as raw JSON body.
  const ct = response.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      // fallthrough
    }
  }
  // Fallback: read text and try to parse.
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
