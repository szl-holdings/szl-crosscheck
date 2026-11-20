"""Synthetic first-party tests for ambiguous dream-check claim prevention."""

from copy import deepcopy

from szl_crosscheck.dream_predicate import SCHEMA, review_next_cycle

NOW = "2026-11-20T04:12:00Z"


def pair():
    plan = {
        "schema": SCHEMA,
        "pre_registered": True,
        "source_dream_sha256": "a" * 64,
        "proposer_digest": "b" * 64,
        "issued_at_utc": "2026-11-20T04:10:00Z",
        "expires_at_utc": "2026-11-20T04:15:00Z",
        "metric": "gpu_utilization_pct",
        "operator": "ge",
        "threshold": 80,
        "unit": "percent",
    }
    obs = {
        "source_dream_sha256": "a" * 64,
        "cycle_sha256": "c" * 64,
        "evaluator_digest": "d" * 64,
        "observed_at_utc": "2026-11-20T04:11:00Z",
        "evidence_sha256": "e" * 64,
        "metric": "gpu_utilization_pct",
        "unit": "percent",
        "value": 0,
    }
    return plan, obs


def run(change=None, now=NOW):
    plan, obs = pair()
    if change is not None:
        change(plan, obs)
    return review_next_cycle(plan=plan, observation=obs, now_utc=now)


def test_target_eighty_zero_utilization_cannot_be_passed():
    result = run()
    assert result["verdict"] == "DECLARED_PREDICATE_NOT_MET_UNATTESTED"
    assert result["metric"] == "gpu_utilization_pct"
    assert result["operator"] == "ge"
    assert result["production_qualified"] is False


def test_ambiguous_natural_language_target_has_no_comparator():
    result = run(lambda p, o: p.update(operator="target"))
    assert result["reason"] == "COMPARATOR_AMBIGUOUS_OR_MISSING"
    result = run(lambda p, o: p.update(operator=None))
    assert result["reason"] == "COMPARATOR_AMBIGUOUS_OR_MISSING"


def test_explicit_numeric_threshold_can_be_met_but_not_trusted():
    result = run(lambda p, o: o.update(value=85))
    assert result["verdict"] == "DECLARED_PREDICATE_MET_UNATTESTED"
    for key in (
        "independent_measurement_verified", "evaluator_identity_authenticated",
        "pre_registration_proven", "training_improvement_proven",
        "source_or_runtime_change_authorized", "production_qualified",
    ):
        assert result[key] is False


def test_explicit_ceiling_has_separate_semantics():
    result = run(
        lambda p, o: p.update(operator="le", threshold=80)
    )
    assert result["verdict"] == "DECLARED_PREDICATE_MET_UNATTESTED"


def test_missing_preregistered_plan_refused():
    result = run(lambda p, o: p.update(pre_registered=False))
    assert result["reason"] == "PLAN_UNFROZEN_OR_UNSUPPORTED"
    result = run(lambda p, o: p.update(pre_registered=1))
    assert result["reason"] == "PLAN_UNFROZEN_OR_UNSUPPORTED"


def test_source_dream_digest_mismatch_is_hold():
    result = run(lambda p, o: o.update(source_dream_sha256="0" * 64))
    assert result["reason"] == "SOURCE_DREAM_BINDING_MISMATCH"


def test_non_next_cycle_and_non_fresh_replay_are_hold():
    result = run(lambda p, o: o.update(observed_at_utc="2026-11-20T04:09:00Z"))
    assert result["reason"] == "NOT_NEXT_DECLARED_CYCLE_WINDOW"
    result = run(now="2026-11-20T04:32:00Z")
    assert result["reason"] == "OBSERVATION_UNAVAILABLE_OR_STALE"


def test_unknown_or_invalid_date_is_hold():
    result = run(now="local_now")
    assert result["reason"] == "CURRENT_CLOCK_UNOBSERVED"
    result = run(lambda p, o: p.update(issued_at_utc="not-a-time"))
    assert result["reason"] == "PLAN_OR_OBSERVATION_CLOCK_UNVERIFIED"


