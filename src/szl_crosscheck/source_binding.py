"""Cryptographic source and outcome binding receipts for the evidence graph.

Binds a claim, the exact source bytes it was grounded in, and an optional
measured model outcome into one content-addressed receipt, and bundles
per-item bindings under a single Merkle root for benchmark runs.

Honest scope: digests prove exactly which bytes were seen at bind time and
that a receipt has not drifted since. They do NOT prove the source is
truthful, that the URL still resolves at verify time, or that an outcome was
honest before it was bound. Keyed receipts use an owner-supplied key at
runtime; keys are never stored in receipts and never logged. No network
access of any kind happens in this module. Fail closed on every invalid
input rather than guessing.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from datetime import datetime

BINDING_SCHEMA = "szl.source-binding/v1"
BUNDLE_SCHEMA = "szl.source-binding-bundle/v1"

MAX_CLAIM_CHARS = 8192
MAX_CONTENT_BYTES = 16 * 1024 * 1024
MAX_SUBRECORD_BYTES = 16384
MAX_URL_BYTES = 512
MAX_KEY_ID_BYTES = 64
MIN_KEY_BYTES = 16
MAX_BUNDLE_LEAVES = 4096
MAX_LABEL_CHARS = 200

_RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_URL_OK = re.compile(r"^https?://[!-~]+$")


class SourceBindingError(ValueError):
    """Unsupported input or failed-closed binding/verification constraint."""


def _digest(data: bytes) -> str:
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise SourceBindingError("content must be non-empty bytes")
    if len(data) > MAX_CONTENT_BYTES:
        raise SourceBindingError("content exceeds bounded size")
    return hashlib.sha256(bytes(data)).hexdigest()


def canonical_json(record: object) -> bytes:
    """Deterministic UTF-8 JSON: sorted keys, no whitespace, strict types."""
    def check(node: object) -> None:
        if node is None or isinstance(node, (str, bool, int)):
            return
        if isinstance(node, float):
            raise SourceBindingError("floats are not canonicalizable")
        if isinstance(node, list):
            for item in node:
                check(item)
            return
        if isinstance(node, Mapping):
            for key, value in node.items():
                if not isinstance(key, str):
                    raise SourceBindingError("mapping keys must be strings")
                check(value)
            return
        raise SourceBindingError("unsupported JSON value type")
    check(record)
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _validated_timestamp(text: object) -> str:
    if not isinstance(text, str) or len(text) != 20 or not _RFC3339_UTC.match(text):
        raise SourceBindingError("retrieved_at must be an RFC3339 UTC instant ending in Z")
    try:
        datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise SourceBindingError("retrieved_at is not a real calendar instant") from exc
    return text


def _validated_url(text: object) -> str:
    if not isinstance(text, str) or not text.isascii():
        raise SourceBindingError("source_url must be an ASCII http(s) URL")
    encoded = text.encode("ascii")
    if len(encoded) > MAX_URL_BYTES or not _URL_OK.match(text):
        raise SourceBindingError("source_url must be http(s) with no whitespace")
    return text


def _validated_subrecord(record: object, field: str) -> dict:
    if not isinstance(record, Mapping):
        raise SourceBindingError("%s must be a JSON object" % field)
    try:
        encoded = canonical_json(dict(record))
    except SourceBindingError as exc:
        raise SourceBindingError("%s must be strictly JSON-typed: %s" % (field, exc)) from exc
    if len(encoded) > MAX_SUBRECORD_BYTES:
        raise SourceBindingError("%s exceeds bounded size" % field)
    return {str(key): record[key] for key in record}


def binding_hash(receipt: Mapping) -> str:
    """Content address of a receipt: sha256 over everything except itself and any hmac."""
    if not isinstance(receipt, Mapping):
        raise SourceBindingError("receipt must be a JSON object")
    pre = {key: value for key, value in receipt.items() if key not in ("binding_hash", "hmac")}
    return hashlib.sha256(canonical_json(pre)).hexdigest()


def bind_source(
    claim_text: object,
    source_url: object,
    content: object,
    retrieved_at: object,
    *,
    excerpt: object = None,
    benchmark: object = None,
    outcome: object = None,
    key: object = None,
    key_id: object = None,
) -> dict:
    """Bind claim text to the exact source bytes (and optional outcome) it is grounded in.

    Fails closed on any invalid input. With an owner-supplied key (never
    persisted), the binding is additionally HMAC-SHA256 signed so later
    verification can detect substitution of whole receipts.
    """
    if not isinstance(claim_text, str) or not claim_text.strip():
        raise SourceBindingError("claim_text must be a nonblank string")
    if len(claim_text) > MAX_CLAIM_CHARS:
        raise SourceBindingError("claim_text exceeds bounded size")
    url = _validated_url(source_url)
    stamp = _validated_timestamp(retrieved_at)
    if not isinstance(content, (bytes, bytearray)):
        raise SourceBindingError("content must be bytes")
    source_bytes = bytes(content)
    source_sha = _digest(source_bytes)

    excerpt_sha = None
    excerpt_text = None
    if excerpt is not None:
        if not isinstance(excerpt, (str, bytes, bytearray)):
            raise SourceBindingError("excerpt must be str or bytes")
        excerpt_text = excerpt if isinstance(excerpt, str) else None
        excerpt_bytes = excerpt.encode("utf-8") if isinstance(excerpt, str) else bytes(excerpt)
        if not excerpt_bytes or len(excerpt_bytes) > MAX_CONTENT_BYTES:
            raise SourceBindingError("excerpt must be non-empty bounded bytes")
        if source_bytes.find(excerpt_bytes) < 0:
            raise SourceBindingError("EXCERPT_NOT_IN_SOURCE: excerpt bytes are not a substring of content")
        excerpt_sha = hashlib.sha256(excerpt_bytes).hexdigest()

    bench = _validated_subrecord(benchmark, "benchmark") if benchmark is not None else None
    out = _validated_subrecord(outcome, "outcome") if outcome is not None else None

    receipt: dict = {
        "schema": BINDING_SCHEMA,
        "claim_sha256": hashlib.sha256(claim_text.encode("utf-8")).hexdigest(),
        "source_url": url,
        "source_content_sha256": source_sha,
        "source_bytes_len": len(source_bytes),
        "retrieved_at": stamp,
    }
    if excerpt_sha is not None:
        receipt["excerpt_sha256"] = excerpt_sha
        if excerpt_text is not None:
            receipt["excerpt_utf8_len"] = len(excerpt_text.encode("utf-8"))
    if bench is not None:
        receipt["benchmark"] = bench
        receipt["benchmark_sha256"] = hashlib.sha256(canonical_json(bench)).hexdigest()
    if out is not None:
        receipt["outcome"] = out
        receipt["outcome_sha256"] = hashlib.sha256(canonical_json(out)).hexdigest()

    if key is not None:
        if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
            raise SourceBindingError("key must be bytes of at least %d bytes" % MIN_KEY_BYTES)
        if not isinstance(key_id, str) or not key_id or not key_id.isascii() or len(key_id.encode("ascii")) > MAX_KEY_ID_BYTES:
            raise SourceBindingError("key_id must be a short ASCII label")
        receipt["key_id"] = key_id
        receipt["binding_hash"] = binding_hash(receipt)
        receipt["hmac"] = hmac.new(bytes(key), receipt["binding_hash"].encode("ascii"), hashlib.sha256).hexdigest()
    else:
        if key_id is not None:
            raise SourceBindingError("key_id provided without key")
        receipt["binding_hash"] = binding_hash(receipt)
    return receipt


def verify_binding(
    receipt: object,
    *,
    claim_text: object = None,
    content: object = None,
    excerpt: object = None,
    key: object = None,
) -> tuple[bool, str]:
    """Fail-closed verification with an explicit reason code.

    (True, "OK") only when schema, binding hash, (optional) hmac, and every
    supplied artifact (claim text, source bytes, excerpt bytes) match.
    Absent artifacts are NOT silently passed: they are simply not checked,
    and the honest caller records which were present.
    """
    if not isinstance(receipt, Mapping):
        return (False, "RECEIPT_NOT_OBJECT")
    inner = dict(receipt)
    if inner.get("schema") != BINDING_SCHEMA:
        return (False, "SCHEMA_MISMATCH")
    recomputed = binding_hash(inner)
    if recomputed != inner.get("binding_hash"):
        return (False, "BINDING_HASH_MISMATCH")
    if "hmac" in inner or "key_id" in inner:
        if key is None:
            return (False, "HMAC_KEY_REQUIRED")
        if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
            return (False, "HMAC_KEY_INVALID")
        expected = hmac.new(bytes(key), recomputed.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(inner.get("hmac", ""))):
            return (False, "HMAC_MISMATCH")
    elif key is not None:
        return (False, "HMAC_ABSENT")
    if claim_text is not None:
        if not isinstance(claim_text, str):
            return (False, "CLAIM_NOT_STRING")
        if hashlib.sha256(claim_text.encode("utf-8")).hexdigest() != inner.get("claim_sha256"):
            return (False, "CLAIM_DIGEST_MISMATCH")
    if content is not None:
        if not isinstance(content, (bytes, bytearray)):
            return (False, "CONTENT_NOT_BYTES")
        if _digest(bytes(content)) != inner.get("source_content_sha256"):
            return (False, "CONTENT_DIGEST_MISMATCH")
        if "excerpt_sha256" in inner and excerpt is not None:
            if isinstance(excerpt, str):
                excerpt_bytes = excerpt.encode("utf-8")
            elif isinstance(excerpt, (bytes, bytearray)):
                excerpt_bytes = bytes(excerpt)
            else:
                return (False, "EXCERPT_INVALID")
            if bytes(content).find(excerpt_bytes) < 0:
                return (False, "EXCERPT_NOT_IN_SOURCE")
            if hashlib.sha256(excerpt_bytes).hexdigest() != inner["excerpt_sha256"]:
                return (False, "EXCERPT_DIGEST_MISMATCH")
    return (True, "OK")


def _merkle_root(leaves: list) -> str:
    level = [bytes.fromhex(leaf) for leaf in leaves]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                nxt.append(hashlib.sha256(b"L:" + level[i] + b"R:" + level[i + 1]).digest())
            else:
                nxt.append(level[i])  # odd node promoted unchanged
        level = nxt
    return level[0].hex()


def bundle_bindings(receipts: object, *, label: object, key: object = None, key_id: object = None) -> dict:
    """Bundle ordered per-item bindings for one benchmark run under a Merkle root.

    Every receipt must first pass its own integrity re-verification; any
    drifted receipt fails the whole bundle. The Merkle rule is deterministic:
    pairs hash as sha256 of b"L:" + left + b"R:" + right; an unpaired odd
    node is promoted unchanged. The bundle hash covers schema, label,
    count, leaves, and root together so labels cannot drift silently.
    """
    if not isinstance(receipts, list) or not receipts:
        raise SourceBindingError("receipts must be a non-empty ordered list")
    if len(receipts) > MAX_BUNDLE_LEAVES:
        raise SourceBindingError("bundle exceeds bounded leaf count")
    if not isinstance(label, str) or not label.strip() or len(label) > MAX_LABEL_CHARS:
        raise SourceBindingError("label must be a short nonblank string")
    leaves = []
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, Mapping):
            raise SourceBindingError("receipt %d is not an object" % index)
        inner = dict(receipt)
        if inner.get("schema") != BINDING_SCHEMA:
            raise SourceBindingError("receipt %d has the wrong schema" % index)
        recomputed = binding_hash(inner)
        if recomputed != inner.get("binding_hash"):
            raise SourceBindingError("receipt %d failed integrity re-verification" % index)
        if "hmac" in inner:
            raise SourceBindingError("hmac-signed receipts require their key to be ordered verifiably")
        leaves.append(recomputed)
    bundle = {
        "schema": BUNDLE_SCHEMA,
        "label": label,
        "count": len(leaves),
        "leaves": leaves,
        "merkle_root": _merkle_root(leaves),
    }
    if key is not None:
        if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
            raise SourceBindingError("key must be bytes of at least %d bytes" % MIN_KEY_BYTES)
        if not isinstance(key_id, str) or not key_id or not key_id.isascii() or len(key_id.encode("ascii")) > MAX_KEY_ID_BYTES:
            raise SourceBindingError("key_id must be a short ASCII label")
        bundle["key_id"] = key_id
        bundle["bundle_sha256"] = hashlib.sha256(canonical_json(bundle)).hexdigest()
        bundle["hmac"] = hmac.new(bytes(key), bundle["bundle_sha256"].encode("ascii"), hashlib.sha256).hexdigest()
    else:
        if key_id is not None:
            raise SourceBindingError("key_id provided without key")
        bundle["bundle_sha256"] = hashlib.sha256(canonical_json(bundle)).hexdigest()
    return bundle


def verify_bundle(bundle: object, *, key: object = None) -> tuple:
    """Fail-closed bundle verification with an explicit reason code."""
    if not isinstance(bundle, Mapping):
        return (False, "BUNDLE_NOT_OBJECT")
    inner = dict(bundle)
    if inner.get("schema") != BUNDLE_SCHEMA:
        return (False, "SCHEMA_MISMATCH")
    leaves = inner.get("leaves")
    if not isinstance(leaves, list) or not leaves or len(leaves) > MAX_BUNDLE_LEAVES:
        return (False, "LEAVES_INVALID")
    for leaf in leaves:
        if not isinstance(leaf, str) or not re.fullmatch(r"[0-9a-f]{64}", leaf):
            return (False, "LEAF_INVALID")
    if inner.get("count") != len(leaves):
        return (False, "COUNT_MISMATCH")
    if _merkle_root(leaves) != inner.get("merkle_root"):
        return (False, "MERKLE_MISMATCH")
    pinned = {k: v for k, v in inner.items() if k not in ("bundle_sha256", "hmac")}
    if hashlib.sha256(canonical_json(pinned)).hexdigest() != inner.get("bundle_sha256"):
        return (False, "BUNDLE_HASH_MISMATCH")
    if "hmac" in inner or "key_id" in inner:
        if key is None:
            return (False, "HMAC_KEY_REQUIRED")
        if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
            return (False, "HMAC_KEY_INVALID")
        expected = hmac.new(bytes(key), inner["bundle_sha256"].encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(inner.get("hmac", ""))):
            return (False, "HMAC_MISMATCH")
    elif key is not None:
        return (False, "HMAC_ABSENT")
    return (True, "OK")
