"""Independent synthetic negative controls for declared harness improvements."""

from copy import deepcopy

from szl_crosscheck.harness_evolution import SCHEMA, review_harness_pair


def record():
    plan = {
        "pre_registered": True,
        "plan_revision": "1" * 40,
        "baseline_harness_revision": "2" * 40,
        "candidate_harness_revision": "3" * 40,
        "model_revision": "4" * 40,
        "evaluator_revision": "5" * 40,
        "heldout_revision": "6" * 64,
        "max_tokens_per_case": 250,
        "max_tools_per_case": 12,
        "max_token_ratio_basis_points": 10000,
        "minimum_net_gain_cases": 4,
        "candidate_family_size": 4,
        "familywise_alpha_ppm": 50000,
    }
    rows = []
    for i in range(40):
        rows.append(
            {
                "case_digest": f"{i + 1:064x}",
                "split": "heldout",
                "baseline_pass": 16 <= i < 20,
                "candidate_pass": i < 20,
                "baseline_tokens": 100,
                "candidate_tokens": 95,
                "baseline_tools": 2,
                "candidate_tools": 2,
            }
        )
    for i in range(40, 45):
        rows.append(
            {
                "case_digest": f"{i + 1:064x}",
                "split": "regression",
                "baseline_pass": True,
                "candidate_pass": True,
                "baseline_tokens": 100,
                "candidate_tokens": 95,
                "baseline_tools": 2,
                "candidate_tools": 2,
            }
        )
    return {
        "schema": SCHEMA,
        "plan": plan,
        "ownership": {
            "proposer_digest": "7" * 64,
            "evaluator_digest": "8" * 64,
        },
        "pairs": rows,
    }


def test_declared_improvement_stays_review_only():
    r = review_harness_pair(record())
    assert r["verdict"] == "SOURCE_CANDIDATE_FOR_OWNER_REVIEW"
    assert r["improved"] == 16 and r["regressed"] == 0
    assert r["p_exact"] == "1/65536"
    assert r["heldout_pairs"] == 40 and r["regression_pairs"] == 5
    for key in (
        "trusted_evaluator_proven",
        "plan_preregistration_proven",
        "model_quality_proven",
        "promotion_authorized",
        "runtime_change_authorized",
    ):
        assert r[key] is False


def test_no_task_identifiers_or_private_prompts_echoed():
    v = record()
    output = str(review_harness_pair(v))
    assert v["pairs"][0]["case_digest"] not in output
    assert "prompt" not in output


def test_no_preregistered_plan_is_hold():
    v = record()
    v["plan"]["pre_registered"] = False
    assert review_harness_pair(v)["reason"] == "PLAN_PREREGISTRATION_UNVERIFIED"


def test_unchanged_harness_source_is_hold():
    v = record()
    v["plan"]["candidate_harness_revision"] = v["plan"][
        "baseline_harness_revision"
    ]
    assert review_harness_pair(v)["reason"] == "NO_CANDIDATE_SOURCE_CHANGE"


def test_missing_or_identical_owner_is_hold():
    v = record()
    v["ownership"]["evaluator_digest"] = v["ownership"]["proposer_digest"]
    assert review_harness_pair(v)["reason"] == "INDEPENDENT_EVALUATOR_CLAIM_MISSING"
    v = record()
    del v["ownership"]["evaluator_digest"]
    assert review_harness_pair(v)["reason"] == "OWNERSHIP_SCHEMA_INVALID"


def test_false_or_missing_case_outcome_not_accepted():
    v = record()
    v["pairs"][0]["candidate_pass"] = 1
    assert review_harness_pair(v)["reason"] == "PASS_FLAG_NOT_BOOLEAN"
    v = record()
    v["pairs"][0].pop("baseline_pass")
    assert review_harness_pair(v)["reason"] == "PAIR_SCHEMA_INVALID"


