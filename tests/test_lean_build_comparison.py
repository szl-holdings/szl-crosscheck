# SPDX-License-Identifier: Apache-2.0
"""Adversarial contract for the Lean-build comparison receipt schema.

Refs szl-crosscheck#4. Proves the schema enforces the doctrine: the only verdict
vocabulary is CONSISTENT / DIVERGENT / INCOMPARABLE, no claim of break or
confirmation exists without a receipt, and the FLT program's own questions
(rebuild, dependency cone, statement fidelity, axiom surface) are all carried.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "lean-build-comparison-v1.json").read_text())


def test_verdict_vocabulary_is_exactly_three_states() -> None:
    assert set(SCHEMA["properties"]["verdict"]["enum"]) == {
        "CONSISTENT", "DIVERGENT", "INCOMPARABLE",
    }
    assert "BREAK" not in SCHEMA["properties"]["verdict"]["enum"]
    assert "PROOF_VALID" not in SCHEMA["properties"]["verdict"]["enum"]


def test_schema_identity_and_required() -> None:
    assert SCHEMA["$id"].endswith("lean-build-comparison-v1.json")
    assert set(SCHEMA["required"]) == {
        "schema", "target_build", "harness_a", "harness_b", "verdict",
    }


def test_two_independent_harnesses_required() -> None:
    assert SCHEMA["properties"]["harness_a"]["$ref"] == "#/$defs/harness"
    assert SCHEMA["properties"]["harness_b"]["$ref"] == "#/$defs/harness"


def test_harness_carries_the_programs_four_questions() -> None:
    h = SCHEMA["$defs"]["harness"]["properties"]
    assert "rebuilt" in h and "kernel_checked" in h
    assert "sorries_in_final_chain" in h and "dependency_cone" in h
    tb = SCHEMA["properties"]["target_build"]["properties"]
    assert "declared_axioms" in tb and "statement_matches_reference" in tb


def test_no_untracked_fields() -> None:
    assert SCHEMA["additionalProperties"] is False
    assert SCHEMA["$defs"]["harness"]["additionalProperties"] is False
