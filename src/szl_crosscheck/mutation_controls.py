"""Source-only, bounded mutation-control review for agentic peer-coded patches.

This is a pure structural check of caller-asserted, untrusted outcomes. It does
NOT execute a test suite, authenticate the evaluator, establish semantic mutation
quality, run an agent, authorize a merge, or change any production controls.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA = "szl.peer-mutation-controls/v1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PLAN_FIELDS = frozenset({
    "preregistered",
    "baseline_revision",
    "candidate_revision",
    "test_revision",
    "evaluator_revision",
    "test_content_sha256",
    "execution_environment_sha256",
    "selected_tests_sha256",
    "selected_test_count",
    "frozen_mutant_set_sha256",
    "declared_mutation_count",
})
OWNERSHIP_FIELDS = frozenset({
    "proposer_digest", "evaluator_digest", "independence_claimed"
})
CONTROL_FIELDS = frozenset({
    "mutant_sha256",
    "test_content_sha256",
    "evaluator_revision",
    "baseline_pass",
    "mutant_pass",
    "run_receipt_sha256",
    "baseline_environment_sha256",
    "mutant_environment_sha256",
    "baseline_selected_tests_sha256",
    "mutant_selected_tests_sha256",
    "baseline_executed_tests",
    "mutant_executed_tests",
    "baseline_skipped_tests",
    "mutant_skipped_tests",
    "mutant_failure_phase",
})
MIN_CONTROLS = 5
MAX_CONTROLS = 32


def frozen_mutant_set_digest(digests: list[str]) -> str:
    """Deterministic *set* fingerprint for preregistration; not attestation.

    Reject invalid/duplicate IDs before using this to declare a preregistration.
    Sorting avoids mutating caller order and makes evidence order-insensitive.
    """
    if (
        type(digests) is not list
        or not MIN_CONTROLS <= len(digests) <= MAX_CONTROLS
        or not all(type(x) is str and HEX64.fullmatch(x) for x in digests)
        or len(set(digests)) != len(digests)
    ):
        raise ValueError("MUTANT_SET_INVALID")
    raw = json.dumps(sorted(digests), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _is_sha(value: Any, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _hold(reason: str, **fields: Any) -> dict[str, Any]:
    result = {
        "schema": SCHEMA,
        "verdict": "HOLD",
        "reason": reason,
        "source_observation_only": True,
        "independent_evaluation_proven": False,
        "preregistration_proven": False,
        "signature_verified": False,
        "patch_correctness_proven": False,
        "promotion_authorized": False,
        "merge_authorized": False,
        "runtime_change_authorized": False,
    }
    result.update(fields)
    return result


def review_mutation_controls(evidence: object) -> dict[str, Any]:
    """Check caller-declared mutation sensitivity without executing anything.

    A positive verdict means *only* that the supplied structure is internally
    consistent. It is not a PASS, release verdict, or independent test witness.
    """
    if type(evidence) is not dict or set(evidence) != {"schema", "plan", "ownership", "controls"}:
        return _hold("ROOT_SCHEMA_INVALID")
    if evidence["schema"] != SCHEMA:
        return _hold("SCHEMA_VERSION_INVALID")

    plan = evidence["plan"]
    if type(plan) is not dict or set(plan) != PLAN_FIELDS:
        return _hold("PLAN_SCHEMA_INVALID")
    if plan["preregistered"] is not True:
        return _hold("PLAN_PREREGISTRATION_UNVERIFIED")
    for field in ("baseline_revision", "candidate_revision", "test_revision", "evaluator_revision"):
        if not _is_sha(plan[field], HEX40):
            return _hold("SOURCE_REVISION_INVALID")
    if plan["baseline_revision"] == plan["candidate_revision"]:
        return _hold("CANDIDATE_SOURCE_UNCHANGED")
    for field in ("test_content_sha256", "execution_environment_sha256", "selected_tests_sha256", "frozen_mutant_set_sha256"):
        if not _is_sha(plan[field], HEX64):
            return _hold("TEST_OR_SET_DIGEST_INVALID")
    selected_count = plan["selected_test_count"]
    if type(selected_count) is not int or not 1 <= selected_count <= 100000:
        return _hold("TEST_POPULATION_POLICY_INVALID")
    n = plan["declared_mutation_count"]
    if type(n) is not int or not MIN_CONTROLS <= n <= MAX_CONTROLS:
        return _hold("MUTATION_COUNT_POLICY_INVALID")

    owners = evidence["ownership"]
    if type(owners) is not dict or set(owners) != OWNERSHIP_FIELDS:
        return _hold("OWNERSHIP_SCHEMA_INVALID")
    if (
        not _is_sha(owners["proposer_digest"], HEX64)
        or not _is_sha(owners["evaluator_digest"], HEX64)
        or owners["proposer_digest"] == owners["evaluator_digest"]
        or owners["independence_claimed"] is not True
    ):
        return _hold("EVALUATOR_INDEPENDENCE_NOT_ESTABLISHED")

    controls = evidence["controls"]
    if type(controls) is not list or len(controls) != n:
        return _hold("MUTATION_COVERAGE_MISSING")
    # Do not leak caller-provided mutant identifiers, paths or prompts in output.
    for control in controls:
        if type(control) is not dict or set(control) != CONTROL_FIELDS:
            return _hold("CONTROL_SCHEMA_INVALID")
        if not all(
            _is_sha(control[field], HEX64)
            for field in (
                "mutant_sha256", "test_content_sha256", "run_receipt_sha256",
                "baseline_environment_sha256", "mutant_environment_sha256",
                "baseline_selected_tests_sha256", "mutant_selected_tests_sha256",
            )
        ) or not _is_sha(control["evaluator_revision"], HEX40):
            return _hold("CONTROL_DIGEST_INVALID")
        if type(control["baseline_pass"]) is not bool or type(control["mutant_pass"]) is not bool:
            return _hold("CONTROL_RESULT_INVALID")
        if (
            control["test_content_sha256"] != plan["test_content_sha256"]
            or control["evaluator_revision"] != plan["evaluator_revision"]
        ):
            return _hold("CONTROL_PROVENANCE_MISMATCH")
        if (
            control["baseline_environment_sha256"] != plan["execution_environment_sha256"]
            or control["mutant_environment_sha256"] != plan["execution_environment_sha256"]
            or control["baseline_selected_tests_sha256"] != plan["selected_tests_sha256"]
            or control["mutant_selected_tests_sha256"] != plan["selected_tests_sha256"]
        ):
            return _hold("EXECUTION_ENVIRONMENT_OR_TEST_POPULATION_MISMATCH")
        for field in ("baseline_executed_tests", "mutant_executed_tests"):
            if type(control[field]) is not int or control[field] != selected_count:
                return _hold("TEST_EXECUTION_COVERAGE_UNVERIFIED")
        for field in ("baseline_skipped_tests", "mutant_skipped_tests"):
            if type(control[field]) is not int or control[field] != 0:
                return _hold("TEST_SKIPS_UNVERIFIED")
        if control["mutant_pass"]:
            if control["mutant_failure_phase"] != "none":
                return _hold("CONTROL_OUTCOME_PHASE_INCONSISTENT")
        elif control["mutant_failure_phase"] != "assertion":
            return _hold("NON_ASSERTION_MUTANT_FAILURE")

    mutants = [c["mutant_sha256"] for c in controls]
    receipts = [c["run_receipt_sha256"] for c in controls]
    if len(set(mutants)) != len(mutants) or len(set(receipts)) != len(receipts):
        return _hold("DUPLICATE_MUTATION_OR_RECEIPT")
    if frozen_mutant_set_digest(mutants) != plan["frozen_mutant_set_sha256"]:
        return _hold("FROZEN_MUTATION_POPULATION_MISMATCH")

    reversed_baselines = sum(not c["baseline_pass"] for c in controls)
    if reversed_baselines:
        return _hold("REVERSED_OR_FAILING_BASELINE", count=reversed_baselines)
    survivors = sum(c["mutant_pass"] for c in controls)
    if survivors == n:
        return _hold("ALL_MUTANTS_SURVIVE", survived=survivors, controls=n)
    if survivors:
        return _hold("MUTANTS_SURVIVE", survived=survivors, controls=n)
    response = _hold(
        "DECLARED_MUTATION_KILLS_SUPPORT_INDEPENDENT_REVIEW",
        controls=n,
        declared_kills=n,
    )
    response["verdict"] = "SOURCE_CANDIDATE_FOR_OWNER_REVIEW"
    return response
