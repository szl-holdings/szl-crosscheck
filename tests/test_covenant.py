# SPDX-License-Identifier: Apache-2.0
"""Independent vectors and adversarial controls for the scoped comparator."""
import copy
import hashlib
import json

import pytest

from szl_crosscheck.covenant import (
    CovenantInputError, chain_identity, crosscheck_covenant, merkle_root,
)


def recursive_root(leaves):
    if not leaves:
        return hashlib.sha256(b"").digest()
    if len(leaves) == 1:
        return hashlib.sha256(b"\x00" + bytes.fromhex(leaves[0])).digest()
    split = 1 << ((len(leaves) - 1).bit_length() - 1)
    return hashlib.sha256(
        b"\x01" + recursive_root(leaves[:split]) + recursive_root(leaves[split:])
    ).digest()


def make_chain(n=3, marker="fixture"):
    previous = "0" * 64
    chain = []
    for i in range(n):
        payload = {"seq": i, "marker": marker, "score": 0.42}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(previous.encode() + encoded).hexdigest()
        chain.append({**payload, "prev_hash": previous, "chain_hash": digest})
        previous = digest
    return chain


@pytest.mark.parametrize("size", list(range(66)) + [127, 128, 129, 255, 256, 257, 4096])
def test_frontier_matches_recursive_shape_vectors(size):
    leaves = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(size)]
    assert merkle_root(leaves) == recursive_root(leaves).hex()


def test_fixed_empty_and_single_leaf_vectors():
    assert merkle_root([]) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert merkle_root(["0" * 64]) == "7f9c9e31ac8256ca2f258583df262dbc7d6f68f2a03043d5c99a4ae5a7396ce9"


@pytest.mark.parametrize("leaves", [None, "0" * 64, [True], ["A" * 64], ["0"], ["g" * 64], ["0" * 64] * 4097])
def test_invalid_leaf_profiles_rejected(leaves):
    with pytest.raises(CovenantInputError):
        merkle_root(leaves)


def test_positive_control_consumes_both_chains_without_mutating():
    chain = make_chain()
    before = copy.deepcopy(chain)
    root = recursive_root([r["chain_hash"] for r in chain]).hex()
    result = crosscheck_covenant(chain, copy.deepcopy(chain), observed_root=root, expected_root=root)
    assert result["verdict"] == "CONSISTENT"
    assert result["execution_authorized"] is False
    assert result["reference"]["tree_size"] == 3
    assert chain == before


@pytest.mark.parametrize("field", ["reference", "candidate", "observed", "expected"])
def test_independently_changed_context_never_consistent(field):
    reference = make_chain()
    candidate = copy.deepcopy(reference)
    root = chain_identity(reference)["root"]
    observed = expected = root
    if field == "reference":
        reference = make_chain(marker="different")
    elif field == "candidate":
        candidate = make_chain(marker="different")
    elif field == "observed":
        observed = "a" * 64
    else:
        expected = "b" * 64
    result = crosscheck_covenant(reference, candidate, observed_root=observed, expected_root=expected)
    assert result["verdict"] == "DIVERGENT"


@pytest.mark.parametrize("mutation", [
    "payload", "order", "truncate", "duplicate", "predecessor",
    "uppercase", "nan", "non_string_key", "non_json", "deep", "cycle",
    "large_string", "large_array", "large_integer",
])
def test_invalid_chain_profiles(mutation):
    chain = make_chain()
    if mutation == "payload":
        chain[1]["score"] = 9
    elif mutation == "order":
        chain.reverse()
    elif mutation == "truncate":
        chain[-1]["chain_hash"] = "a"
    elif mutation == "duplicate":
        chain.append(copy.deepcopy(chain[-1]))
    elif mutation == "predecessor":
        chain[1]["prev_hash"] = "a" * 64
    elif mutation == "uppercase":
        chain[0]["chain_hash"] = chain[0]["chain_hash"].upper()
    elif mutation == "nan":
        chain[0]["score"] = float("nan")
    elif mutation == "non_string_key":
        chain[0][1] = "invalid"
    elif mutation == "non_json":
        chain[0]["score"] = object()
    elif mutation == "deep":
        value = None
        for _ in range(34):
            value = [value]
        chain[0]["score"] = value
    elif mutation == "cycle":
        chain[0]["score"] = chain
    elif mutation == "large_string":
        chain[0]["score"] = "x" * 65537
    elif mutation == "large_array":
        chain[0]["score"] = [None] * 4097
    elif mutation == "large_integer":
        chain[0]["score"] = 1 << 4097
    with pytest.raises(CovenantInputError):
        chain_identity(chain)
    valid = make_chain()
    root = chain_identity(valid)["root"]
    assert crosscheck_covenant(valid, chain, observed_root=root, expected_root=root)["verdict"] == "INVALID"


@pytest.mark.parametrize("chain", [None, [], {}, [None], [True]])
def test_missing_population_is_invalid(chain):
    with pytest.raises(CovenantInputError):
        chain_identity(chain)


def test_valid_truncated_chain_differs_from_anchored_population():
    reference = make_chain(5)
    candidate = reference[:-1]
    result = crosscheck_covenant(
        reference, candidate, observed_root=chain_identity(candidate)["root"],
        expected_root=chain_identity(reference)["root"],
    )
    assert result["verdict"] == "DIVERGENT"


def test_missing_or_malformed_root_fails_closed():
    chain = make_chain()
    root = chain_identity(chain)["root"]
    assert crosscheck_covenant(chain, chain, observed_root=None, expected_root=root)["verdict"] == "INVALID"
    assert crosscheck_covenant(chain, chain, observed_root=root, expected_root=True)["verdict"] == "INVALID"
