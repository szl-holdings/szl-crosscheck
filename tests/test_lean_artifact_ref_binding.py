# SPDX-License-Identifier: Apache-2.0
"""Fail-closed target-artifact identity tests for Lean comparison receipts."""

import pytest

from szl_crosscheck.lean_build import (
    CLAIM_BOUNDARY,
    ReceiptValidationError,
    derive_comparison,
    derive_verdict,
    validate_lean_build_receipt,
)


def _receipt() -> dict:
    target_digest = "a" * 64
    value = {
        "schema": "szl.lean-build-comparison/v1",
        "generated_at": "2026-09-23T15:00:00Z",
        "target_build": {
            "artifact_ref": "ghcr.io/example/flt-lean@sha256:" + target_digest,
            "artifact_sha256": target_digest,
            "lean_version": "4.19.0",
            "entrypoint": "FermatLastTheorem.lean",
            "theorem_name": "FermatLastTheorem.fermat_last_theorem",
            "reference_statement_sha256": "b" * 64,
            "declared_axioms": ["Classical.choice", "propext"],
        },
        "harness_a": {
            "harness_id": "native-lake-build",
            "runner_identity": "runner-a",
            "implementation_sha256": "c" * 64,
            "source_revision": "1" * 40,
            "completed_at": "2026-09-23T14:58:00Z",
            "rebuilt": True,
            "kernel_checked": True,
            "exit_code": 0,
            "artifact_sha256": target_digest,
            "observed_statement_sha256": "b" * 64,
            "statement_matches_reference": True,
            "observed_axioms": ["Classical.choice", "propext"],
            "sorries_in_final_chain": 0,
            "dependency_cone": {
                "declared_theorems": 10,
                "load_bearing_theorems": 4,
                "sha256": "d" * 64,
            },
            "log_sha256": "e" * 64,
            "errors": [],
        },
        "harness_b": {
            "harness_id": "containerized-lean-check",
            "runner_identity": "runner-b",
            "implementation_sha256": "f" * 64,
            "source_revision": "2" * 40,
            "completed_at": "2026-09-23T14:59:00Z",
            "rebuilt": True,
            "kernel_checked": True,
            "exit_code": 0,
            "artifact_sha256": target_digest,
            "observed_statement_sha256": "b" * 64,
            "statement_matches_reference": True,
            "observed_axioms": ["Classical.choice", "propext"],
            "sorries_in_final_chain": 0,
            "dependency_cone": {
                "declared_theorems": 10,
                "load_bearing_theorems": 4,
                "sha256": "d" * 64,
            },
            "log_sha256": "0" * 64,
            "errors": [],
        },
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


def test_digest_qualified_artifact_ref_must_match_declared_digest() -> None:
    receipt = _receipt()
    receipt["target_build"]["artifact_ref"] = (
        "ghcr.io/example/flt-lean@sha256:" + "9" * 64
    )

    with pytest.raises(ReceiptValidationError, match="artifact_ref digest disagrees"):
        validate_lean_build_receipt(receipt)


def test_malformed_digest_qualifier_fails_closed() -> None:
    receipt = _receipt()
    receipt["target_build"]["artifact_ref"] = "ghcr.io/example/flt-lean@sha256:not-a-digest"

    with pytest.raises(ReceiptValidationError, match="malformed sha256 digest qualifier"):
        validate_lean_build_receipt(receipt)


def test_non_digest_reference_keeps_separate_digest_binding() -> None:
    receipt = _receipt()
    receipt["target_build"]["artifact_ref"] = "artifact://flt-lean/release-candidate"

    validated = validate_lean_build_receipt(receipt)

    assert validated["verdict"] == "CONSISTENT"
    assert validated["target_build"]["artifact_sha256"] == "a" * 64
