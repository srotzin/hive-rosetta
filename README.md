# hive-rosetta

> Open x402 v2 SDK. EIP-3009 on Base. Free forever.
>
> Two packages, two languages, byte-identical wire format. The Hive-flavored profile defaults inference traffic to [hivecompute](https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions) with mandatory spectral-ZK attestation on every response.

[![npm](https://img.shields.io/npm/v/@hive-civilization/rosetta.svg)](https://www.npmjs.com/package/@hive-civilization/rosetta)
[![pypi](https://img.shields.io/pypi/v/hive-rosetta.svg)](https://pypi.org/project/hive-rosetta/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## What this is

x402 is the HTTP-402-Payment-Required protocol for agent-to-API micropayments — `transferWithAuthorization` (EIP-3009) on USDC, scheme `exact`, mostly on Base mainnet. The protocol is simple. The wiring varies per framework. `hive-rosetta` is the canonical client/server SDK for that wiring.

It ships in two flavors:

| Package | npm | PyPI | Defaults |
|---|---|---|---|
| **Open core** | [`@hive-civilization/rosetta`](https://www.npmjs.com/package/@hive-civilization/rosetta) | [`hive-rosetta`](https://pypi.org/project/hive-rosetta/) | Bring your own signer, facilitator, recipient. No Hive lock-in. |
| **Hive-flavored** | [`@hive-civilization/rosetta-hive`](https://www.npmjs.com/package/@hive-civilization/rosetta-hive) | [`hive-rosetta-hive`](https://pypi.org/project/hive-rosetta-hive/) | Pre-wires hivemorph as facilitator, rewrites inference URLs to hivecompute, attaches DID/Beacon attribution. |

Both are MIT. The Hive-flavored profile is **free forever** — it's a funnel, not a paid surface.

## Install

```bash
npm install @hive-civilization/rosetta
# or, with Hive defaults
npm install @hive-civilization/rosetta-hive
```

```bash
pip install hive-rosetta
# or, with Hive defaults
pip install hive-rosetta-hive
```

## Quick start (Node, open mode)

```js
import { client, eip3009Signer } from '@hive-civilization/rosetta';

const c = client({
  signer: eip3009Signer(process.env.PRIVATE_KEY),
});

const res = await c.fetch('https://api.example.com/v1/paid/endpoint');
const data = await res.json();
```

The `c.fetch` call:
1. Sends the request unauthenticated.
2. If the server returns 402, parses the `accepts` envelope.
3. Picks the first `exact` scheme entry, signs an EIP-3009 transferWithAuthorization.
4. Retries the request with `PAYMENT-SIGNATURE` header (and v1 `X-Payment` for backward compatibility).
5. Returns the 200 response.

## Quick start (Python, open mode)

```python
import asyncio
from hive_rosetta import client, eip3009_signer

async def main():
    c = client(signer=eip3009_signer(private_key))
    res = await c.fetch("https://api.example.com/v1/paid/endpoint")
    print(await res.aread())

asyncio.run(main())
```

## Quick start (Hive flavor — the funnel)

```js
import { client } from '@hive-civilization/rosetta-hive';
import { eip3009Signer } from '@hive-civilization/rosetta';

const c = client({
  signer: eip3009Signer(process.env.PRIVATE_KEY),
  did: 'did:hive:agent:my-agent',  // optional; unlocks tier multipliers when registered
});

// This call gets routed through hivecompute for spectral-ZK attested inference:
const res = await c.fetch('https://api.openai.com/v1/chat/completions', {
  method: 'POST',
  body: JSON.stringify({ model: 'gpt-4o-mini', messages: [{ role: 'user', content: 'hello' }] }),
});
```

The Hive client adds:
- **Inference URL rewrites:** OpenAI / Anthropic / Together / OpenRouter / Fireworks / Groq → hivecompute. Same OpenAI-compatible response shape, plus an attached spectral-ZK ticket. ~$0.02/call. 100% margin to the Hive treasury, by design — that's how the funnel works.
- **DID attribution:** if you set `did`, every paid call surfaces under your tier in [Hive Audit](https://thehiveryiq.com/audit). Tier-verified DIDs get 8%–40% off and priority queue.
- **Mandatory spectral-ZK on every response.** Cryptographically provable behavior trace — the only x402 audit primitive that satisfies EU AI Act Article 12 + 13 enforceable August 2026.

## Server

```js
import express from 'express';
import { server } from '@hive-civilization/rosetta';

const app = express();

app.use('/v1/paid/*', server({
  payTo: '0xYourTreasury',
  network: 'eip155:8453',
  asset: 'USDC',
  amount: '5000',                                   // 0.005 USDC, 6-decimal atomic
  facilitator: 'https://your-facilitator.example',
}).express());

app.get('/v1/paid/data', (req, res) => res.json({ ok: true }));
```

## Wire format

x402 v2 specifies three Base64-encoded JSON headers:

| Header | Direction | Meaning |
|---|---|---|
| `PAYMENT-REQUIRED` | Server → Client (with 402) | The `accepts` envelope: schemes, networks, assets, amounts, recipients. |
| `PAYMENT-SIGNATURE` | Client → Server | The signed authorization. |
| `PAYMENT-RESPONSE` | Server → Client (with 200) | Settlement result: tx hash, network, success. |

For backward compatibility with x402 v1 deployments, `hive-rosetta` reads `X-Payment` / `x-payment` / `X-PAYMENT` on input and emits v2 names by default. Set `protocolVersion: 'both'` to dual-emit during a rollover window.

## Conformance

Both packages run a shared cross-language test suite (112 vectors at v0.1):

```bash
npm test                                      # Node
.venv/bin/python -m pytest                    # Python
```

The Node and Python signers produce **byte-identical signatures** for identical inputs. The canonical-form JSON output is byte-identical to [`hivetrust/src/lib/canonical.js`](https://github.com/srotzin/hivetrust). If those drift, spectral-ZK ticket verification breaks silently — so we test for it explicitly.

## Scope (v0.1)

In the box:
- **Chains:** Base mainnet (`eip155:8453`), Base Sepolia (`eip155:84532`).
- **Assets:** USDC (USD Coin v2), USDT (Tether USD v1) on Base mainnet.
- **Schemes:** `exact`.
- **Signers:** EIP-3009 (`transferWithAuthorization`).
- **Server adapters:** Express (Node), FastAPI middleware (Python).

Not in v0.1 (ships in v0.2+ as paying customers ask for it):
- Other chains (Solana, Algorand, Aptos, Hedera, Stellar, Sui, Keeta).
- Other schemes (`upto`, `batch-settlement`).
- Permit2, ERC-7710, EIP-1271 signers.
- Browser bundle, i18n, MCP/A2A transport adapters.

## Why this exists

There are 13 other x402 SDKs. They all do most of the things. None produce a cryptographically provable audit trail that satisfies EU AI Act Article 12 (logging) + Article 13 (transparency), enforceable August 2026. The Hive-flavored `rosetta-hive` package is the only one that does — because it routes through a substrate that bakes spectral-ZK attestation into every response.

If you're a framework maintainer, agent dev, or x402 service operator, you can use the open core and ignore Hive entirely. If you're a regulated agent — financial services, healthcare, EU markets — the Hive flavor is the path of lowest legal friction.

## Live endpoints

- Hivecompute (paid inference, spectral-ZK on every response): `https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions`
- Hivemorph facilitator: `https://hivemorph.onrender.com`
- Hivetrust (DID + tier resolver): `https://hivetrust.onrender.com`
- Hive Audit (the moat product): [`https://thehiveryiq.com/audit`](https://thehiveryiq.com/audit)

## License

MIT. See [LICENSE](LICENSE).

---

# Appendix — Universal Adapter Cookbook

> The following is the original `hive-rosetta` cookbook (v1.0.0). It documents how to wire x402 settlement across every major agent SDK and Web3 toolchain. Examples target the open core and the `thehiveryiq.com` endpoint family.

## Index

| Stack | Pattern | Section |
|---|---|---|
| Coinbase AgentKit | ActionProvider | [#agentkit](#coinbase-agentkit) |
| GOAT SDK | Plugin | [#goat](#goat-sdk) |
| LangGraph / LangChain | MCP adapter | [#langgraph](#langgraph--langchain) |
| Microsoft AutoGen | Tool | [#autogen](#microsoft-autogen) |
| CrewAI | Tool class | [#crewai](#crewai) |
| Google ADK | MCPTool / RemoteAgent | [#adk](#google-adk) |
| ElizaOS | Plugin | [#eliza](#elizaos) |
| Mastra | Tool | [#mastra](#mastra) |
| Vercel AI SDK | Tool | [#vercel-ai](#vercel-ai-sdk) |
| OpenAI Agents | MCP server | [#openai-agents](#openai-agents-sdk) |
| MCP servers | Streamable-HTTP wrapper | [#mcp](#mcp-servers) |
| HuggingFace Transformers | Tool | [#transformers](#huggingface-transformers) |
| smolagents | Tool | [#smolagents](#smolagents) |
| Significant-Gravitas/AutoGPT | Block | [#autogpt](#autogpt) |
| BerriAI/LiteLLM | Function call | [#litellm](#litellm) |
| assistant-ui | Tool component | [#assistant-ui](#assistant-ui) |
| pydantic-ai | Tool | [#pydantic-ai](#pydantic-ai) |
| Cline | MCP config | [#cline](#cline) |
| SuperAGI | Tool | [#superagi](#superagi) |
| E2B | Sandbox call | [#e2b](#e2b) |
| Qwen-Agent | Tool | [#qwen-agent](#qwen-agent) |
| viem / wagmi | signTypedData | [#viem-wagmi](#viem--wagmi) |
| ethers.js | signTypedData | [#ethersjs](#ethersjs) |
| RainbowKit | Wallet UX | [#rainbowkit](#rainbowkit) |
| thirdweb | Auth | [#thirdweb](#thirdweb) |
| Alchemy aa-sdk | Account abstraction | [#aa-sdk](#alchemy-aa-sdk) |
| WalletConnect | Session signing | [#walletconnect](#walletconnect) |
| MetaMask Snap | Native flow | [#metamask-snap](#metamask-snap) |
| Safe core SDK | Multi-sig | [#safe](#safe) |
| ApeWorX | Python testing | [#ape](#ape) |
| Foundry | Forge tests | [#foundry](#foundry) |

---

## The protocol in three lines

A paid HTTP request to an x402-wired service:

```
GET /v1/some/resource HTTP/1.1
Host: hive-api.example.com
X-Payment: <eip-3009 transferWithAuthorization signature>
```

The server's facilitator validates the signature, settles USDC on-chain, then returns 200 with the payload. If `X-Payment` is missing, the server returns `402 Payment Required` with an `accepts` block telling the client where to pay, how much, and on which chain.

Every example below is the same protocol with framework-specific wrapping.

---

## Coinbase AgentKit

```ts
import { HiveActionProvider } from "@coinbase/agentkit";

const provider = new HiveActionProvider({
  endpoint: "https://thehiveryiq.com",
  payTo: "0x15184bf50b3d3f52b60434f8942b7d52f2eb436e",
});

agent.addProvider(provider);
```

Reference: [coinbase/agentkit#1157](https://github.com/coinbase/agentkit/pull/1157)

---

## GOAT SDK

```ts
import { hivePlugin } from "@goat-sdk/plugin-hive";

const tools = await getOnChainTools({
  wallet: viem(walletClient),
  plugins: [hivePlugin()],
});
```

Reference: [goat-sdk/goat#575](https://github.com/goat-sdk/goat/pull/575)

---

## LangGraph / LangChain

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "hive": {
        "url": "https://thehiveryiq.com/mcp",
        "transport": "streamable_http",
    }
})
tools = await client.get_tools()
```

The free tools work without payment. Paid tools auto-attach `X-Payment` via the user-supplied wallet adapter.

---

## Microsoft AutoGen

```python
from autogen_ext.tools.mcp import McpWorkbench, StreamableHttpServerParams

workbench = McpWorkbench(
    StreamableHttpServerParams(url="https://thehiveryiq.com/mcp")
)
```

---

## CrewAI

```python
from crewai_tools import BaseTool
import httpx

class HiveAlphaTool(BaseTool):
    name: str = "Hive Alpha Signals"
    description: str = "Free ALEO/USDC, USGS seismic, FRED housing. <800ms."
    def _run(self) -> str:
        return httpx.get("https://thehiveryiq.com/v1/hive/alpha/free").text
```

---

## Google ADK

```python
from google.adk.tools import MCPTool
from google.adk.agents import RemoteAgent

# As an MCP tool
hive_alpha = MCPTool(
    server_url="https://thehiveryiq.com/mcp",
    tool_name="get_alpha_signals",
)

# As a remote A2A agent
hive_agent = RemoteAgent(
    agent_card_url="https://thehiveryiq.com/.well-known/agent-card.json"
)
```

---

## ElizaOS

```ts
import { hiveEvaluator } from "@hivecivilization/eliza-plugin";

const character = {
  name: "MyAgent",
  evaluators: [hiveEvaluator],
  // ...
};
```

---

## Mastra

```ts
import { createTool } from "@mastra/core";

export const hiveAlpha = createTool({
  id: "hive-alpha",
  description: "Free Hive alpha feed",
  execute: async () => fetch("https://thehiveryiq.com/v1/hive/alpha/free").then(r => r.json()),
});
```

---

## Vercel AI SDK

```ts
import { tool } from "ai";
import { z } from "zod";

const hiveAlpha = tool({
  description: "Free Hive alpha feed",
  parameters: z.object({}),
  execute: async () => fetch("https://thehiveryiq.com/v1/hive/alpha/free").then(r => r.json()),
});
```

---

## OpenAI Agents SDK

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4o",
    tools=[{
        "type": "mcp",
        "server_label": "hive",
        "server_url": "https://thehiveryiq.com/mcp",
        "require_approval": "never",
    }],
    input="Get latest alpha signals from Hive",
)
```

---

## MCP servers

Every Hive surface is reachable as a remote MCP server via Streamable-HTTP:

```json
{
  "mcpServers": {
    "hive": {
      "url": "https://thehiveryiq.com/mcp",
      "transport": "streamable-http"
    }
  }
}
```

41 individual MCP shim repos at [github.com/srotzin](https://github.com/srotzin) (every Hive endpoint family).

---

## HuggingFace Transformers

```python
from transformers import pipeline
import requests

class HiveAlphaTool:
    def __call__(self):
        return requests.get("https://thehiveryiq.com/v1/hive/alpha/free").json()
```

---

## smolagents

```python
from smolagents import Tool

class HiveAlpha(Tool):
    name = "hive_alpha"
    description = "Free Hive alpha feed."
    def forward(self):
        import requests
        return requests.get("https://thehiveryiq.com/v1/hive/alpha/free").json()
```

---

## AutoGPT

Register as a Block in your AutoGPT instance:

```python
from autogpt.blocks import Block, BlockOutput

class HiveAlphaBlock(Block):
    def run(self, **kwargs) -> BlockOutput:
        import requests
        return BlockOutput(data=requests.get("https://thehiveryiq.com/v1/hive/alpha/free").json())
```

---

## LiteLLM

```python
import litellm

response = litellm.completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Get Hive alpha"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_hive_alpha",
            "description": "Free ALEO/USGS/FRED feed. <800ms.",
            "parameters": {"type": "object", "properties": {}},
        }
    }],
)
```

---

## assistant-ui

```tsx
import { makeAssistantTool } from "@assistant-ui/react";

const HiveAlphaTool = makeAssistantTool({
  toolName: "hive_alpha",
  description: "Free Hive alpha feed",
  execute: async () => fetch("https://thehiveryiq.com/v1/hive/alpha/free").then(r => r.json()),
});
```

---

## pydantic-ai

```python
from pydantic_ai import Agent

agent = Agent('openai:gpt-4o')

@agent.tool_plain
def hive_alpha() -> dict:
    """Free Hive alpha feed."""
    import httpx
    return httpx.get("https://thehiveryiq.com/v1/hive/alpha/free").json()
```

---

## Cline

`.vscode/cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "hive": {
      "url": "https://thehiveryiq.com/mcp",
      "transport": "streamable-http"
    }
  }
}
```

---

## SuperAGI

```python
from superagi.tools.base_tool import BaseTool

class HiveAlpha(BaseTool):
    name = "Hive Alpha"
    description = "Free Hive alpha feed"
    def _execute(self):
        import requests
        return requests.get("https://thehiveryiq.com/v1/hive/alpha/free").json()
```

---

## E2B

```python
from e2b_code_interpreter import Sandbox

sandbox = Sandbox()
result = sandbox.run_code("""
import requests
print(requests.get("https://thehiveryiq.com/v1/hive/alpha/free").json())
""")
```

---

## Qwen-Agent

```python
from qwen_agent.tools import BaseTool

class HiveAlpha(BaseTool):
    name = "hive_alpha"
    description = "Free Hive alpha feed"
    def call(self, params):
        import requests
        return requests.get("https://thehiveryiq.com/v1/hive/alpha/free").json()
```

---

## viem / wagmi

The signing primitive every x402 client needs:

```ts
import { walletClient } from "./wallet";

const signature = await walletClient.signTypedData({
  account,
  domain: {
    name: "USD Coin",
    version: "2",
    chainId: 8453,
    verifyingContract: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  },
  types: {
    TransferWithAuthorization: [
      { name: "from",        type: "address" },
      { name: "to",          type: "address" },
      { name: "value",       type: "uint256" },
      { name: "validAfter",  type: "uint256" },
      { name: "validBefore", type: "uint256" },
      { name: "nonce",       type: "bytes32" },
    ],
  },
  primaryType: "TransferWithAuthorization",
  message: {
    from: account.address,
    to: "0x15184bf50b3d3f52b60434f8942b7d52f2eb436e",
    value: 5000n, // $0.005 USDC (6 decimals)
    validAfter: 0n,
    validBefore: BigInt(Math.floor(Date.now() / 1000) + 60),
    nonce: crypto.getRandomValues(new Uint8Array(32)),
  },
});
```

That signature goes in the `X-Payment` header.

---

## ethers.js

```ts
const signature = await signer._signTypedData(domain, types, message);
```

Same `domain`, `types`, `message` as viem above.

---

## RainbowKit

RainbowKit handles the wallet UX layer; signing falls through to wagmi. Every connected wallet works with x402 through `useSignTypedData`.

---

## thirdweb

```ts
import { signTypedData } from "thirdweb/utils";
const sig = await signTypedData({ account, domain, types, message });
```

---

## Alchemy aa-sdk

```ts
import { createSmartAccountClient } from "@alchemy/aa-core";

const sig = await smartAccountClient.signTypedData({ domain, types, primaryType, message });
```

The smart account becomes the `from` address — paid calls settle from the AA wallet.

---

## WalletConnect

`wallet_signTypedData_v4` — same payload, routed through the WalletConnect session.

---

## MetaMask Snap

A Hive Snap can offer a one-tap "Pay $0.005 to Hive" UX with full receipt persistence. Reference: `MetaMask/snaps#3976`.

---

## Safe

Multi-sig wallets pay via Safe transactions. The `X-Payment` value becomes the Safe transaction signature. Useful for treasury-controlled agents.

---

## ApeWorX

Python testing of x402 flows:

```python
from ape import accounts, networks

def test_hive_payment():
    with networks.base.mainnet_fork.use_provider("foundry"):
        account = accounts.test_accounts[0]
        # build EIP-3009 transferWithAuthorization, send to facilitator
```

---

## Foundry

```solidity
function test_HivePayment() public {
    bytes memory payment = abi.encode(
        from, to, value, validAfter, validBefore, nonce, v, r, s
    );
    // forge calls /v1/hive/* with X-Payment header
}
```

---

## Live endpoints

- Free alpha feed: `https://thehiveryiq.com/v1/hive/alpha/free`
- Paid construction lookup: `https://thehiveryiq.com/v1/icc-es/lookup`
- Reputation: `https://hivetrust.onrender.com/v1/reputation/{did}`
- MCP root: `https://thehiveryiq.com/mcp`
- A2A card: `https://thehiveryiq.com/.well-known/agent-card.json`
- Pheromones: [hive-pheromones.onrender.com](https://hive-pheromones.onrender.com)
- Public Index preview: [hive-pheromones.onrender.com/index](https://hive-pheromones.onrender.com/index)

## Reference

- x402 spec: [github.com/coinbase/x402](https://github.com/coinbase/x402)
- USDC EIP-3009: [eips.ethereum.org/EIPS/eip-3009](https://eips.ethereum.org/EIPS/eip-3009)
- Hive launch threads: see the open PRs and issues across all 30+ repos linked above.

## License

MIT
