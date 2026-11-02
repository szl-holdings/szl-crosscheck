"""Integer measurements must not disappear during floating normalization."""
import copy
from fractions import Fraction

import pytest

from szl_crosscheck.crosscheck import crosscheck, seal

CONTEXT = {
    "machine": {"identity": "fixture", "cpu": "fixture", "os": "fixture", "python": "3.12"},
    "dataset_revision": "fixture-v1", "model_revision": "fixture-v1",
    "parameters": {"top_k": 10},
    "input_hashes": {key: "a" * 64 for key in ("corpus", "queries", "qrels")},
    "source": {"repository": "fixture", "commit": "b" * 40},
}


def chain(value):
    return seal({"context": CONTEXT,
                 "results": [{"state": "MEASURED", "lane": "counts",
                              "metrics": {"count": value}}]})


@pytest.mark.parametrize("a,b", [
    (2**55, 2**55 + 1),
    (-(2**55), -(2**55 + 1)),
    (10**100, 10**100 + 1),
    (10**300, 10**300 + 1),
    (2**55 + 1, float(2**55)),
    (float(2**55), 2**55 + 1),
    (-(2**55 + 1), -float(2**55)),
])
def test_distinct_integer_values_are_not_consistent_at_zero_tolerance(a, b):
    report = crosscheck(chain(a), chain(b), rel_tol=0)
    expected = float(abs(Fraction(a) - Fraction(b)) / Fraction(max(abs(a), abs(b), 1e-12)))
    row = report["lanes"][0]
    assert report["verdict"] == row["verdict"] == "DIVERGENT"
    assert row["worst_metric"] == "count"
    assert row["max_rel_delta"] == row["deltas"]["count"] == expected
    assert expected > 0


@pytest.mark.parametrize("a,b", [
    (2**55, float(2**55)), (0, 0.0), (10**100, 10**100),
])
def test_equal_integer_and_mixed_representations_remain_consistent(a, b):
    report = crosscheck(chain(a), chain(b), rel_tol=0)
    assert report["verdict"] == "CONSISTENT"
    assert report["lanes"][0]["max_rel_delta"] == 0


def test_integer_delta_respects_existing_tolerance_boundary():
    # Exact dyadic delta keeps this boundary independent of decimal rounding.
    a, b = 2**55 - 1, 2**55
    delta = 1 / 2**55
    assert crosscheck(chain(a), chain(b), rel_tol=delta)["verdict"] == "CONSISTENT"
    assert crosscheck(chain(a), chain(b), rel_tol=delta / 2)["verdict"] == "DIVERGENT"


def test_report_is_deterministic_and_inputs_are_not_modified():
    a, b = chain(2**55), chain(2**55 + 1)
    before = copy.deepcopy((a, b))
    assert crosscheck(a, b, 0) == crosscheck(a, b, 0)
    assert (a, b) == before


def test_opposite_large_mixed_values_normalize_without_overflow():
    report = crosscheck(chain(10**308), chain(-1e308), rel_tol=0)
    assert report["verdict"] == "DIVERGENT"
    assert report["lanes"][0]["max_rel_delta"] == 2.0
