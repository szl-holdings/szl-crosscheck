"""Semantic validation for independent Lean-build comparison receipts.

The comparison contract records whether two independently implemented harnesses
produced compatible bounded observations for one source-bound Lean build.  A
``CONSISTENT`` verdict is deliberately narrow: it is not a proof-validity,
theorem-correctness, security, or production-readiness claim.
"""
from __future__ import annotations

import copy
import re
from datetime import datetime
from typing import Any, Mapping

SCHEMA = "szl.lean-build-comparison/v1"
CLAIM_BOUNDARY = (
    "Comparison consistency is not a proof-validity, theorem-correctness, "
    "security, or production-readiness claim."
)
VERDICTS = frozenset({"CONSISTENT", "DIVERGENT", "INCOMPARABLE"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "generated_at",
        "target_build",
        "harness_a",
        "harness_b",
        "comparison",
        "verdict",
        "verdict_reasons",
        "claim_boundary",
    }
)
TARGET_KEYS = frozenset(
    {
        "artifact_ref",
        "artifact_sha256",
        "lean_version",
        "entrypoint",
        "theorem_name",
        "reference_statement_sha256",
        "declared_axioms",
    }
)
HARNESS_KEYS = frozenset(
    {
        "harness_id",
        "runner_identity",
        "implementation_sha256",
        "source_revision",
        "completed_at",
        "rebuilt",
        "kernel_checked",
        "exit_code",
        "artifact_sha256",
        "observed_statement_sha256",
        "statement_matches_reference",
        "observed_axioms",
        "sorries_in_final_chain",
        "dependency_cone",
        "log_sha256",
        "errors",
    }
)
DEPENDENCY_CONE_KEYS = frozenset(
    {"declared_theorems", "load_bearing_theorems", "sha256"}
)
COMPARISON_KEYS = frozenset(
    {
        "artifact_digest_agreement",
        "harness_implementation_independent",
        "runner_identity_independent",
        "statement_agreement",
        "axiom_surface_agreement",
        "dependency_cone_agreement",
        "kernel_outcome_agreement",
        "notes",
    }
)