def test_duplicate_evaluator_or_owner_proof_by_digest_refused():
    result = run(
        lambda p, o: o.update(evaluator_digest=p["proposer_digest"])
    )
    assert result["reason"] == "INDEPENDENT_EVALUATOR_CLAIM_UNVERIFIED"


def test_missing_evidence_digest_refused():
    result = run(lambda p, o: o.update(evidence_sha256=None))
    assert result["reason"] == "NEXT_CYCLE_OR_EVIDENCE_DIGEST_UNVERIFIED"


def test_nonfinite_measurement_and_boolean_are_rejected():
    for value in (float("nan"), float("inf"), True, -1, 101):
        result = run(lambda p, o: o.update(value=value))
        assert result["reason"] == "MEASUREMENT_INVALID_OR_UNOBSERVED"


def test_threshold_finite_and_in_metric_bounds():
    for value in (101, float("-inf"), False):
        result = run(lambda p, o: p.update(threshold=value))
        assert result["reason"] == "DECLARED_THRESHOLD_INVALID"


def test_unbounded_python_integers_fail_closed_without_overflow():
    for value in (10**700, -(10**700)):
        result = run(lambda p, o, value=value: o.update(value=value))
        assert result["verdict"] == "HOLD"
        assert result["reason"] == "MEASUREMENT_INVALID_OR_UNOBSERVED"
        result = run(lambda p, o, value=value: p.update(threshold=value))
        assert result["verdict"] == "HOLD"
        assert result["reason"] == "DECLARED_THRESHOLD_INVALID"


def test_finite_numeric_boundary_controls_are_unchanged():
    for value, expected in (
        (0, "DECLARED_PREDICATE_NOT_MET_UNATTESTED"),
        (0.0, "DECLARED_PREDICATE_NOT_MET_UNATTESTED"),
        (100, "DECLARED_PREDICATE_MET_UNATTESTED"),
        (100.0, "DECLARED_PREDICATE_MET_UNATTESTED"),
    ):
        assert run(lambda p, o, value=value: o.update(value=value))["verdict"] == expected


def test_metric_and_unit_mismatch_hold():
    result = run(lambda p, o: o.update(unit="celsius"))
    assert result["reason"] == "METRIC_UNIT_OR_IDENTITY_MISMATCH"
    result = run(lambda p, o: p.update(metric="system_go_live"))
    assert result["reason"] == "METRIC_NOT_EXPLICIT"


def test_temperature_and_power_need_explicit_operator():
    for metric, unit, value, threshold in (
        ("gpu_temperature_c", "celsius", 63, 75),
        ("gpu_power_w", "watt", 28.5, 30),
    ):
        plan, obs = pair()
        plan.update(metric=metric, unit=unit, operator="le", threshold=threshold)
        obs.update(metric=metric, unit=unit, value=value)
        result = review_next_cycle(plan=plan, observation=obs, now_utc=NOW)
        assert result["verdict"] == "DECLARED_PREDICATE_MET_UNATTESTED"


def test_source_claims_do_not_change_input_or_echo_digest():
    plan, obs = pair()
    copy = deepcopy((plan, obs))
    result = review_next_cycle(plan=plan, observation=obs, now_utc=NOW)
    assert (plan, obs) == copy
    assert plan["source_dream_sha256"] not in str(result)


def test_extra_fields_never_create_a_promotion_control():
    plan, obs = pair()
    obs["verified_real_training"] = True
    result = review_next_cycle(plan=plan, observation=obs, now_utc=NOW)
    assert result["reason"] == "OBSERVATION_SCHEMA_INVALID"


def test_unbounded_time_window_refused():
    result = run(
        lambda p, o: p.update(expires_at_utc="2026-11-20T06:00:00Z")
    )
    assert result["reason"] == "PLAN_WINDOW_UNBOUNDED"
