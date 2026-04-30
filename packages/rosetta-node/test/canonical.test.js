// Conformance: JCS canonicalization. Vectors are byte-deterministic.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canonicalize } from '../src/index.js';

test('canonical: primitives round-trip', () => {
  assert.equal(canonicalize(null), 'null');
  assert.equal(canonicalize(true), 'true');
  assert.equal(canonicalize(false), 'false');
  assert.equal(canonicalize(0), '0');
  assert.equal(canonicalize(42), '42');
  assert.equal(canonicalize('hello'), '"hello"');
});

test('canonical: object keys sorted lexicographically', () => {
  assert.equal(
    canonicalize({ z: 1, a: 2, m: 3 }),
    '{"a":2,"m":3,"z":1}',
  );
});

test('canonical: nested objects', () => {
  assert.equal(
    canonicalize({ z: 1, a: [3, 2, 1], m: { b: 2, a: 1 } }),
    '{"a":[3,2,1],"m":{"a":1,"b":2},"z":1}',
  );
});

test('canonical: undefined keys dropped', () => {
  assert.equal(canonicalize({ a: 1, b: undefined, c: 3 }), '{"a":1,"c":3}');
});

test('canonical: arrays preserve order', () => {
  assert.equal(canonicalize([3, 1, 2]), '[3,1,2]');
});

test('canonical: empty containers', () => {
  assert.equal(canonicalize({}), '{}');
  assert.equal(canonicalize([]), '[]');
});

test('canonical: unicode strings escape correctly via JSON.stringify', () => {
  // canonical relies on JSON.stringify for strings — same escape rules.
  assert.equal(canonicalize('café'), JSON.stringify('café'));
});
