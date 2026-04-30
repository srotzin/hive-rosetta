// High-level client. Drop-in fetch wrapper that handles 402 → sign → retry.
//
// Defaults to v2 headers on emit, accepts v1 + v2 on read. In dual mode
// emits both for Hive-internal traffic during the rollover.

import { readPaymentSignature, writePaymentSignature, readPaymentResponse } from './headers.js';
import { RosettaError, ErrorCode } from './errors.js';
import { canonicalize } from './canonical.js';

export function client(opts = {}) {
  const {
    signer,
    facilitator,
    fetchImpl = (typeof fetch !== 'undefined' ? fetch : null),
    protocolVersion = 2,
    onSign,
    onSettle,
  } = opts;

  if (!fetchImpl) {
    throw new RosettaError(ErrorCode.ERR_INTERNAL ?? 'ERR_INTERNAL', 'No fetch implementation available; pass opts.fetchImpl');
  }

  return {
    async fetch(url, init = {}) {
      const first = await fetchImpl(url, init);
      if (first.status !== 402) return first;

      // Read the 402 body for accepts; spec puts requirements either in
      // PaymentRequired body or PAYMENT-REQUIRED header.
      const payload = await parse402Body(first);
      const accepts = payload?.accepts ?? [];
      if (accepts.length === 0) {
        throw new RosettaError(
          ErrorCode.ERR_NO_ACCEPTABLE_PAYMENT,
          '402 response had no accepts list',
          { url, status: first.status },
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
          { url },
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

      // Retry with payment header.
      const headers = new Headers(init.headers || {});
      writePaymentSignature(headers, signed, { protocolVersion });
      const retried = await fetchImpl(url, { ...init, headers });

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
