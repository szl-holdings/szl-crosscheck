"""Bounded paired-trace arithmetic for an independently governed agent-harness change.

This module has no tools, filesystem, network, model imports or side effects.
An input record can be invented: checking the record's shape or arithmetic is
NOT authentication, independent evaluation, deployment or proof of improvement.
"""

from __future__ import annotations

import math
import re

SCHEMA = "szl.harness-evolution-pair/v1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PLAN_FIELDS = {
    "pre_registered",
    "plan_revision",
    "baseline_harness_revision",
    "candidate_harness_revision",
    "model_revision",
    "evaluator_revision",
    "heldout_revision",
    "max_tokens_per_case",
    "max_tools_per_case",
    "max_token_ratio_basis_points",
    "minimum_net_gain_cases",
    "candidate_family_size",
    "familywise_alpha_ppm",
}
PAIR_FIELDS = {
    "case_digest",
    "split",
    "baseline_pass",
    "candidate_pass",
    "baseline_tokens",
    "candidate_tokens",
    "baseline_tools",
    "candidate_tools",
}
MIN_HELDOUT = 30
MIN_REGRESSION = 5
MAX_CASES = 512


def _hold(reason: str, **extra: object) -> dict:
    response = {
        "schema": SCHEMA,
        "verdict": "HOLD",
        "reason": reason,
        "source_evidence_only": True,
        "trusted_evaluator_proven": False,
        "plan_preregistration_proven": False,
        "model_quality_proven": False,
        "promotion_authorized": False,
        "runtime_change_authorized": False,
    }
    response.update(extra)
    return response


def _sha(value: object, pattern: re.Pattern) -> bool:
    return type(value) is str and bool(pattern.fullmatch(value))


def _positive(value: object, *, lower: int = 1, upper: int) -> bool:
    return type(value) is int and lower <= value <= upper


def _pair(row: object, policy: dict) -> str | None:
    if type(row) is not dict or set(row) != PAIR_FIELDS:
        return "PAIR_SCHEMA_INVALID"
    if not _sha(row["case_digest"], HEX64) or row["split"] not in (
        "heldout", "regression"
    ):
        return "CASE_ID_OR_SPLIT_INVALID"
    for key in ("baseline_pass", "candidate_pass"):
        if type(row[key]) is not bool:
            return "PASS_FLAG_NOT_BOOLEAN"
    for side in ("baseline", "candidate"):
        if not _positive(
            row[f"{side}_tokens"],
            upper=policy["max_tokens_per_case"],
        ):
            return "PER_CASE_TOKEN_BUDGET_INVALID"
        if not _positive(
            row[f"{side}_tools"],
            lower=0,
            upper=policy["max_tools_per_case"],
        ):
            return "PER_CASE_TOOL_BUDGET_INVALID"
    return None


def _one_sided_exact(wins: int, losses: int) -> tuple[int, int]:
    """Under exchangeable discordant pairs, P(X >= wins | p=.5), exact."""
    total = wins + losses
    return sum(math.comb(total, i) for i in range(wins, total + 1)), 2**total


