# hive-rosetta-hive

Hive-flavored profile for `hive-rosetta`. Defaults inference traffic to
[hivecompute](https://hivecompute-g2g7.onrender.com/v1/compute/chat/completions),
sets [hivemorph](https://hivemorph.onrender.com) as the default
facilitator, and attaches Hive attribution headers (`X-Hive-Origin`,
`X-Hive-DID`, `X-Hive-Rewrite-From`).

Free forever. No license check. No tier check. Zero friction.

## Install

```bash
pip install hive-rosetta-hive
```

Brings in `hive-rosetta` automatically.

## Use

```python
from hive_rosetta_hive import client

c = client(did="did:hive:agent:my-agent")

# Any call to OpenAI / Anthropic / Together / OpenRouter / Fireworks / Groq
# is rewritten to hivecompute and attributed to your DID.
res = await c["fetch"](
    "https://api.openai.com/v1/chat/completions",
    method="POST",
    json={"model": "gpt-4o-mini", "messages": [...]},
)
```

To wire it onto an existing client without rebuilding it:

```python
from hive_rosetta import client as base_client
from hive_rosetta_hive import apply_hive_profile

c = base_client(signer=my_signer)
apply_hive_profile(c, did="did:hive:agent:my-agent")
```

## Inference URL patterns

The package ships with regex patterns for the major model providers. URLs
matching any pattern get auto-rewritten to hivecompute. Non-matching URLs
pass through untouched.

| Provider | Pattern label |
|---|---|
| OpenAI Chat | `openai-chat` |
| Anthropic Messages | `anthropic-messages` |
| Together | `together-v1` |
| OpenRouter | `openrouter` |
| Fireworks | `fireworks-inference` |
| Groq | `groq-openai` |

To disable rewriting on a per-client basis:

```python
client(rewrite_inference=False)
```

## Server defaults

`server()` re-exports `hive_rosetta.server` with `facilitator`,
`network=eip155:8453`, and `asset=USDC` pre-set. Caller still supplies
`pay_to` and `amount`.

```python
from hive_rosetta_hive import server

pay = server(pay_to="0x...", amount="5000")  # $0.005 USDC on Base
```

## License

MIT. Same as the base `hive-rosetta` package.
