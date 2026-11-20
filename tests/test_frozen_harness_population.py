"""Synthetic denial and consistency tests for opt-in frozen case populations."""

from copy import deepcopy

from test_harness_evolution import record
from szl_crosscheck.frozen_population import (
    FROZEN_POPULATION_SCHEMA,
    review_frozen_harness_pair,
    validate_policy,
)
from szl_crosscheck.harness_evolution import review_harness_pair


def policy_for(evidence):
    return {
        "schema": FROZEN_POPULATION_SCHEMA,
        "heldout_case_digests": [
            r["case_digest"] for r in evidence["pairs"] if r["split"] == "heldout"
        ],
        "regression_case_digests": [
            r["case_digest"] for r in evidence["pairs"] if r["split"] == "regression"
        ],
    }


def test_exact_frozen_population_is_only_source_review():
    evidence = record()
    policy = policy_for(evidence)
    result = review_frozen_harness_pair(evidence, policy)
    assert result["verdict"] == "SOURCE_CANDIDATE_FOR_OWNER_REVIEW"
    assert result["frozen_population_complete"] is True
    assert result["population_preregistration_proven"] is False
    assert len(result["frozen_population_sha256"]) == 64
    assert result["missing_heldout_count"] == result["unexpected_heldout_count"] == 0
    assert result["promotion_authorized"] is False
    assert result["runtime_change_authorized"] is False
    assert evidence["pairs"][0]["case_digest"] not in str(result)


def test_split_swap_same_counts_cannot_pass_kimi_negative_control():
    evidence = record()
    policy = policy_for(evidence)
    evidence["pairs"][0]["split"] = "regression"
    evidence["pairs"][40]["split"] = "heldout"
    assert review_harness_pair(evidence)["verdict"] == "SOURCE_CANDIDATE_FOR_OWNER_REVIEW"
    result = review_frozen_harness_pair(evidence, policy)
    assert result["verdict"] == "HOLD"
    assert result["reason"] == "FROZEN_POPULATION_MISMATCH"
    assert (result["missing_heldout_count"], result["unexpected_heldout_count"]) == (1, 1)
    assert (result["missing_regression_count"], result["unexpected_regression_count"]) == (1, 1)


def test_valid_partial_heldout_set_is_not_complete_population():
    evidence = record()
    policy = policy_for(evidence)
    evidence["pairs"] = evidence["pairs"][:35] + evidence["pairs"][40:]
    assert review_harness_pair(evidence)["verdict"] == "SOURCE_CANDIDATE_FOR_OWNER_REVIEW"
    result = review_frozen_harness_pair(evidence, policy)
    assert result["verdict"] == "HOLD"
    assert result["missing_heldout_count"] == 5
    assert result["unexpected_heldout_count"] == 0


def test_replaced_case_at_same_count_cannot_pass():
    evidence = record()
    policy = policy_for(evidence)
    evidence["pairs"][24]["case_digest"] = "f" * 64
    assert review_harness_pair(evidence)["verdict"] == "SOURCE_CANDIDATE_FOR_OWNER_REVIEW"
    result = review_frozen_harness_pair(evidence, policy)
    assert result["reason"] == "FROZEN_POPULATION_MISMATCH"
    assert result["missing_heldout_count"] == result["unexpected_heldout_count"] == 1


def test_order_independent_policy_digest_and_result():
    evidence = record()
    policy = policy_for(evidence)
    report = review_frozen_harness_pair(evidence, policy)
    policy["heldout_case_digests"].reverse()
    policy["regression_case_digests"].reverse()
    evidence["pairs"].reverse()
    assert review_frozen_harness_pair(evidence, policy) == report


def test_duplicate_or_cross_split_case_expected_policy_is_invalid():
    evidence = record()
    policy = policy_for(evidence)
    policy["regression_case_digests"][0] = policy["heldout_case_digests"][0]
    assert validate_policy(policy) is None
    assert review_frozen_harness_pair(evidence, policy)["reason"] == "FROZEN_POPULATION_POLICY_INVALID"
    policy = policy_for(evidence)
    policy["heldout_case_digests"][1] = policy["heldout_case_digests"][0]
    assert validate_policy(policy) is None


def test_malformed_policy_rejected_without_source_promotion():
    evidence = record()
    cases = [None, {}, {"schema": FROZEN_POPULATION_SCHEMA}, []]
    for malformed in cases:
        assert review_frozen_harness_pair(evidence, malformed)["verdict"] == "HOLD"
    for key, value in [
        ("schema", False),
        ("schema", "other"),
        ("heldout_case_digests", ("0" * 64,)),
        ("regression_case_digests", []),
    ]:
        policy = policy_for(evidence)
        policy[key] = value
        assert review_frozen_harness_pair(evidence, policy)["reason"] == "FROZEN_POPULATION_POLICY_INVALID"
    policy = policy_for(evidence)
    policy["heldout_case_digests"][0] = "A" * 64
    assert validate_policy(policy) is None
    policy = policy_for(evidence)
    policy["heldout_case_digests"] += [f"{i + 50:064x}" for i in range(480)]
    assert validate_policy(policy) is None


def test_incomplete_source_arithmetic_cannot_be_upgraded():
    evidence = record()
    policy = policy_for(evidence)
    evidence["pairs"][0]["candidate_tokens"] = 251
    result = review_frozen_harness_pair(evidence, policy)
    assert result["verdict"] == "HOLD"
    assert result["reason"] == "PER_CASE_TOKEN_BUDGET_INVALID"
    assert result["frozen_population_complete"] is False


def test_input_is_unchanged_even_on_mismatch():
    evidence = record()
    policy = policy_for(evidence)
    before = deepcopy((evidence, policy))
    review_frozen_harness_pair(evidence, policy)
    assert (evidence, policy) == before
