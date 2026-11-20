"""Opt-in exact case-population check for caller-declared harness evaluations.

This module is pure arithmetic and hashing. Neither caller-provided case IDs nor
an expectation digest authenticates a preregistered population or its evaluator.
No network, filesystem, model, agent, or provider operations occur here.
"""

from __future__ import annotations

import hashlib
import json
import re

from .harness_evolution import MAX_CASES, MIN_HELDOUT, MIN_REGRESSION, review_harness_pair

FROZEN_POPULATION_SCHEMA = "szl.harness-frozen-population/v1"
_CASE_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_EXPECTED_KEYS = {"schema", "heldout_case_digests", "regression_case_digests"}


def validate_policy(policy: object) -> tuple[set[str], set[str]] | None:
    """Validate exact, unique, case-sensitive expected populations by split.

    Kimi's source-only reviewer suggested a globally unique two-split contract
    and explicit rejection of same-size split-swaps as a negative control.
    """
    if type(policy) is not dict or set(policy) != _EXPECTED_KEYS:
        return None
    if type(policy["schema"]) is not str or policy["schema"] != FROZEN_POPULATION_SCHEMA:
        return None
    heldout = policy["heldout_case_digests"]
    regression = policy["regression_case_digests"]
    if type(heldout) is not list or type(regression) is not list:
        return None
    if len(heldout) < MIN_HELDOUT or len(regression) < MIN_REGRESSION:
        return None
    if len(heldout) + len(regression) > MAX_CASES:
        return None
    seen: set[str] = set()
    for digest in heldout + regression:
        if type(digest) is not str or not _CASE_DIGEST.fullmatch(digest):
            return None
        if digest in seen:
            return None
        seen.add(digest)
    return set(heldout), set(regression)


def _policy_hash(heldout: set[str], regression: set[str]) -> str:
    """Canonical identity for equality checking, never a signature or timestamp."""
    payload = {
        "schema": FROZEN_POPULATION_SCHEMA,
        "heldout_case_digests": sorted(heldout),
        "regression_case_digests": sorted(regression),
    }
    wire = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(wire.encode("utf-8")).hexdigest()


def review_frozen_harness_pair(evidence: object, expected_policy: object) -> dict:
    """Admit source-only owner review only if both gates and exact sets agree.

    The existing pair reviewer is unchanged. Expected case sets must be frozen
    by an independent owner before either result is obtained; this function
    cannot establish that fact, authenticate inputs, or authorize execution.
    Results disclose aggregate coverage counts, never private case digests.
    """
    base = review_harness_pair(evidence)
    expected = validate_policy(expected_policy)
    if expected is None:
        return {
            **base,
            "verdict": "HOLD",
            "reason": "FROZEN_POPULATION_POLICY_INVALID",
            "frozen_population_complete": False,
            "population_preregistration_proven": False,
        }

    expected_heldout, expected_regression = expected
    supplement = {
        "frozen_population_schema": FROZEN_POPULATION_SCHEMA,
        "frozen_population_sha256": _policy_hash(expected_heldout, expected_regression),
        "frozen_population_complete": False,
        "population_preregistration_proven": False,
    }
    if base["verdict"] != "SOURCE_CANDIDATE_FOR_OWNER_REVIEW":
        return {**base, **supplement}

    # A positive existing review implies validated typed rows, unique case IDs
    # and split labels. We still require complete identity, not merely counts.
    observed_heldout = {
        row["case_digest"] for row in evidence["pairs"] if row["split"] == "heldout"
    }
    observed_regression = {
        row["case_digest"] for row in evidence["pairs"] if row["split"] == "regression"
    }
    counts = {
        "expected_heldout_count": len(expected_heldout),
        "observed_heldout_count": len(observed_heldout),
        "missing_heldout_count": len(expected_heldout - observed_heldout),
        "unexpected_heldout_count": len(observed_heldout - expected_heldout),
        "expected_regression_count": len(expected_regression),
        "observed_regression_count": len(observed_regression),
        "missing_regression_count": len(expected_regression - observed_regression),
        "unexpected_regression_count": len(observed_regression - expected_regression),
    }
    complete = observed_heldout == expected_heldout and observed_regression == expected_regression
    reviewed = {**base, **supplement, **counts, "frozen_population_complete": complete}
    if not complete:
        reviewed["verdict"] = "HOLD"
        reviewed["reason"] = "FROZEN_POPULATION_MISMATCH"
    return reviewed
