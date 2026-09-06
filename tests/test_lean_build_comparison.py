# SPDX-License-Identifier: Apache-2.0
"""Adversarial tests for the Lean-build comparison receipt contract."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from szl_crosscheck.lean_build import (
    CLAIM_BOUNDARY,
    ReceiptValidationError,
    VERDICTS,
    derive_comparison,
    derive_verdict,
    validate_lean_build_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas" / "lean-build-comparison-v1.json").read_text(encoding="utf-8")
)


def _harness(
    *,
    harness_id: str,
    runner_identity: str,
    implementation_sha256: str,
    log_sha256: str,
) -> dict:
    return {
        "harness_id": harness_id,
        "runner_identity": runner_identity,
        "implementation_sha256": implementation_sha256,
        "source_revision": "1" * 40,
        "completed_at": "2026-09-06T12:00:00Z",
        "rebuilt": True,
        "kernel_checked": True,
        "exit_code": 0,
        "artifact_sha256": "a" * 64,
        "observed_statement_sha256": "b" * 64,
        "statement_matches_reference": True,
        "observed_axioms": ["propext", "Classical.choice"],
        "sorries_in_final_chain": 0,
        "dependency_cone": {
            "declared_theorems": 281,
            "load_bearing_theorems": 73,
            "sha256": "d" * 64,
        },
        "log_sha256": log_sha256,
        "errors": [],
    }


def _receipt() -> dict:
    value = {
        "schema": "szl.lean-build-comparison/v1",
        "generated_at": "2026-09-06T12:00:01Z",
        "target_build": {
            "artifact_ref": "ghcr.io/example/flt-lean@sha256:" + "a" * 64,
            "artifact_sha256": "a" * 64,
            "lean_version": "4.19.0",
            "entrypoint": "FermatLastTheorem.lean",
            "theorem_name": "FermatLastTheorem.fermat_last_theorem",
            "reference_statement_sha256": "b" * 64,
            "declared_axioms": ["Classical.choice", "propext"],
        },
        "harness_a": _harness(
            harness_id="native-lake-build",
            runner_identity="github-hosted-ubuntu-24.04-a",
            implementation_sha256="c" * 64,
            log_sha256="e" * 64,
        ),
        "harness_b": _harness(
            harness_id="containerized-lean-check",
            runner_identity="github-hosted-ubuntu-24.04-b",
            implementation_sha256="f" * 64,
            log_sha256="0" * 64,
        ),
        "comparison": {},
        "verdict": "INCOMPARABLE",
        "verdict_reasons": ["placeholder"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    value["comparison"] = derive_comparison(value)
    value["verdict"], value["verdict_reasons"] = derive_verdict(
        value, value["comparison"]
    )
    return value


def _rederive(value: dict) -> dict:
    value["comparison"] = derive_comparison(value)
    value["verdict"], value["verdict_reasons"] = derive_verdict(
        value, value["comparison"]
    )
    return value


def test_valid_consistent_receipt_is_accepted_without_overclaiming() -> None:
    receipt = _receipt()

    validated = validate_lean_build_receipt(receipt)

    assert validated == receipt
    assert validated is not receipt
    assert validated["verdict"] == "CONSISTENT"
    assert validated["verdict_reasons"] == [
        "all bounded observations agree across independently identified harnesses"
    ]
    assert "proof-validity" in validated["claim_boundary"]
    assert "production-readiness" in validated["claim_boundary"]


def test_verdict_vocabulary_is_exactly_bounded() -> None:
    assert VERDICTS == {"CONSISTENT", "DIVERGENT", "INCOMPARABLE"}
    assert set(SCHEMA["properties"]["verdict"]["enum"]) == VERDICTS
    serialized = json.dumps(SCHEMA, sort_keys=True)
    assert '"BREAK"' not in serialized
    assert '"PROOF_VALID"' not in serialized


def test_schema_requires_source_build_harness_comparison_and_claim_boundary() -> None:
    assert set(SCHEMA["required"]) == {
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
    target_required = set(SCHEMA["properties"]["target_build"]["required"])
    assert {
        "artifact_ref",
        "artifact_sha256",
        "lean_version",
        "entrypoint",
        "theorem_name",
        "reference_statement_sha256",
        "declared_axioms",
    } == target_required
    harness_required = set(SCHEMA["$defs"]["harness"]["required"])
    assert {
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
    } == harness_required


def test_statement_mismatch_derives_divergent_not_proof_language() -> None:
    receipt = _receipt()
    receipt["harness_b"]["observed_statement_sha256"] = "9" * 64
    receipt["harness_b"]["statement_matches_reference"] = False
    _rederive(receipt)

    validated = validate_lean_build_receipt(receipt)

    assert validated["verdict"] == "DIVERGENT"
    assert validated["verdict_reasons"] == ["observed theorem statements disagree"]


def test_wrong_target_artifact_makes_the_receipt_incomparable() -> None:
    receipt = _receipt()
    receipt["harness_b"]["artifact_sha256"] = "8" * 64
    _rederive(receipt)

    validated = validate_lean_build_receipt(receipt)

    assert validated["verdict"] == "INCOMPARABLE"
    assert validated["verdict_reasons"] == [
        "harness_b did not inspect the target artifact digest"
    ]


def test_same_harness_or_runner_identity_cannot_claim_independence() -> None:
    receipt = _receipt()
    receipt["harness_b"]["harness_id"] = receipt["harness_a"]["harness_id"]
    receipt["harness_b"]["runner_identity"] = receipt["harness_a"]["runner_identity"]
    receipt["harness_b"]["implementation_sha256"] = receipt["harness_a"][
        "implementation_sha256"
    ]
    _rederive(receipt)

    validated = validate_lean_build_receipt(receipt)

    assert validated["verdict"] == "INCOMPARABLE"
    assert validated["verdict_reasons"][:2] == [
        "harness implementations are not independently identified",
        "harness or runner identities are not independent",
    ]


def test_missing_statement_or_dependency_evidence_is_incomparable() -> None:
    receipt = _receipt()
    receipt["target_build"]["reference_statement_sha256"] = None
    for key in ("harness_a", "harness_b"):
        receipt[key]["observed_statement_sha256"] = None
        receipt[key]["statement_matches_reference"] = None
    receipt["harness_b"]["dependency_cone"] = None
    _rederive(receipt)

    validated = validate_lean_build_receipt(receipt)

    assert validated["verdict"] == "INCOMPARABLE"
    assert validated["verdict_reasons"][:2] == [
        "statement-fidelity evidence is incomplete",
        "dependency-cone evidence is incomplete",
    ]


def test_execution_error_or_incomplete_kernel_check_is_incomparable() -> None:
    receipt = _receipt()
    receipt["harness_a"]["kernel_checked"] = False
    receipt["harness_a"]["exit_code"] = 2
    receipt["harness_a"]["errors"] = ["lake build exited non-zero"]
    _rederive(receipt)

    validated = validate_lean_build_receipt(receipt)

    assert validated["verdict"] == "INCOMPARABLE"
    assert "harness_a reported execution errors" in validated["verdict_reasons"]
    assert "harness_a did not complete the kernel check" in validated[
        "verdict_reasons"
    ]
    assert "harness_a exited non-zero" in validated["verdict_reasons"]


def test_fabricated_consistent_verdict_is_rejected() -> None:
    receipt = _receipt()
    receipt["harness_b"]["observed_axioms"] = ["Classical.choice"]
    receipt["comparison"] = derive_comparison(receipt)
    receipt["verdict"] = "CONSISTENT"
    receipt["verdict_reasons"] = [
        "all bounded observations agree across independently identified harnesses"
    ]

    with pytest.raises(ReceiptValidationError, match="not derived"):
        validate_lean_build_receipt(receipt)


def test_supplied_comparison_cannot_disagree_with_observations() -> None:
    receipt = _receipt()
    receipt["comparison"]["dependency_cone_agreement"] = False

    with pytest.raises(ReceiptValidationError, match="comparison fields"):
        validate_lean_build_receipt(receipt)


def test_statement_match_flag_must_equal_recorded_digest_comparison() -> None:
    receipt = _receipt()
    receipt["harness_a"]["statement_matches_reference"] = False

    with pytest.raises(ReceiptValidationError, match="disagrees with the recorded digests"):
        validate_lean_build_receipt(receipt)


def test_unknown_fields_malformed_digests_and_naive_time_fail_closed() -> None:
    unknown = _receipt()
    unknown["proof_valid"] = True
    with pytest.raises(ReceiptValidationError, match="unknown=.*proof_valid"):
        validate_lean_build_receipt(unknown)

    bad_digest = _receipt()
    bad_digest["harness_a"]["log_sha256"] = "not-a-digest"
    with pytest.raises(ReceiptValidationError, match="SHA-256"):
        validate_lean_build_receipt(bad_digest)

    naive_time = _receipt()
    naive_time["generated_at"] = "2026-09-06T12:00:01"
    with pytest.raises(ReceiptValidationError, match="timezone"):
        validate_lean_build_receipt(naive_time)


def test_validator_returns_a_defensive_copy() -> None:
    receipt = _receipt()
    validated = validate_lean_build_receipt(receipt)

    validated["harness_a"]["errors"].append("mutated after validation")

    assert receipt["harness_a"]["errors"] == []
    assert copy.deepcopy(receipt) != validated
