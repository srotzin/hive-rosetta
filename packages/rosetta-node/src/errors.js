// Structured errors with stable codes. Subset shipped at v0.1 covers the paths
// that v0.1 code can actually raise. Adding codes is non-breaking; renaming
// or renumbering existing codes is breaking — never do it.

export const ErrorCode = Object.freeze({
  // protocol shape
  ERR_INVALID_VERSION: 'ERR_INVALID_VERSION',
  ERR_MISSING_HEADER: 'ERR_MISSING_HEADER',
  ERR_MALFORMED_HEADER: 'ERR_MALFORMED_HEADER',

  // chains & networks
  ERR_UNSUPPORTED_NETWORK: 'ERR_UNSUPPORTED_NETWORK',
  ERR_UNSUPPORTED_ASSET: 'ERR_UNSUPPORTED_ASSET',
  ERR_INVALID_RECIPIENT: 'ERR_INVALID_RECIPIENT',

  // schemes
  ERR_AMOUNT_MISMATCH: 'ERR_AMOUNT_MISMATCH',
  ERR_VALIDBEFORE_TOO_LOW: 'ERR_VALIDBEFORE_TOO_LOW',

  // signing
  ERR_SIGNER_FAILED: 'ERR_SIGNER_FAILED',
  ERR_INVALID_PRIVATE_KEY: 'ERR_INVALID_PRIVATE_KEY',

  // facilitator
  ERR_FACILITATOR_UNREACHABLE: 'ERR_FACILITATOR_UNREACHABLE',
  ERR_FACILITATOR_REJECTED: 'ERR_FACILITATOR_REJECTED',

  // negotiation
  ERR_NO_ACCEPTABLE_PAYMENT: 'ERR_NO_ACCEPTABLE_PAYMENT',
});

export class RosettaError extends Error {
  constructor(code, message, context = {}, remediation = undefined) {
    // Prefix code so .message includes the stable identifier and stack traces /
    // log lines tell you which condition fired without inspecting .code.
    super(`[${code}] ${message}`);
    this.name = 'RosettaError';
    this.code = code;
    this.context = context;
    if (remediation !== undefined) this.remediation = remediation;
  }

  toJSON() {
    return {
      code: this.code,
      message: this.message,
      context: this.context,
      ...(this.remediation ? { remediation: this.remediation } : {}),
    };
  }
}
