# SPDX-License-Identifier: Apache-2.0
"""Exact receipt-chain and RFC 6962 Merkle comparison for Covenant.

This implementation uses only the standard library. It does not import Khipu
or Eclipse and does not verify signatures, witness independence, freshness,
authorization, or append-only continuity. CONSISTENT is comparison evidence,
never a permission to execute or recall.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

GENESIS = "0" * 64
MAX_LEAVES = 4096
MAX_RECEIPT_BYTES = 65536
MAX_JSON_NODES = 4096
MAX_JSON_DEPTH = 32
SCOPE = "exact receipt-chain and RFC6962 Merkle agreement only"
_HEX = re.compile(r"[0-9a-f]{64}\Z")


class CovenantInputError(ValueError):
    """A value is outside the declared bounded comparison profile."""


def _digest(value):
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise CovenantInputError("digest must be 64 lowercase hexadecimal characters")
    return value


def _canonical(value):
    # Bound the object before serialization, including nested or cyclic inputs.
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise CovenantInputError("receipt exceeds JSON shape limits")
        kind = type(item)
        if kind is dict:
            if len(item) > MAX_JSON_NODES:
                raise CovenantInputError("receipt has too many object fields")
            for key, child in item.items():
                if type(key) is not str or len(key) > MAX_RECEIPT_BYTES:
                    raise CovenantInputError("JSON keys must be bounded strings")
                pending.append((child, depth + 1))
        elif kind is list:
            if len(item) > MAX_JSON_NODES:
                raise CovenantInputError("receipt has too many array items")
            pending.extend((child, depth + 1) for child in item)
        elif kind is str:
            if len(item) > MAX_RECEIPT_BYTES:
                raise CovenantInputError("JSON string is too large")
        elif kind is float:
            if not math.isfinite(item):
                raise CovenantInputError("JSON numbers must be finite")
        elif kind is int:
            if item.bit_length() > 4096:
                raise CovenantInputError("JSON integer is too large")
        elif kind not in (bool, type(None)):
            raise CovenantInputError("receipt must contain JSON values only")
        if len(pending) + count > MAX_JSON_NODES:
            raise CovenantInputError("receipt exceeds JSON node limit")
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ensure_ascii=True,
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise CovenantInputError("receipt is not canonicalizable") from exc
    if len(encoded) > MAX_RECEIPT_BYTES:
        raise CovenantInputError("canonical receipt is too large")
    return encoded


def merkle_root(leaf_digests):
    """RFC 6962 root using an iterative carry frontier, not recursive slices.

    A leaf is SHA256(0x00 || the 32 digest bytes). An interior node is
    SHA256(0x01 || left || right). Empty input has SHA256(empty) as its root.
    """
    if type(leaf_digests) not in (list, tuple) or len(leaf_digests) > MAX_LEAVES:
        raise CovenantInputError("leaves must be a list or tuple of at most 4096 digests")
    frontier = []
    for value in leaf_digests:
        node = hashlib.sha256(b"\x00" + bytes.fromhex(_digest(value))).digest()
        level = 0
        while level < len(frontier) and frontier[level] is not None:
            node = hashlib.sha256(b"\x01" + frontier[level] + node).digest()
            frontier[level] = None
            level += 1
        if level == len(frontier):
            frontier.append(node)
        else:
            frontier[level] = node
    root = None
    for node in frontier:
        if node is not None:
            root = node if root is None else hashlib.sha256(b"\x01" + node + root).digest()
    return (root if root is not None else hashlib.sha256(b"").digest()).hex()


def chain_identity(receipts):
    """Recompute every link and return exact chain and Merkle identities."""
    if type(receipts) not in (list, tuple) or not 0 < len(receipts) <= MAX_LEAVES:
        raise CovenantInputError("chain must contain 1..4096 receipts")
    previous = GENESIS
    leaves = []
    exact = hashlib.sha256()
    for index, receipt in enumerate(receipts):
        if type(receipt) is not dict:
            raise CovenantInputError(f"receipt {index} must be an object")
        encoded = _canonical(receipt)
        if _digest(receipt.get("prev_hash")) != previous:
            raise CovenantInputError(f"receipt {index} has the wrong predecessor")
        payload = {key: value for key, value in receipt.items()
                   if key not in ("prev_hash", "chain_hash")}
        computed = hashlib.sha256(previous.encode("ascii") + _canonical(payload)).hexdigest()
        if _digest(receipt.get("chain_hash")) != computed:
            raise CovenantInputError(f"receipt {index} payload digest differs")
        # Length framing binds the exact receipt sequence, including metadata.
        exact.update(len(encoded).to_bytes(8, "big"))
        exact.update(encoded)
        leaves.append(computed)
        previous = computed
    return {
        "tree_size": len(leaves), "terminal_hash": previous,
        "chain_sha256": exact.hexdigest(), "root": merkle_root(leaves),
    }


def crosscheck_covenant(reference_chain, candidate_chain, *, observed_root, expected_root):
    """Compare two complete chains and a producer root to a caller-owned root.

    Both chains are consumed. All agreement is exact; retrieval tolerances are
    inapplicable. Missing or malformed values never yield CONSISTENT.
    """
    result = {"verdict": "INVALID", "scope": SCOPE, "execution_authorized": False}
    try:
        expected = _digest(expected_root)
        observed = _digest(observed_root)
        reference = chain_identity(reference_chain)
        candidate = chain_identity(candidate_chain)
    except CovenantInputError as exc:
        return {**result, "reason": str(exc)}
    consistent = (
        reference == candidate
        and reference["root"] == expected
        and candidate["root"] == observed
    )
    return {
        **result, "verdict": "CONSISTENT" if consistent else "DIVERGENT",
        "reason": "exact agreement" if consistent else "chain or root disagreement",
        "reference": reference, "candidate": candidate,
        "expected_root": expected, "observed_root": observed,
    }
