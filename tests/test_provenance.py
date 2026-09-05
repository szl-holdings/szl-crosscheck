import copy
import hashlib
import pytest
from szl_crosscheck.crosscheck import canonical, crosscheck, seal
from test_crosscheck import A, B


def changed(chain, change):
    payload = {k: copy.deepcopy(v) for k, v in chain[0].items() if k not in ("prev_hash", "chain_hash")}
    change(payload)
    return seal(payload)


@pytest.mark.parametrize("key", ["machine", "input_hashes", "parameters", "model_revision", "dataset_revision"])
def test_context_mismatch_is_incomparable(key):
    def mutate(payload):
        value = payload["context"][key]
        if isinstance(value, dict):
            value[next(iter(value))] = "f" * 64
        else:
            payload["context"][key] = "different"
    assert crosscheck(A, changed(B, mutate))["verdict"] == "INCOMPARABLE"


def test_missing_provenance_is_invalid():
    assert crosscheck(A, changed(B, lambda p: p.pop("context")))["verdict"] == "INVALID"


def test_disjoint_metric_keys_cannot_pass():
    other = changed(A, lambda p: [r.update(metrics={"other": 1.0}) for r in p["results"]])
    assert crosscheck(A, other)["verdict"] == "INCOMPARABLE"


@pytest.mark.parametrize("value", [True, "0.2"])
def test_non_numeric_metric_invalid(value):
    other = changed(B, lambda p: p["results"][0]["metrics"].update(ndcg10=value))
    assert crosscheck(A, other)["verdict"] == "INVALID"


@pytest.mark.parametrize("value", [-1, True, float("nan"), float("inf")])
def test_invalid_tolerance(value):
    assert crosscheck(A, B, value)["verdict"] == "INVALID"


def test_duplicate_lane_invalid():
    other = changed(B, lambda p: p["results"].append(copy.deepcopy(p["results"][0])))
    assert crosscheck(A, other)["verdict"] == "INVALID"


def test_dual_hash_binds_full_report_and_terminals():
    report = crosscheck(A, B)
    digest = report.pop("dual_receipt")
    assert digest == hashlib.sha256(canonical(report).encode()).hexdigest()
    assert len(report["a_terminal"]) == len(report["b_terminal"]) == 64


@pytest.mark.parametrize("chain", [None, [None], [1], {"bad": 1}])
def test_malformed_chain_fails_closed(chain):
    assert crosscheck(chain, B)["verdict"] == "INVALID"


def test_extreme_finite_metrics_do_not_overflow_relative_delta():
    left = changed(A, lambda p: [r.update(metrics={"score": 1e308}) for r in p["results"]])
    right = changed(B, lambda p: [r.update(metrics={"score": -1e308}) for r in p["results"]])
    report = crosscheck(left, right)
    assert report["verdict"] == "DIVERGENT"
    assert all(row["max_rel_delta"] == 2.0 for row in report["lanes"])
    canonical(report)
