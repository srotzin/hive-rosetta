# hive-rosetta

Open x402 v2 SDK for Python. v0.1: Base mainnet + Sepolia, EIP-3009, scheme=exact.

## Install

```bash
pip install hive-rosetta
```

## Usage

```python
from hive_rosetta import eip3009_signer, client, canonicalize

signer = eip3009_signer("0x" + "11" * 32)
c = client(signer=signer, facilitator="https://facilitator.example.com")
# response = await c.fetch("https://api.example.com/resource")
```

## License

MIT
