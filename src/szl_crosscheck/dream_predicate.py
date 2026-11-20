"""Source-only next-cycle dream-check comparator; never interpret vague prose as PASS.

This validates caller-declared, explicitly preregistered numeric predicates.
It does not authenticate observation data, timestamps, evaluator independence,
signature, or the GPU that produced an observation. No IO, agents or models.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import math
import re

SCHEMA = "szl.dream-next-cycle-predicate/v1"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_TIME = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z"
)
_PLAN = {
    "schema", "pre_registered", "source_dream_sha256", "proposer_digest",
    "issued_at_utc", "expires_at_utc", "metric", "operator", "threshold",
    "unit",
}
_OBS = {
    "source_dream_sha256", "cycle_sha256", "evaluator_digest",
    "observed_at_utc", "evidence_sha256", "metric", "unit", "value",
}
_METRICS = {
    "gpu_utilization_pct": ("percent", 0, 100),
    "gpu_temperature_c": ("celsius", 0, 125),
    "gpu_power_w": ("watt", 0, 3000),
}
_OPERATORS = {
    "ge": lambda a, b: a >= b,
    "gt": lambda a, b: a > b,
    "le": lambda a, b: a <= b,
    "lt": lambda a, b: a < b,
    "eq": lambda a, b: a == b,
}
MAX_AGE = timedelta(minutes=10)


def _hold(reason: str) -> dict:
    return {
        "schema": SCHEMA,
        "verdict": "HOLD",
        "reason": reason,
        "independent_measurement_verified": False,
        "evaluator_identity_authenticated": False,
        "pre_registration_proven": False,
        "training_improvement_proven": False,
        "source_or_runtime_change_authorized": False,
        "production_qualified": False,
    }


def _utc(value: object) -> datetime | None:
    if type(value) is not str or not _TIME.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _digest(value: object) -> bool:
    return type(value) is str and bool(_SHA.fullmatch(value))


def _number(value: object, bounds: tuple[str, int, int]) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and bounds[1] <= value <= bounds[2]
    )


def review_next_cycle(
    *, plan: object, observation: object, now_utc: str
) -> dict:
    """Compare exact declared metric/operator/threshold against next-cycle value.

    A favourable result is NOT scientific proof. Only an authenticated
    independent verifier can validate actual telemetry and source lineage.
    """
    now = _utc(now_utc)
    if now is None:
        return _hold("CURRENT_CLOCK_UNOBSERVED")
    if type(plan) is not dict or set(plan) != _PLAN:
        return _hold("PLAN_SCHEMA_INVALID")
    if plan.get("schema") != SCHEMA or plan["pre_registered"] is not True:
        return _hold("PLAN_UNFROZEN_OR_UNSUPPORTED")
    if type(observation) is not dict or set(observation) != _OBS:
        return _hold("OBSERVATION_SCHEMA_INVALID")

    prior = plan["source_dream_sha256"]
    if not _digest(prior) or observation["source_dream_sha256"] != prior:
        return _hold("SOURCE_DREAM_BINDING_MISMATCH")
    if (
        not _digest(observation["cycle_sha256"])
        or observation["cycle_sha256"] == prior
        or not _digest(observation["evidence_sha256"])
    ):
        return _hold("NEXT_CYCLE_OR_EVIDENCE_DIGEST_UNVERIFIED")
    proposer = plan["proposer_digest"]
    reviewer = observation["evaluator_digest"]
    if not _digest(proposer) or not _digest(reviewer) or proposer == reviewer:
        return _hold("INDEPENDENT_EVALUATOR_CLAIM_UNVERIFIED")

    started = _utc(plan["issued_at_utc"])
    expires = _utc(plan["expires_at_utc"])
    observed = _utc(observation["observed_at_utc"])
    if started is None or expires is None or observed is None:
        return _hold("PLAN_OR_OBSERVATION_CLOCK_UNVERIFIED")
    if not started < observed <= expires or now < observed:
        return _hold("NOT_NEXT_DECLARED_CYCLE_WINDOW")
    if observed > now + timedelta(seconds=30) or now - observed > MAX_AGE:
        return _hold("OBSERVATION_UNAVAILABLE_OR_STALE")
    if expires - started > timedelta(hours=1):
        return _hold("PLAN_WINDOW_UNBOUNDED")

    metric = plan["metric"]
    if type(metric) is not str or metric not in _METRICS:
        return _hold("METRIC_NOT_EXPLICIT")
    bounds = _METRICS[metric]
    if (
        observation["metric"] != metric
        or plan["unit"] != bounds[0]
        or observation["unit"] != bounds[0]
    ):
        return _hold("METRIC_UNIT_OR_IDENTITY_MISMATCH")
    operator = plan["operator"]
    if type(operator) is not str or operator not in _OPERATORS:
        return _hold("COMPARATOR_AMBIGUOUS_OR_MISSING")
    if not _number(plan["threshold"], bounds):
        return _hold("DECLARED_THRESHOLD_INVALID")
    if not _number(observation["value"], bounds):
        return _hold("MEASUREMENT_INVALID_OR_UNOBSERVED")

    result = _hold("DECLARED_VALUE_COMPARED_NOT_INDEPENDENTLY_VERIFIED")
    if _OPERATORS[operator](observation["value"], plan["threshold"]):
        result["verdict"] = "DECLARED_PREDICATE_MET_UNATTESTED"
    else:
        result["verdict"] = "DECLARED_PREDICATE_NOT_MET_UNATTESTED"
    result["metric"] = metric
    result["operator"] = operator
    return result
