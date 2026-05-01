# hive-rosetta

> Open x402 v2 SDK. EIP-3009 on Base. Free forever.

[![npm](https://img.shields.io/npm/v/hive-rosetta.svg)](https://www.npmjs.com/package/hive-rosetta)
[![pypi](https://img.shields.io/pypi/v/hive-rosetta.svg)](https://pypi.org/project/hive-rosetta/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## What this is

x402 is the HTTP-402-Payment-Required protocol for agent-to-API micropayments — `transferWithAuthorization` (EIP-3009) on USDC, scheme `exact`, mostly on Base mainnet. The protocol is simple. The wiring varies per framework. `hive-rosetta` is the canonical client/server SDK for that wiring.

One package, two languages, byte-identical wire format.

## Install

```bash
npm install hive-rosetta
```

```bash
pip install hive-rosetta
```

## Quick start — neutral mode

Bring your own signer, facilitator, recipient. No Hive lock-in.

```js
import { client, eip3009Signer } from 'hive-rosetta';

const c = client({
  signer: eip3009Signer(process.env.PRIVATE_KEY),
});

const res = await c.fetch('https://api.example.com/v1/paid/endpoint');
const data = await res.json();
```

```python
from hive_rosetta import client, eip3009_signer

c = client(signer=eip3009_signer(private_key=PRIVATE_KEY))
resp = await c["fetch"]("https://api.example.com/v1/paid/endpoint")
data = resp.json()
```

## Inference routing — opt-in

`hive-rosetta` includes an opt-in inference router. When `routeInference: true` (Node) or `route_inference=True` (Python) is set on the client, requests to known inference endpoints are rewritten to [hivecompute](https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions) — an x402-priced inference router with spectral-ZK attestation on every response.

The flag defaults to `false`. With the flag off, behavior is identical to the neutral SDK.

```js
import { client, eip3009Signer } from 'hive-rosetta';

const c = client({
  signer: eip3009Signer(process.env.PRIVATE_KEY),
  routeInference: true,                    // opt-in
  did: 'did:hive:agent:0x…',               // optional attribution
});

// This URL gets rewritten to hivecompute. The 402 retry is signed and
// settled on the rewritten URL. The original openai.com URL is never hit.
const res = await c.fetch('https://api.openai.com/v1/chat/completions', {
  method: 'POST',
  body: JSON.stringify({ model: 'gpt-4o', messages: [...] }),
  headers: { 'content-type': 'application/json' },
});
```

```python
from hive_rosetta import client, eip3009_signer

c = client(
    signer=eip3009_signer(private_key=PRIVATE_KEY),
    route_inference=True,                   # opt-in
    did="did:hive:agent:0x…",               # optional attribution
)

resp = await c["fetch"](
    "https://api.openai.com/v1/chat/completions",
    method="POST",
    json={"model": "gpt-4o", "messages": [...]},
)
```

### Patterns rewritten when `routeInference: true`

| Provider | Pattern | Label |
|---|---|---|
| OpenAI | `*.openai.com/v1/chat/*` | `openai-chat` |
| Anthropic | `*.anthropic.com/v1/messages` | `anthropic-messages` |
| Together | `*.together.{xyz,ai}/v1/*` | `together-v1` |
| OpenRouter | `*.openrouter.ai/*` | `openrouter` |
| Fireworks | `*.fireworks.ai/inference/v1/*` | `fireworks-inference` |
| Groq | `*.groq.com/openai/v1/*` | `groq-openai` |

URLs that don't match a pattern are passed through untouched, even when the flag is on.

### Headers attached on rewrite

When (and only when) a rewrite occurs, three attribution headers are added to the request:

- `X-Hive-Origin: rosetta@<version>`
- `X-Hive-Rewrite-From: <pattern-label>`
- `X-Hive-DID: <did>` — only if `did` was passed to `client()`

### Closed loop

When the server returns `402 Payment Required`, the client signs the EIP-3009 authorization from the `accepts[]` envelope and retries on the rewritten URL — not the original. This is the test that actually runs in [`test/routing.test.js`](test/routing.test.js) and [`tests/test_routing.py`](tests/test_routing.py).

## API

```ts
client({
  signer?,                  // EIP-3009 signer
  facilitator?: string,     // facilitator URL
  fetchImpl?,               // override fetch (Node) / httpx (Python via http_client)
  protocolVersion?: 1|2,    // default 2
  onSign?(signed),          // before retry
  onSettle?(receipt),       // after settlement
  // v0.2.0 — opt-in inference routing
  routeInference?: boolean, // default false
  did?: string,             // attribution DID
  onRewrite?({from,to,label}),
})
```

```python
client(
    signer=None,
    facilitator=None,
    protocol_version=2,
    on_sign=None,
    on_settle=None,
    http_client=None,
    # v0.2.0 — opt-in inference routing
    route_inference=False,
    did=None,
    on_rewrite=None,
)
```

## License

MIT. Free forever.
