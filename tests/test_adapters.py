import copy
import hashlib
import json

import pytest

from szl_crosscheck.adapters import fastapi_retrieval, stdlib_retrieval
from szl_crosscheck.crosscheck import GENESIS, canonical, crosscheck, verify_chain


def sample():
    inputs = {"corpus": {"d1": "café"}, "queries": {"q1": "café"}, "qrels": {"q1": {"d1": 1}}}
    context = {"machine": {"identity": "fixture", "cpu": "fixture", "os": "fixture", "python": "3.12"},
               "dataset_revision": "fixture-v1", "model_revision": "bm25-k1=1.5-b=0.75",
               "parameters": {"top_k": 10, "k1": 1.5, "b": 0.75},
               "input_hashes": {k: hashlib.sha256(canonical(v).encode()).hexdigest() for k, v in inputs.items()},
               "source": {"repository": "fixture", "commit": "b" * 40}}
    metrics = {"ndcg@10": 1.0, "recall@10": 1.0}
    record = {"prev_hash": GENESIS, "ts": "fixture", "signature": "UNSIGNED_HONEST",
              "run": {"context": context, "result": {"state": "MEASURED", "lane": "bm25", "k": 10, "aggregate": metrics}}}
    record["self_hash"] = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    native_hash = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    run = {"status": "MEASURED", "lane": "sparse_bm25", "dataset_hash": native_hash(inputs["corpus"]),
           "qrels_hash": native_hash(inputs["qrels"]), "model_revision": context["model_revision"],
           "config": {"top_k": 10}, "metrics": metrics, "result_hash": native_hash(metrics)}
    return inputs, context, [record], run


def test_native_adapters_compare_with_distinct_canonical_formats():
    inputs, context, chain, run = sample()
    a = stdlib_retrieval(chain, context)
    b = fastapi_retrieval(run, context, inputs)
    assert verify_chain(a)[0] and verify_chain(b)[0]
    assert crosscheck(a, b)["verdict"] == "CONSISTENT"
    assert b[0]["native_schema"] == "RunReceipt (unchained HTTP response)"
    assert "no native chain or query hash" in b[0]["native_limitations"][0]
    assert a[0]["native_chain"] == chain
    run["metrics"]["ndcg@10"] = 0
    assert verify_chain(b)[0]


def test_native_stdlib_tamper_and_context_rejected():
    inputs, context, chain, run = sample()
    altered = copy.deepcopy(chain)
    altered[0]["run"]["result"]["aggregate"]["ndcg@10"] = 0
    with pytest.raises(ValueError, match="tampered"):
        stdlib_retrieval(altered, context)
    context = copy.deepcopy(context)
    context["dataset_revision"] = "other"
    with pytest.raises(ValueError, match="bind"):
        stdlib_retrieval(chain, context)


@pytest.mark.parametrize("field", ["dataset_hash", "qrels_hash", "result_hash", "model_revision"])
def test_native_response_binding_mismatch_rejected(field):
    inputs, context, chain, run = sample()
    run[field] = "bad"
    with pytest.raises(ValueError):
        fastapi_retrieval(run, context, inputs)


def test_captured_query_mismatch_rejected():
    inputs, context, chain, run = sample()
    inputs["queries"]["q1"] = "other"
    with pytest.raises(ValueError, match="queries input hash mismatch"):
        fastapi_retrieval(run, context, inputs)


def test_native_model_revision_must_equal_declared_context():
    inputs, context, chain, run = sample()
    context["model_revision"] = "a-different-model"
    with pytest.raises(ValueError, match="model/config differs from context"):
        fastapi_retrieval(run, context, inputs)
