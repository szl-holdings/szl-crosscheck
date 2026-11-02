"""Distinct JSON context values must never alias through Python equality."""
import copy
import hashlib
import json

import pytest

from szl_crosscheck.crosscheck import GENESIS, canonical, crosscheck, seal
from szl_crosscheck.adapters import fastapi_retrieval, stdlib_retrieval
from test_adapters import sample
from test_crosscheck import A


def payload():
    return {key: copy.deepcopy(value) for key, value in A[0].items()
            if key not in ("prev_hash", "chain_hash")}


@pytest.mark.parametrize("left,right", [
    (True, 1), (False, 0), (1, 1.0),
    ({"flags": [True]}, {"flags": [1]}),
])
def test_distinct_parameter_json_is_incomparable(left, right):
    a, b = payload(), payload()
    a["context"]["parameters"]["feature"] = left
    b["context"]["parameters"]["feature"] = right
    report = crosscheck(seal(a), seal(b))
    assert report["verdict"] == "INCOMPARABLE"
    assert report["lanes"] == []


def test_aliasing_contexts_within_one_verified_chain_are_invalid():
    records = []
    previous = GENESIS
    for index, feature in enumerate((True, 1)):
        record = payload()
        record["context"]["parameters"]["feature"] = feature
        record["results"] = [{"state": "MEASURED", "lane": f"lane-{index}", "metrics": {"score": 1}}]
        digest = hashlib.sha256((previous + canonical(record)).encode()).hexdigest()
        records.append({**record, "prev_hash": previous, "chain_hash": digest})
        previous = digest
    report = crosscheck(records, records)
    assert report["verdict"] == "INVALID"
    assert "mixed measurement contexts" in report["reason"]


@pytest.mark.parametrize("path", [
    ("machine", "identity"), ("machine", "cpu"), ("machine", "os"),
    ("machine", "python"), ("dataset_revision",), ("model_revision",),
    ("source", "repository"),
])
@pytest.mark.parametrize("value", [True, 1, ["fixture"], {"id": "fixture"}, " \t"])
def test_textual_provenance_requires_nonblank_strings(path, value):
    record = payload()
    parent = record["context"]
    for part in path[:-1]:
        parent = parent[part]
    parent[path[-1]] = value
    chain = seal(record)
    assert crosscheck(chain, chain)["verdict"] == "INVALID"


def test_context_key_order_and_independent_source_remain_compatible():
    a, b = payload(), payload()
    b["context"] = dict(reversed(list(b["context"].items())))
    b["context"]["source"] = {"repository": "another-implementation", "commit": "c" * 40}
    assert crosscheck(seal(a), seal(b))["verdict"] == "CONSISTENT"


@pytest.mark.parametrize("native,supplied", [
    (True, 1), (False, 0), (1, 1.0),
    ({"flags": [True]}, {"flags": [1]}),
])
def test_native_adapter_cannot_rebind_a_differently_typed_context(native, supplied):
    _inputs, context, chain, _run = sample()
    context["parameters"]["feature"] = native
    del chain[0]["self_hash"]
    chain[0]["self_hash"] = hashlib.sha256(json.dumps(
        chain[0], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()).hexdigest()
    claimed = copy.deepcopy(context)
    claimed["parameters"]["feature"] = supplied
    with pytest.raises(ValueError, match="bind the supplied context"):
        stdlib_retrieval(chain, claimed)


@pytest.mark.parametrize("adapter", ["stdlib", "fastapi"])
@pytest.mark.parametrize("native,declared", [(True, 1), (False, 0), (1, 1.0)])
def test_native_cutoff_type_must_match_declared_context(adapter, native, declared):
    inputs, context, chain, run = sample()
    context["parameters"]["top_k"] = declared
    chain[0]["run"]["result"]["k"] = native
    del chain[0]["self_hash"]
    chain[0]["self_hash"] = hashlib.sha256(json.dumps(
        chain[0], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()).hexdigest()
    run["config"]["top_k"] = native
    with pytest.raises(ValueError, match="differs from context"):
        if adapter == "stdlib":
            stdlib_retrieval(chain, context)
        else:
            fastapi_retrieval(run, context, inputs)
