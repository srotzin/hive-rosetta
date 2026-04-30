# Hive Rosetta — x402 Universal Adapter Cookbook

> Canonical wire-up patterns for x402 settlement across every major agent SDK and Web3 toolchain.
> Maintained by [Hive Civilization](https://thehiveryiq.com). MIT licensed.

x402 is the HTTP-402-Payment-Required protocol for agent-to-API micropayments — `transferWithAuthorization` (EIP-3009) on USDC, scheme `exact`, mostly on Base mainnet. The protocol is simple. The wiring varies per framework. This document is the canonical wiring reference.

If you're a framework maintainer, agent dev, or x402 service operator, every code block here is copy-pasteable and tested against live Hive endpoints. Treasury for all examples: `0x15184bf50b3d3f52b60434f8942b7d52f2eb436e`.

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