class ReceiptValidationError(ValueError):
    """Raised when a Lean comparison receipt is malformed or self-inconsistent."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReceiptValidationError(f"{label} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise ReceiptValidationError(f"{label} contains a non-string key")
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    observed = frozenset(value)
    missing = sorted(expected - observed)
    unknown = sorted(observed - expected)
    if missing or unknown:
        raise ReceiptValidationError(
            f"{label} key mismatch: missing={missing}, unknown={unknown}"
        )


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ReceiptValidationError(f"{label} must be one non-empty trimmed string")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ReceiptValidationError(f"{label} must be boolean")
    return value


def _nullable_boolean(value: Any, label: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ReceiptValidationError(f"{label} must be boolean or null")
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReceiptValidationError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ReceiptValidationError(f"{label} must be >= {minimum}")
    return value


def _nullable_integer(
    value: Any, label: str, *, minimum: int | None = None
) -> int | None:
    if value is None:
        return None
    return _integer(value, label, minimum=minimum)


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ReceiptValidationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _nullable_digest(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _digest(value, label)


def _git_revision(value: Any, label: str) -> str:
    if not isinstance(value, str) or not GIT_SHA_RE.fullmatch(value):
        raise ReceiptValidationError(f"{label} must be an exact lowercase Git SHA")
    return value


def _timestamp(value: Any, label: str) -> str:
    text = _text(value, label)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ReceiptValidationError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReceiptValidationError(f"{label} must include a timezone")
    return text


def _text_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ReceiptValidationError(f"{label} must be an array")
    output = [_text(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if len(output) != len(set(output)):
        raise ReceiptValidationError(f"{label} must not contain duplicates")
    return output


def _validate_target(value: Any) -> Mapping[str, Any]:
    target = _mapping(value, "target_build")
    _exact_keys(target, TARGET_KEYS, "target_build")
    _text(target["artifact_ref"], "target_build.artifact_ref")
    _digest(target["artifact_sha256"], "target_build.artifact_sha256")
    _text(target["lean_version"], "target_build.lean_version")
    _text(target["entrypoint"], "target_build.entrypoint")
    _text(target["theorem_name"], "target_build.theorem_name")
    _nullable_digest(
        target["reference_statement_sha256"],
        "target_build.reference_statement_sha256",
    )
    _text_list(target["declared_axioms"], "target_build.declared_axioms")
    return target


def _validate_dependency_cone(value: Any, label: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    cone = _mapping(value, label)
    _exact_keys(cone, DEPENDENCY_CONE_KEYS, label)
    declared = _integer(cone["declared_theorems"], f"{label}.declared_theorems", minimum=0)
    load_bearing = _integer(
        cone["load_bearing_theorems"],
        f"{label}.load_bearing_theorems",
        minimum=0,
    )
    if load_bearing > declared:
        raise ReceiptValidationError(
            f"{label}.load_bearing_theorems cannot exceed declared_theorems"
        )
    _digest(cone["sha256"], f"{label}.sha256")
    return cone


def _validate_harness(
    value: Any, label: str, target: Mapping[str, Any]
) -> Mapping[str, Any]:
    harness = _mapping(value, label)
    _exact_keys(harness, HARNESS_KEYS, label)
    _text(harness["harness_id"], f"{label}.harness_id")
    _text(harness["runner_identity"], f"{label}.runner_identity")
    _digest(harness["implementation_sha256"], f"{label}.implementation_sha256")
    _git_revision(harness["source_revision"], f"{label}.source_revision")
    _timestamp(harness["completed_at"], f"{label}.completed_at")
    _boolean(harness["rebuilt"], f"{label}.rebuilt")
    _boolean(harness["kernel_checked"], f"{label}.kernel_checked")
    _integer(harness["exit_code"], f"{label}.exit_code")
    _digest(harness["artifact_sha256"], f"{label}.artifact_sha256")
    observed_statement = _nullable_digest(
        harness["observed_statement_sha256"],
        f"{label}.observed_statement_sha256",
    )
    statement_flag = _nullable_boolean(
        harness["statement_matches_reference"],
        f"{label}.statement_matches_reference",
    )
    reference_statement = target["reference_statement_sha256"]
    expected_statement_flag = (
        None
        if reference_statement is None or observed_statement is None
        else observed_statement == reference_statement
    )
    if statement_flag is not expected_statement_flag:
        raise ReceiptValidationError(
            f"{label}.statement_matches_reference disagrees with the recorded digests"
        )
    _text_list(harness["observed_axioms"], f"{label}.observed_axioms")
    _nullable_integer(
        harness["sorries_in_final_chain"],
        f"{label}.sorries_in_final_chain",
        minimum=0,
    )
    _validate_dependency_cone(harness["dependency_cone"], f"{label}.dependency_cone")
    _digest(harness["log_sha256"], f"{label}.log_sha256")
    _text_list(harness["errors"], f"{label}.errors")
    return harness


def _validate_comparison(value: Any) -> Mapping[str, Any]:
    comparison = _mapping(value, "comparison")
    _exact_keys(comparison, COMPARISON_KEYS, "comparison")
    _boolean(
        comparison["artifact_digest_agreement"],
        "comparison.artifact_digest_agreement",
    )
    _boolean(
        comparison["harness_implementation_independent"],
        "comparison.harness_implementation_independent",
    )
    _boolean(
        comparison["runner_identity_independent"],
        "comparison.runner_identity_independent",
    )
    _nullable_boolean(comparison["statement_agreement"], "comparison.statement_agreement")
    _nullable_boolean(
        comparison["axiom_surface_agreement"],
        "comparison.axiom_surface_agreement",
    )
    _nullable_boolean(
        comparison["dependency_cone_agreement"],
        "comparison.dependency_cone_agreement",
    )
    _boolean(comparison["kernel_outcome_agreement"], "comparison.kernel_outcome_agreement")
    _text_list(comparison["notes"], "comparison.notes")
    return comparison


def derive_comparison(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Derive all bounded comparison fields from recorded observations."""
    target = _mapping(receipt.get("target_build"), "target_build")
    harness_a = _mapping(receipt.get("harness_a"), "harness_a")
    harness_b = _mapping(receipt.get("harness_b"), "harness_b")

    target_artifact = target.get("artifact_sha256")
    artifact_agreement = (
        harness_a.get("artifact_sha256") == target_artifact
        and harness_b.get("artifact_sha256") == target_artifact
    )
    implementation_independent = (
        harness_a.get("implementation_sha256")
        != harness_b.get("implementation_sha256")
    )
    runner_independent = (
        harness_a.get("harness_id") != harness_b.get("harness_id")
        and harness_a.get("runner_identity") != harness_b.get("runner_identity")
    )

    reference = target.get("reference_statement_sha256")
    observed_a = harness_a.get("observed_statement_sha256")
    observed_b = harness_b.get("observed_statement_sha256")
    flag_a = harness_a.get("statement_matches_reference")
    flag_b = harness_b.get("statement_matches_reference")
    if reference is None or observed_a is None or observed_b is None:
        statement_agreement: bool | None = None
    elif flag_a is None or flag_b is None:
        statement_agreement = None
    else:
        statement_agreement = bool(
            observed_a == reference
            and observed_b == reference
            and flag_a is True
            and flag_b is True
        )

    expected_axioms = sorted(target.get("declared_axioms") or [])
    axiom_agreement = bool(
        sorted(harness_a.get("observed_axioms") or []) == expected_axioms
        and sorted(harness_b.get("observed_axioms") or []) == expected_axioms
    )

    cone_a = harness_a.get("dependency_cone")
    cone_b = harness_b.get("dependency_cone")
    if cone_a is None or cone_b is None:
        dependency_agreement: bool | None = None
    else:
        dependency_agreement = bool(
            cone_a.get("declared_theorems") == cone_b.get("declared_theorems")
            and cone_a.get("load_bearing_theorems")
            == cone_b.get("load_bearing_theorems")
            and cone_a.get("sha256") == cone_b.get("sha256")
        )

    outcome_a = (
        harness_a.get("rebuilt"),
        harness_a.get("kernel_checked"),
        harness_a.get("exit_code"),
        harness_a.get("sorries_in_final_chain"),
    )
    outcome_b = (
        harness_b.get("rebuilt"),
        harness_b.get("kernel_checked"),
        harness_b.get("exit_code"),
        harness_b.get("sorries_in_final_chain"),
    )

    return {
        "artifact_digest_agreement": artifact_agreement,
        "harness_implementation_independent": implementation_independent,
        "runner_identity_independent": runner_independent,
        "statement_agreement": statement_agreement,
        "axiom_surface_agreement": axiom_agreement,
        "dependency_cone_agreement": dependency_agreement,
        "kernel_outcome_agreement": outcome_a == outcome_b,
        "notes": [],
    }


