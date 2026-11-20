"""Negative-control tests for Kimi/peer agentic coding review, all synthetic."""

from copy import deepcopy

import pytest

from szl_crosscheck.mutation_controls import (
    SCHEMA,
    frozen_mutant_set_digest,
    review_mutation_controls,
)


def fixture(n=5):
    rows = [
        {
            "mutant_sha256": f"{100 + i:064x}",
            "test_content_sha256": "6" * 64,
            "evaluator_revision": "5" * 40,
            "baseline_pass": True,
            "mutant_pass": False,
            "run_receipt_sha256": f"{1000 + i:064x}",
            "baseline_environment_sha256": "9" * 64,
            "mutant_environment_sha256": "9" * 64,
            "baseline_selected_tests_sha256": "a" * 64,
            "mutant_selected_tests_sha256": "a" * 64,
            "baseline_executed_tests": 3,
            "mutant_executed_tests": 3,
            "baseline_skipped_tests": 0,
            "mutant_skipped_tests": 0,
            "mutant_failure_phase": "assertion",
        }
        for i in range(n)
    ]
    return {
        "schema": SCHEMA,
        "plan": {
            "preregistered": True,
            "baseline_revision": "1" * 40,
            "candidate_revision": "2" * 40,
            "test_revision": "3" * 40,
            "evaluator_revision": "5" * 40,
            "test_content_sha256": "6" * 64,
            "execution_environment_sha256": "9" * 64,
            "selected_tests_sha256": "a" * 64,
            "selected_test_count": 3,
            "frozen_mutant_set_sha256": frozen_mutant_set_digest(
                [r["mutant_sha256"] for r in rows]
            ),
            "declared_mutation_count": n,
        },
        "ownership": {
            "proposer_digest": "7" * 64,
            "evaluator_digest": "8" * 64,
            "independence_claimed": True,
        },
        "controls": rows,
    }


def test_positive_never_authorizes_or_attests():
    result = review_mutation_controls(fixture())
    assert result["verdict"] == "SOURCE_CANDIDATE_FOR_OWNER_REVIEW"
    assert result["controls"] == result["declared_kills"] == 5
    for key in (
        "independent_evaluation_proven", "preregistration_proven",
        "signature_verified", "patch_correctness_proven", "promotion_authorized",
        "merge_authorized", "runtime_change_authorized",
    ):
        assert result[key] is False


def test_four_controls_is_below_minimum():
    v = fixture()
    v["controls"].pop()
    assert review_mutation_controls(v)["reason"] == "MUTATION_COVERAGE_MISSING"


def test_duplicate_mutant_under_distinct_receipts_is_hold():
    v = fixture()
    v["controls"][1]["mutant_sha256"] = v["controls"][0]["mutant_sha256"]
    assert review_mutation_controls(v)["reason"] == "DUPLICATE_MUTATION_OR_RECEIPT"


def test_duplicate_receipt_is_hold():
    v = fixture()
    v["controls"][1]["run_receipt_sha256"] = v["controls"][0]["run_receipt_sha256"]
    assert review_mutation_controls(v)["reason"] == "DUPLICATE_MUTATION_OR_RECEIPT"


def test_all_mutants_survive_is_hold():
    v = fixture()
    for c in v["controls"]:
        c["mutant_pass"] = True
        c["mutant_failure_phase"] = "none"
    assert review_mutation_controls(v)["reason"] == "ALL_MUTANTS_SURVIVE"


def test_one_mutant_survives_is_hold():
    v = fixture()
    v["controls"][3]["mutant_pass"] = True
    v["controls"][3]["mutant_failure_phase"] = "none"
    r = review_mutation_controls(v)
    assert (r["reason"], r["survived"]) == ("MUTANTS_SURVIVE", 1)


def test_failing_baseline_cannot_be_relabelled():
    v = fixture()
    v["controls"][2]["baseline_pass"] = False
    assert review_mutation_controls(v)["reason"] == "REVERSED_OR_FAILING_BASELINE"


def test_mismatched_evaluator_or_test_digest_is_hold():
    for field, value in (("test_content_sha256", "f" * 64), ("evaluator_revision", "e" * 40)):
        v = fixture()
        v["controls"][0][field] = value
        assert review_mutation_controls(v)["reason"] == "CONTROL_PROVENANCE_MISMATCH"


def test_untrusted_identical_owner_or_false_independence():
    v = fixture()
    v["ownership"]["evaluator_digest"] = v["ownership"]["proposer_digest"]
    assert review_mutation_controls(v)["reason"] == "EVALUATOR_INDEPENDENCE_NOT_ESTABLISHED"
    v = fixture()
    v["ownership"]["independence_claimed"] = False
    assert review_mutation_controls(v)["reason"] == "EVALUATOR_INDEPENDENCE_NOT_ESTABLISHED"