def test_extra_fields_do_not_claim_external_attestation():
    v = record()
    v["trusted_signature"] = True
    assert review_harness_pair(v)["reason"] == "ROOT_SCHEMA_INVALID"
    v = record()
    v["pairs"][0]["verifier_override"] = True
    assert review_harness_pair(v)["reason"] == "PAIR_SCHEMA_INVALID"


def test_duplicate_or_malformed_task_id_is_hold():
    v = record()
    v["pairs"][1]["case_digest"] = v["pairs"][0]["case_digest"]
    assert review_harness_pair(v)["reason"] == "DUPLICATE_CASE_ID"
    v = record()
    v["pairs"][0]["case_digest"] = "not-sha256"
    assert review_harness_pair(v)["reason"] == "CASE_ID_OR_SPLIT_INVALID"


def test_regression_tasks_required_not_drop_weak_results():
    v = record()
    v["pairs"] = v["pairs"][:40]
    assert review_harness_pair(v)["reason"] == "MINIMUM_COVERAGE_NOT_MET"
    v = record()
    v["pairs"][40]["candidate_pass"] = False
    assert review_harness_pair(v)["reason"] == "PRIOR_CAPABILITY_REGRESSION"


def test_candidate_breach_of_token_or_tool_budget_is_hold():
    v = record()
    v["pairs"][0]["candidate_tokens"] = 251
    assert review_harness_pair(v)["reason"] == "PER_CASE_TOKEN_BUDGET_INVALID"
    v = record()
    v["pairs"][0]["candidate_tools"] = 13
    assert review_harness_pair(v)["reason"] == "PER_CASE_TOOL_BUDGET_INVALID"


def test_total_token_cost_regression_is_hold():
    v = record()
    for row in v["pairs"]:
        row["candidate_tokens"] = 110
    assert review_harness_pair(v)["reason"] == "TOKEN_COST_REGRESSION"


def test_no_measured_gain_is_hold_even_if_cost_reduces():
    v = record()
    for row in v["pairs"][:16]:
        row["candidate_pass"] = False
    assert (
        review_harness_pair(v)["reason"]
        == "PAIRED_GAIN_BELOW_PREREGISTERED_THRESHOLD"
    )


def test_single_success_cannot_satisfy_multiplicity_corrected_evidence():
    v = record()
    v["plan"]["minimum_net_gain_cases"] = 1
    for row in v["pairs"][1:16]:
        row["candidate_pass"] = False
    assert review_harness_pair(v)["reason"] == "MULTIPLICITY_ADJUSTED_SIGN_TEST_NOT_MET"


def test_many_patch_trials_cannot_reuse_weak_single_test():
    v = record()
    v["plan"]["candidate_family_size"] = 128
    assert (
        review_harness_pair(v)["reason"]
        == "MULTIPLICITY_ADJUSTED_SIGN_TEST_NOT_MET"
    )


def test_plan_threshold_or_family_size_boolean_invalid():
    for key in ("max_tokens_per_case", "familywise_alpha_ppm", "candidate_family_size"):
        v = record()
        v["plan"][key] = True
        assert review_harness_pair(v)["reason"] == "EVALUATION_POLICY_INVALID"


def test_limits_and_malformed_inputs_hold():
    assert review_harness_pair(None)["reason"] == "ROOT_SCHEMA_INVALID"
    v = record()
    v["pairs"] = v["pairs"] * 12
    assert review_harness_pair(v)["reason"] == "PAIR_COUNT_INVALID"
    v = record()
    v["plan"]["max_tokens_per_case"] = -1
    assert review_harness_pair(v)["reason"] == "EVALUATION_POLICY_INVALID"


def test_order_independent_arithmetic():
    v = record()
    initial = review_harness_pair(v)
    v["pairs"].reverse()
    assert review_harness_pair(v) == initial


def test_input_is_not_mutated():
    v = record()
    before = deepcopy(v)
    review_harness_pair(v)
    assert v == before
