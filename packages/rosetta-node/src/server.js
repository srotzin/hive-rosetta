// Express middleware for serving 402 responses. v0.1 covers the express
// adapter only; Fastify/Hono/Next/MCP/A2A defer to v0.2.

import { readPaymentSignature, writePaymentResponse } from './headers.js';
import { canonicalize } from './canonical.js';
import { RosettaError, ErrorCode } from './errors.js';
import { assertRecipient, resolveAsset } from './registry.js';

export function server(opts = {}) {
  const {
    payTo,
    network,
    asset,
    amount,
    facilitator,
    freePaths = [],
    protocolVersion = 2,
    description = '',
    fetchImpl = (typeof fetch !== 'undefined' ? fetch : null),
  } = opts;

  if (!payTo) throw new RosettaError(ErrorCode.ERR_INVALID_RECIPIENT, 'server() requires payTo');
  assertRecipient(payTo);
  resolveAsset(network, asset); // validate now, fail fast
  if (!facilitator) throw new RosettaError(ErrorCode.ERR_FACILITATOR_UNREACHABLE, 'server() requires facilitator URL');

  function buildPaymentRequired(req) {
    const dynamicAmount = typeof amount === 'function' ? amount(req) : amount;
    return {
      x402Version: 2,
      accepts: [
        {
          scheme: 'exact',
          network,
          asset,
          maxAmountRequired: String(dynamicAmount),
          payTo,
          resource: req.originalUrl || req.url,
          description,
          mimeType: 'application/json',
        },
      ],
    };
  }

  return {
    express() {
      return async (req, res, next) => {
        try {
          if (freePaths.includes(req.path)) return next();
          const sig = readPaymentSignature(req.headers);
          if (!sig) {
            const body = buildPaymentRequired(req);
            res.status(402)
              .setHeader('content-type', 'application/json')
              .send(canonicalize(body));
            return;
          }

          // Forward signature to facilitator for verify+settle.
          const verifyUrl = facilitator.replace(/\/$/, '') + '/verify';
          const settleUrl = facilitator.replace(/\/$/, '') + '/settle';
          const verifyRes = await fetchImpl(verifyUrl, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ paymentPayload: sig, paymentRequirements: buildPaymentRequired(req).accepts[0] }),
          });
          if (!verifyRes.ok) {
            res.status(402)
              .setHeader('content-type', 'application/json')
              .send(JSON.stringify({ error: 'facilitator verify rejected', status: verifyRes.status }));
            return;
          }

          const settleRes = await fetchImpl(settleUrl, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ paymentPayload: sig, paymentRequirements: buildPaymentRequired(req).accepts[0] }),
          });
          const settlement = await settleRes.json().catch(() => ({}));
          if (settlement && settlement.success !== false) {
            writePaymentResponse(res, settlement);
          }
          next();
        } catch (e) {
          next(e);
        }
      };
    },
  };
}