def test_missing_preregistration_is_hold():
    v = fixture()
    v["plan"]["preregistered"] = False
    assert review_mutation_controls(v)["reason"] == "PLAN_PREREGISTRATION_UNVERIFIED"


def test_frozen_population_mismatch_is_hold():
    v = fixture()
    v["plan"]["frozen_mutant_set_sha256"] = "a" * 64
    assert review_mutation_controls(v)["reason"] == "FROZEN_MUTATION_POPULATION_MISMATCH"


def test_boolean_count_or_invalid_digest_is_hold():
    v = fixture()
    v["plan"]["declared_mutation_count"] = True
    assert review_mutation_controls(v)["reason"] == "MUTATION_COUNT_POLICY_INVALID"
    v = fixture()
    v["controls"][0]["mutant_sha256"] = "X" * 64
    assert review_mutation_controls(v)["reason"] == "CONTROL_DIGEST_INVALID"
    v = fixture()
    v["controls"][0]["mutant_pass"] = 0
    assert review_mutation_controls(v)["reason"] == "CONTROL_RESULT_INVALID"


def test_unknown_fields_are_rejected():
    v = fixture()
    v["trusted_by_kimi"] = True
    assert review_mutation_controls(v)["reason"] == "ROOT_SCHEMA_INVALID"
    v = fixture()
    v["controls"][0]["override"] = "PASS"
    assert review_mutation_controls(v)["reason"] == "CONTROL_SCHEMA_INVALID"


def test_unchanged_candidate_is_hold():
    v = fixture()
    v["plan"]["candidate_revision"] = v["plan"]["baseline_revision"]
    assert review_mutation_controls(v)["reason"] == "CANDIDATE_SOURCE_UNCHANGED"


def test_order_independence_and_input_immutability():
    v = fixture()
    before = deepcopy(v)
    first = review_mutation_controls(v)
    v["controls"].reverse()
    assert review_mutation_controls(v) == first
    assert before["controls"] == list(reversed(v["controls"]))


def test_mutant_set_requires_unique_lowercase_sha256_and_bounded_count():
    with pytest.raises(ValueError, match="MUTANT_SET_INVALID"):
        frozen_mutant_set_digest(["a" * 64] * 5)
    with pytest.raises(ValueError, match="MUTANT_SET_INVALID"):
        frozen_mutant_set_digest(["A" * 64] * 5)
    with pytest.raises(ValueError, match="MUTANT_SET_INVALID"):
        frozen_mutant_set_digest([f"{i:064x}" for i in range(4)])


def test_case_identifier_and_prompt_never_echoed():
    v = fixture()
    result = str(review_mutation_controls(v))
    assert v["controls"][0]["mutant_sha256"] not in result
    assert "prompt" not in result


def test_collection_failure_cannot_masquer_as_killed_mutant():
    v = fixture()
    v["controls"][0]["mutant_failure_phase"] = "collection"
    assert review_mutation_controls(v)["reason"] == "NON_ASSERTION_MUTANT_FAILURE"


def test_zero_executed_tests_fail_closed_even_if_mutant_failed():
    v = fixture()
    v["controls"][0]["mutant_executed_tests"] = 0
    assert review_mutation_controls(v)["reason"] == "TEST_EXECUTION_COVERAGE_UNVERIFIED"


def test_false_success_via_skipped_critical_test_is_hold():
    v = fixture()
    v["controls"][0]["baseline_skipped_tests"] = 1
    assert review_mutation_controls(v)["reason"] == "TEST_SKIPS_UNVERIFIED"


def test_transitive_environment_drift_is_hold():
    v = fixture()
    v["controls"][0]["mutant_environment_sha256"] = "b" * 64
    assert review_mutation_controls(v)["reason"] == "EXECUTION_ENVIRONMENT_OR_TEST_POPULATION_MISMATCH"


def test_test_population_mismatch_is_hold_even_if_counts_match():
    v = fixture()
    v["controls"][0]["mutant_selected_tests_sha256"] = "c" * 64
    assert review_mutation_controls(v)["reason"] == "EXECUTION_ENVIRONMENT_OR_TEST_POPULATION_MISMATCH"


def test_bool_counts_are_invalid():
    v = fixture()
    v["controls"][0]["baseline_executed_tests"] = True
    assert review_mutation_controls(v)["reason"] == "TEST_EXECUTION_COVERAGE_UNVERIFIED"
    v = fixture()
    v["plan"]["selected_test_count"] = True
    assert review_mutation_controls(v)["reason"] == "TEST_POPULATION_POLICY_INVALID"


def test_inconsistent_success_and_failure_phase_is_hold():
    v = fixture()
    v["controls"][0]["mutant_pass"] = True
    assert review_mutation_controls(v)["reason"] == "CONTROL_OUTCOME_PHASE_INCONSISTENT"
