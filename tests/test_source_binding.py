"""Tests for source_binding: content-addressed claim/source/outcome bindings."""
from __future__ import annotations

import copy
import pytest

from szl_crosscheck.source_binding import (
    BINDING_SCHEMA,
    BUNDLE_SCHEMA,
    SourceBindingError,
    bind_source,
    binding_hash,
    bundle_bindings,
    canonical_json,
    verify_binding,
    verify_bundle,
)

CONTENT = b"In 2026 the estate verified all five organs before admission.\nOrgan a11oy exports one span per request."
CLAIM = "The estate verified all five organs before admission."
URL = "https://example.org/estate/verification-2026.txt"
STAMP = "2026-11-19T22:45:00Z"
KEY = bytes(range(16, 32))


def _bind(**overrides) -> dict:
    kwargs = dict(
        claim_text=CLAIM,
        source_url=URL,
        content=CONTENT,
        retrieved_at=STAMP,
        excerpt="verified all five organs",
        benchmark={"benchmark_id": "szl.five-organ/v1", "item_id": "trace"},
        outcome={"model": "flagship55", "passed": True},
    )
    kwargs.update(overrides)
    return bind_source(**kwargs)


def test_happy_path_bind_and_verify():
    receipt = _bind()
    assert receipt["schema"] == BINDING_SCHEMA
    assert receipt["binding_hash"] == binding_hash(receipt)
    ok, reason = verify_binding(receipt, claim_text=CLAIM, content=CONTENT, excerpt="verified all five organs", key=None)
    assert ok is True
    assert reason == "OK"
    ok2, _ = verify_binding(receipt)
    assert ok2 is True


def test_excerpt_must_be_in_source():
    with pytest.raises(SourceBindingError):
        _bind(excerpt="not in source")
    ok, reason = verify_binding(_bind(), content=CONTENT, excerpt="absent bytes")
    assert ok is False and reason == "EXCERPT_NOT_IN_SOURCE"


def test_tamper_detection():
    receipt = _bind()
    ok, reason = verify_binding(receipt, claim_text=CLAIM + " almost")
    assert ok is False and reason == "CLAIM_DIGEST_MISMATCH"
    ok2, reason2 = verify_binding(receipt, content=CONTENT + b"extra")
    assert ok2 is False and reason2 == "CONTENT_DIGEST_MISMATCH"
    drifted = copy.deepcopy(receipt)
    drifted["retrieved_at"] = "2026-11-19T23:59:59Z"
    ok3, reason3 = verify_binding(drifted)
    assert ok3 is False and reason3 == "BINDING_HASH_MISMATCH"
    wrong_schema = dict(receipt)
    wrong_schema["schema"] = "szl.other/v9"
    assert verify_binding(wrong_schema) == (False, "SCHEMA_MISMATCH")


def test_hmac_keyed_binding_and_mismatch():
    receipt = _bind(key=KEY, key_id="szl-owner-2026q4")
    assert "hmac" in receipt and "key_id" in receipt
    ok, reason = verify_binding(receipt, key=KEY)
    assert ok is True and reason == "OK"
    ok2, reason2 = verify_binding(receipt)
    assert ok2 is False and reason2 == "HMAC_KEY_REQUIRED"
    ok3, reason3 = verify_binding(receipt, key=bytes(32))
    assert ok3 is False and reason3 == "HMAC_MISMATCH"
    unsigned = _bind()
    ok4, reason4 = verify_binding(unsigned, key=KEY)
    assert ok4 is False and reason4 == "HMAC_ABSENT"
    with pytest.raises(SourceBindingError):
        _bind(key=b"short", key_id="k")
    with pytest.raises(SourceBindingError):
        _bind(key=KEY)  # key without key_id


def test_fail_closed_inputs():
    for bad_kwargs in [
        dict(claim_text=""),
        dict(claim_text=123),
        dict(source_url="ftp://example.org/x"),
        dict(source_url="https://exa mple.org"),
        dict(content="not bytes"),
        dict(retrieved_at="2026-11-19 22:45:00Z"),
        dict(retrieved_at="2026-13-40T99:99:99Z"),
        dict(benchmark="not-a-mapping"),
        dict(outcome={"x": 1.5}),
        dict(key_id="dangling"),
        dict(claim_text="x" * 8193),
    ]:
        with pytest.raises(SourceBindingError):
            _bind(**bad_kwargs)


def test_canonical_json_deterministic():
    same = {"b": 1, "a": [2, {"y": 3, "x": None}]}
    other = {"a": [2, {"x": None, "y": 3}], "b": 1}
    assert canonical_json(same) == canonical_json(other)
    assert b" " not in canonical_json(same)
    with pytest.raises(SourceBindingError):
        canonical_json({"f": 1.25})


def _receipts(n: int) -> list:
    return [
        bind_source(
            claim_text="claim %d" % i,
            source_url=URL,
            content=b"source %d" % i,
            retrieved_at=STAMP,
        )
        for i in range(n)
    ]


def test_bundle_merkle_and_verification():
    receipts = _receipts(3)
    bundle = bundle_bindings(receipts, label="szl.bench-run/v1 demo")
    assert bundle["schema"] == BUNDLE_SCHEMA
    assert bundle["count"] == 3
    assert verify_bundle(bundle) == (True, "OK")
    assert len(set(bundle["leaves"])) == 3


def test_bundle_tamper_detection():
    bundle = bundle_bindings(_receipts(4), label="run-A")
    assert verify_bundle(bundle) == (True, "OK")
    tampered = copy.deepcopy(bundle)
    tampered["leaves"][0] = "0" * 64
    assert verify_bundle(tampered)[1] == "MERKLE_MISMATCH"
    relabel = copy.deepcopy(bundle)
    relabel["label"] = "run-B"
    assert verify_bundle(relabel)[1] == "BUNDLE_HASH_MISMATCH"
    recount = copy.deepcopy(bundle)
    recount["count"] = 99
    assert verify_bundle(recount)[1] in ("COUNT_MISMATCH", "BUNDLE_HASH_MISMATCH")


def test_bundle_hmac_and_fail_closed():
    bundle = bundle_bindings(_receipts(2), label="run-K", key=KEY, key_id="szl-owner-2026q4")
    assert verify_bundle(bundle, key=KEY) == (True, "OK")
    assert verify_bundle(bundle)[1] == "HMAC_KEY_REQUIRED"
    assert verify_bundle(bundle, key=bytes(32))[1] == "HMAC_MISMATCH"
    drift = _receipts(2)
    drift[1] = copy.deepcopy(drift[1])
    drift[1]["retrieved_at"] = "2026-11-19T23:00:00Z"
    with pytest.raises(SourceBindingError):
        bundle_bindings(drift, label="drifted")
    with pytest.raises(SourceBindingError):
        bundle_bindings([], label="empty")
    with pytest.raises(SourceBindingError):
        bundle_bindings(_receipts(2), label="   ")
    with pytest.raises(SourceBindingError):
        bundle_bindings([{"schema": "nope"}], label="bad")
    with pytest.raises(SourceBindingError):
        bundle_bindings(_receipts(2), label="l", key_id="dangling")


def test_signed_receipt_cannot_be_bundled_blindly():
    signed = _bind(key=KEY, key_id="szl-owner-2026q4")
    with pytest.raises(SourceBindingError):
        bundle_bindings([signed], label="mixed")
