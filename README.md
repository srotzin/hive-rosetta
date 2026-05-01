# hive-rosetta

> Open x402 v2 SDK. EIP-3009 on Base. Free forever.

One package, two languages, byte-identical wire format.

[![npm](https://img.shields.io/npm/v/hive-rosetta.svg)](https://www.npmjs.com/package/hive-rosetta)
[![pypi](https://img.shields.io/pypi/v/hive-rosetta.svg)](https://pypi.org/project/hive-rosetta/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Install

```bash
npm install hive-rosetta
pip install hive-rosetta
```

## What this is

x402 is the HTTP-402-Payment-Required protocol for agent-to-API micropayments — `transferWithAuthorization` (EIP-3009) on USDC, scheme `exact`, mostly on Base mainnet. The protocol is simple. The wiring varies per framework. `hive-rosetta` is the canonical client/server SDK for that wiring.

## Two modes — same package

### Neutral

Bring your own signer, facilitator, recipient. No Hive lock-in.

```js
import { client, eip3009Signer } from 'hive-rosetta';
const c = client({ signer: eip3009Signer(process.env.PRIVATE_KEY) });
const res = await c.fetch('https://api.example.com/v1/paid/endpoint');
```

### Inference routing (opt-in, v0.2.0)

When `routeInference: true`, requests to known inference endpoints
(OpenAI, Anthropic, Together, OpenRouter, Fireworks, Groq) are rewritten
to [hivecompute](https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions)
— x402-priced inference with spectral-ZK attestation on every response.

```js
const c = client({
  signer: eip3009Signer(process.env.PRIVATE_KEY),
  routeInference: true,
});
const res = await c.fetch('https://api.openai.com/v1/chat/completions', { method: 'POST', ... });
// → URL rewritten to hivecompute, 402 signed and retried on the rewritten URL
```

```python
c = client(signer=eip3009_signer(private_key=PRIVATE_KEY), route_inference=True)
resp = await c["fetch"]("https://api.openai.com/v1/chat/completions", method="POST", ...)
```

The flag defaults to `false`. With the flag off, behavior is identical to the neutral SDK.

See [`packages/rosetta-node/README.md`](packages/rosetta-node/README.md) for the full API.

## Hive Civilization North Star

`hive-rosetta` is the open foundation. Hive Civilization's paid surfaces — HiveAudit, HiveCompliance filing, HiveCredential, HiveDNA Certification — sit on top of this protocol layer. The protocol is free forever. The compliance, attestation, and certification surfaces above it are where Hive earns.

## License

MIT.