def derive_verdict(
    receipt: Mapping[str, Any], comparison: Mapping[str, Any] | None = None
) -> tuple[str, list[str]]:
    """Return the only verdict justified by the recorded bounded evidence."""
    comparison = comparison or derive_comparison(receipt)
    target = _mapping(receipt.get("target_build"), "target_build")
    harnesses = (
        ("harness_a", _mapping(receipt.get("harness_a"), "harness_a")),
        ("harness_b", _mapping(receipt.get("harness_b"), "harness_b")),
    )

    incomparable: list[str] = []
    if comparison.get("harness_implementation_independent") is not True:
        incomparable.append("harness implementations are not independently identified")
    if comparison.get("runner_identity_independent") is not True:
        incomparable.append("harness or runner identities are not independent")
    if comparison.get("statement_agreement") is None:
        incomparable.append("statement-fidelity evidence is incomplete")
    if comparison.get("dependency_cone_agreement") is None:
        incomparable.append("dependency-cone evidence is incomplete")

    target_artifact = target.get("artifact_sha256")
    for label, harness in harnesses:
        if harness.get("artifact_sha256") != target_artifact:
            incomparable.append(f"{label} did not inspect the target artifact digest")
        if harness.get("errors"):
            incomparable.append(f"{label} reported execution errors")
        if harness.get("rebuilt") is not True:
            incomparable.append(f"{label} did not complete the rebuild")
        if harness.get("kernel_checked") is not True:
            incomparable.append(f"{label} did not complete the kernel check")
        if harness.get("exit_code") != 0:
            incomparable.append(f"{label} exited non-zero")
        if harness.get("sorries_in_final_chain") is None:
            incomparable.append(f"{label} did not measure final-chain sorries")

    if incomparable:
        return "INCOMPARABLE", incomparable

    divergent: list[str] = []
    agreement_labels = (
        ("artifact_digest_agreement", "target artifact digests disagree"),
        ("statement_agreement", "observed theorem statements disagree"),
        ("axiom_surface_agreement", "observed axiom surfaces disagree"),
        ("dependency_cone_agreement", "observed dependency cones disagree"),
        ("kernel_outcome_agreement", "kernel outcomes disagree"),
    )
    for key, reason in agreement_labels:
        if comparison.get(key) is not True:
            divergent.append(reason)
    if divergent:
        return "DIVERGENT", divergent

    return "CONSISTENT", [
        "all bounded observations agree across independently identified harnesses"
    ]


def validate_lean_build_receipt(receipt: Any) -> dict[str, Any]:
    """Validate structure and prove that comparison and verdict are derived.

    The returned value is a defensive copy.  Validation never upgrades a
    ``CONSISTENT`` comparison into a proof-validity or theorem-correctness claim.
    """
    value = _mapping(receipt, "receipt")
    _exact_keys(value, TOP_LEVEL_KEYS, "receipt")
    if value["schema"] != SCHEMA:
        raise ReceiptValidationError(f"schema must be {SCHEMA}")
    _timestamp(value["generated_at"], "generated_at")
    target = _validate_target(value["target_build"])
    _validate_harness(value["harness_a"], "harness_a", target)
    _validate_harness(value["harness_b"], "harness_b", target)
    supplied_comparison = _validate_comparison(value["comparison"])

    verdict = value["verdict"]
    if verdict not in VERDICTS:
        raise ReceiptValidationError(f"verdict must be one of {sorted(VERDICTS)}")
    reasons = _text_list(value["verdict_reasons"], "verdict_reasons")
    if not reasons:
        raise ReceiptValidationError("verdict_reasons must contain at least one reason")
    if value["claim_boundary"] != CLAIM_BOUNDARY:
        raise ReceiptValidationError("claim_boundary is absent or altered")

    derived_comparison = derive_comparison(value)
    if dict(supplied_comparison) != derived_comparison:
        raise ReceiptValidationError("comparison fields are not derived from the observations")
    derived_verdict, derived_reasons = derive_verdict(value, derived_comparison)
    if verdict != derived_verdict or reasons != derived_reasons:
        raise ReceiptValidationError(
            "verdict or verdict_reasons are not derived from the comparison evidence"
        )
    return copy.deepcopy(dict(value))


__all__ = [
    "CLAIM_BOUNDARY",
    "ReceiptValidationError",
    "SCHEMA",
    "VERDICTS",
    "derive_comparison",
    "derive_verdict",
    "validate_lean_build_receipt",
]
