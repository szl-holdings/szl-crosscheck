"""Every assertion executed green before this file was pushed."""
import hashlib, json

from szl_crosscheck.crosscheck import GENESIS, canonical, crosscheck


def make_chain(harness, lanes):
    results = [{"engine": l, "runs": [1, 2, 3], "metrics": m} for l, m in lanes.items()]
    r = {"harness": harness, "results": results}
    payload = dict(r)
    r["prev_hash"] = GENESIS
    r["chain_hash"] = hashlib.sha256((GENESIS + canonical(payload)).encode()).hexdigest()
    return [r]


A = make_chain("stdlib-bench", {"bm25": {"ndcg10": 0.42, "mrr": 0.38}, "dense": {"ndcg10": 0.51}})
B = make_chain("fastapi-plane", {"bm25": {"ndcg10": 0.4201, "mrr": 0.3799}, "dense": {"ndcg10": 0.5102}})


def test_consistent_within_tolerance():
    assert crosscheck(A, B)["verdict"] == "CONSISTENT"


def test_divergent_names_metric_and_delta():
    bad = make_chain("fastapi-plane", {"bm25": {"ndcg10": 0.71, "mrr": 0.38}, "dense": {"ndcg10": 0.51}})
    r = crosscheck(A, bad)
    assert r["verdict"] == "DIVERGENT"
    lane = [l for l in r["lanes"] if l["lane"] == "bm25"][0]
    assert lane["worst_metric"] == "ndcg10" and lane["max_rel_delta"] > 0.4


def test_disjoint_lanes_incomparable():
    other = make_chain("fastapi-plane", {"tfidf": {"ndcg10": 0.5}})
    assert crosscheck(A, other)["verdict"] == "INCOMPARABLE"


def test_tampered_chain_invalid():
    import copy
    bad = copy.deepcopy(B)
    bad[0]["results"][0]["metrics"]["ndcg10"] = 0.99
    r = crosscheck(A, bad)
    assert r["verdict"] == "INVALID" and "chain B" in r["reason"]


def test_dual_receipt_deterministic():
    assert crosscheck(A, B)["dual_receipt"] == crosscheck(A, B)["dual_receipt"]


def test_empty_chain_fails_closed():
    assert crosscheck([], B)["verdict"] == "INVALID"
