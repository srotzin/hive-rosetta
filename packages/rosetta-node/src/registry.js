// Chain + asset registry. v0.1 ships Base mainnet and Base Sepolia only.
// Adding chains is opt-in via chains.register; never silently extended.
//
// Aligned with hivemorph/hive_x402/payment_required.py ASSET_CHAIN_REGISTRY
// and the EIP-712 domains that hivemorph/broadcast/evm.py enforces.

import { RosettaError, ErrorCode } from './errors.js';

export const CAIP2 = Object.freeze({
  BASE_MAINNET: 'eip155:8453',
  BASE_SEPOLIA: 'eip155:84532',
});

// Hive treasury (EVM). REQUIRED_EVM_RECIPIENT in broadcast/evm.py.
export const HIVE_TREASURY_BASE = '0x15184bf50b3d3f52b60434f8942b7d52f2eb436e';

export const ASSETS = Object.freeze({
  // Base mainnet USDC (USD Coin v2). decimals=6.
  [CAIP2.BASE_MAINNET]: {
    'USDC': {
      address: '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913',
      decimals: 6,
      eip712: { name: 'USD Coin', version: '2' },
    },
    'USDT': {
      address: '0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2',
      decimals: 6,
      eip712: { name: 'Tether USD', version: '1' },
    },
  },
  [CAIP2.BASE_SEPOLIA]: {
    'USDC': {
      address: '0x036CbD53842c5426634e7929541eC2318f3dCF7e',
      decimals: 6,
      eip712: { name: 'USDC', version: '2' },
    },
  },
});

export function resolveAsset(network, symbolOrAddress) {
  const chain = ASSETS[network];
  if (!chain) {
    throw new RosettaError(
      ErrorCode.ERR_UNSUPPORTED_NETWORK,
      `Network not supported in v0.1: ${network}`,
      { network, supported: Object.keys(ASSETS) },
      'v0.1 supports Base mainnet (eip155:8453) and Base Sepolia (eip155:84532).',
    );
  }
  // Symbol lookup
  if (chain[symbolOrAddress]) return { ...chain[symbolOrAddress], symbol: symbolOrAddress };
  // Address lookup (case-insensitive)
  const lower = String(symbolOrAddress).toLowerCase();
  for (const [sym, meta] of Object.entries(chain)) {
    if (meta.address.toLowerCase() === lower) return { ...meta, symbol: sym };
  }
  throw new RosettaError(
    ErrorCode.ERR_UNSUPPORTED_ASSET,
    `Asset not registered for ${network}: ${symbolOrAddress}`,
    { network, asset: symbolOrAddress },
  );
}

// validBefore floor — Hive constraint: validBefore=9_999_999_999 sentinel
// is the canonical "no expiry" value used in production. Any value below
// (now + minimum lifetime) signals replay-window pressure and we reject.
export const VALIDBEFORE_SENTINEL = 9_999_999_999;
export const VALIDBEFORE_MIN_LIFETIME_SECONDS = 30;

export function assertValidBefore(validBefore, nowSeconds = Math.floor(Date.now() / 1000)) {
  if (validBefore === VALIDBEFORE_SENTINEL) return; // accepted sentinel
  if (validBefore < nowSeconds + VALIDBEFORE_MIN_LIFETIME_SECONDS) {
    throw new RosettaError(
      ErrorCode.ERR_VALIDBEFORE_TOO_LOW,
      `validBefore (${validBefore}) is below minimum lifetime floor`,
      { validBefore, now: nowSeconds, minimum: nowSeconds + VALIDBEFORE_MIN_LIFETIME_SECONDS },
      `Set validBefore to at least ${VALIDBEFORE_MIN_LIFETIME_SECONDS}s in the future, or use the sentinel ${VALIDBEFORE_SENTINEL}.`,
    );
  }
}

export function assertRecipient(addr) {
  if (typeof addr !== 'string' || !/^0x[0-9a-fA-F]{40}$/.test(addr)) {
    throw new RosettaError(
      ErrorCode.ERR_INVALID_RECIPIENT,
      `Recipient must be 0x-prefixed 40-hex EVM address`,
      { address: addr },
    );
  }
}
