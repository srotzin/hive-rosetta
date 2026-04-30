"""
Conformance: JCS canonicalization. Vectors are byte-deterministic.
Mirrors rosetta-node/test/canonical.test.js (7 tests).
"""
import json

import pytest

from hive_rosetta import canonicalize


def test_primitives_round_trip():
    assert canonicalize(None) == "null"
    assert canonicalize(True) == "true"
    assert canonicalize(False) == "false"
    assert canonicalize(0) == "0"
    assert canonicalize(42) == "42"
    assert canonicalize("hello") == '"hello"'


def test_object_keys_sorted_lexicographically():
    assert canonicalize({"z": 1, "a": 2, "m": 3}) == '{"a":2,"m":3,"z":1}'


def test_nested_objects():
    assert (
        canonicalize({"z": 1, "a": [3, 2, 1], "m": {"b": 2, "a": 1}})
        == '{"a":[3,2,1],"m":{"a":1,"b":2},"z":1}'
    )


def test_none_keys_dropped():
    """Python None keys are dropped — mirrors Node undefined-key drop."""
    assert canonicalize({"a": 1, "b": None, "c": 3}) == '{"a":1,"c":3}'


def test_arrays_preserve_order():
    assert canonicalize([3, 1, 2]) == "[3,1,2]"


def test_empty_containers():
    assert canonicalize({}) == "{}"
    assert canonicalize([]) == "[]"


def test_unicode_strings_escape_correctly():
    # canonicalize relies on json.dumps for strings — same escape rules as JSON.stringify.
    assert canonicalize("café") == json.dumps("café", ensure_ascii=False)