def review_harness_pair(evidence: object) -> dict:
    """Review caller-claimed matched task outcomes; never verify their provenance.

    A positive return is only SOURCE_CANDIDATE_FOR_OWNER_REVIEW, never an
    independent measurement or authorization. No task text or identifiers
    appear in the output.
    """
    if type(evidence) is not dict or set(evidence) != {
        "schema", "plan", "ownership", "pairs"
    }:
        return _hold("ROOT_SCHEMA_INVALID")
    if evidence["schema"] != SCHEMA:
        return _hold("SCHEMA_VERSION_INVALID")
    plan = evidence["plan"]
    if type(plan) is not dict or set(plan) != PLAN_FIELDS:
        return _hold("PLAN_SCHEMA_INVALID")
    if plan["pre_registered"] is not True:
        return _hold("PLAN_PREREGISTRATION_UNVERIFIED")
    for name in (
        "plan_revision", "baseline_harness_revision",
        "candidate_harness_revision", "model_revision", "evaluator_revision",
    ):
        if not _sha(plan[name], HEX40):
            return _hold("SOURCE_REVISION_INVALID")
    if plan["baseline_harness_revision"] == plan["candidate_harness_revision"]:
        return _hold("NO_CANDIDATE_SOURCE_CHANGE")
    if not _sha(plan["heldout_revision"], HEX64):
        return _hold("HELDOUT_SUITE_DIGEST_INVALID")
    limits = (
        ("max_tokens_per_case", 1, 200000),
        ("max_tools_per_case", 0, 10000),
        ("max_token_ratio_basis_points", 1, 15000),
        ("minimum_net_gain_cases", 1, MAX_CASES),
        ("candidate_family_size", 1, 128),
        ("familywise_alpha_ppm", 1, 50000),
    )
    for field, lower, upper in limits:
        if not _positive(plan[field], lower=lower, upper=upper):
            return _hold("EVALUATION_POLICY_INVALID")

    owners = evidence["ownership"]
    if type(owners) is not dict or set(owners) != {
        "proposer_digest", "evaluator_digest"
    }:
        return _hold("OWNERSHIP_SCHEMA_INVALID")
    if (
        not _sha(owners["proposer_digest"], HEX64)
        or not _sha(owners["evaluator_digest"], HEX64)
        or owners["proposer_digest"] == owners["evaluator_digest"]
    ):
        return _hold("INDEPENDENT_EVALUATOR_CLAIM_MISSING")

    rows = evidence["pairs"]
    if type(rows) is not list or not 1 <= len(rows) <= MAX_CASES:
        return _hold("PAIR_COUNT_INVALID")
    heldout = []
    regressions = []
    seen: set[str] = set()
    for row in rows:
        problem = _pair(row, plan)
        if problem:
            return _hold(problem)
        if row["case_digest"] in seen:
            return _hold("DUPLICATE_CASE_ID")
        seen.add(row["case_digest"])
        (heldout if row["split"] == "heldout" else regressions).append(row)

    if len(heldout) < MIN_HELDOUT or len(regressions) < MIN_REGRESSION:
        return _hold("MINIMUM_COVERAGE_NOT_MET")
    if any(
        row["baseline_pass"] and not row["candidate_pass"]
        for row in regressions
    ):
        return _hold("PRIOR_CAPABILITY_REGRESSION", regression_cases=len(regressions))
    # A single combined budget can be gamed by spending too much on heldout
    # tasks and compensating with near-zero work on prior-capability probes.
    # Compare each frozen stratum separately; never shift cost between them.
    for label, stratum in (("heldout", heldout), ("regression", regressions)):
        baseline_cost = sum(row["baseline_tokens"] for row in stratum)
        candidate_cost = sum(row["candidate_tokens"] for row in stratum)
        if candidate_cost * 10000 > (
            baseline_cost * plan["max_token_ratio_basis_points"]
        ):
            return _hold("TOKEN_COST_REGRESSION", split=label)
    base_tokens = sum(row["baseline_tokens"] for row in rows)
    candidate_tokens = sum(row["candidate_tokens"] for row in rows)

    wins = sum(not row["baseline_pass"] and row["candidate_pass"] for row in heldout)
    losses = sum(row["baseline_pass"] and not row["candidate_pass"] for row in heldout)
    if wins - losses < plan["minimum_net_gain_cases"]:
        return _hold(
            "PAIRED_GAIN_BELOW_PREREGISTERED_THRESHOLD",
            heldout_pairs=len(heldout),
            improved=wins,
            regressed=losses,
        )
    numerator, denominator = _one_sided_exact(wins, losses)
    if numerator * 1_000_000 * plan["candidate_family_size"] > (
        denominator * plan["familywise_alpha_ppm"]
    ):
        return _hold(
            "MULTIPLICITY_ADJUSTED_SIGN_TEST_NOT_MET",
            heldout_pairs=len(heldout),
            improved=wins,
            regressed=losses,
            p_exact=f"{numerator}/{denominator}",
        )

    result = _hold(
        "DECLARED_PAIRED_ARITHMETIC_SUPPORTS_FURTHER_REVIEW",
        heldout_pairs=len(heldout),
        regression_pairs=len(regressions),
        improved=wins,
        regressed=losses,
        p_exact=f"{numerator}/{denominator}",
        candidate_family_size=plan["candidate_family_size"],
        total_baseline_tokens=base_tokens,
        total_candidate_tokens=candidate_tokens,
    )
    result["verdict"] = "SOURCE_CANDIDATE_FOR_OWNER_REVIEW"
    return result
