// hive-rosetta protocol version constants.
export const X402_V1 = 1;
export const X402_V2 = 2;

// Header names — v2 (canonical wire format).
export const HEADER_PAYMENT_REQUIRED = 'PAYMENT-REQUIRED';
export const HEADER_PAYMENT_SIGNATURE = 'PAYMENT-SIGNATURE';
export const HEADER_PAYMENT_RESPONSE = 'PAYMENT-RESPONSE';

// Header names — v1 (legacy read tolerance).
// Hive constraint #14: middleware.py reads X-Payment / x-payment / X-PAYMENT.
// Rosetta accepts all three on input, emits v2 names on output by default.
export const HEADER_V1_INPUT_VARIANTS = ['X-Payment', 'x-payment', 'X-PAYMENT'];
export const HEADER_V1_DEFAULT_OUTPUT = 'X-Payment';

export const PACKAGE_VERSION = '0.1.0';
