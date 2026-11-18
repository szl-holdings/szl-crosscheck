"""Synthetic finite-domain tests. No real-language or uniqueness claim."""
import pytest
from szl_crosscheck.semantic_fidelity import compare_position_clue, SemanticInputError

C = {"german": "nationality", "rabbit": "pet", "cat": "pet", "swede": "nationality"}


def compare(source, a, b, categories=C, houses=5):
    return compare_position_clue(houses=houses, categories=categories,
                                 source=source, encoder_a=a, encoder_b=b)


def test_exact_same_meaning_accepted():
    r = compare("Abs(pos('german') - pos('rabbit')) == 2",
                "Abs(pos('german')-pos('rabbit'))==2",
                "Abs(pos('rabbit')-pos('german'))==2")
    assert r["status"] == "MATCH" and r["checked_assignments"] > 0
    assert not r["uniqueness_certified"] and not r["execution_authorized"]


def test_shared_paraphrase_drift_detected_even_when_encoders_agree():
    # The paper's critical case: distance 2 became distance 3.
    source = "Abs(pos('german')-pos('rabbit'))==2"
    wrong = "Abs(pos('german')-pos('rabbit'))==3"
    r = compare(source, wrong, wrong)
    assert r["dual_equivalent"] and not r["source_equivalent"] and r["status"] == "DRIFT"
    assert r["witnesses"]["a_vs_source"]["assignment"]


def test_independent_disagreement_detected():
    r = compare("pos('german')+1 == pos('rabbit')",
                "pos('german')<pos('rabbit')", "pos('german')+1==pos('rabbit')")
    assert not r["dual_equivalent"] and r["status"] == "DRIFT"


def test_missing_source_is_not_verified():
    r = compare(None, "pos('german') == 1", "pos('german') == 1")
    assert r["status"] == "INDETERMINATE" and r["source_equivalent"] is None


def test_same_category_excludes_same_house():
    r = compare("pos('rabbit') != pos('cat')",
                "pos('rabbit') != pos('cat')", "pos('rabbit') != pos('cat')")
    assert r["status"] == "MATCH" and r["checked_assignments"] == 20


def test_direction_flip_detected():
    r = compare("pos('german')<pos('rabbit')",
                "pos('rabbit')<pos('german')", "pos('german')<pos('rabbit')")
    assert r["status"] == "DRIFT"


@pytest.mark.parametrize("payload", [
    "__import__('os').system('id')",
    "pos('german').__class__",
    "[x for x in range(10)]",
    "pos('unknown')==1",
    "pos('german')==1 or True",
    "pos('german') == 1 == 1",
])
def test_unsupported_or_unsafe_input_rejected(payload):
    with pytest.raises(SemanticInputError):
        compare("pos('german')==1", payload, "pos('german')==1")


def test_out_of_range_houses_rejected():
    with pytest.raises(SemanticInputError):
        compare_position_clue(houses=10, categories=C, source=None,
                              encoder_a="pos('german')==1", encoder_b="pos('german')==1")


def test_unsatisfiable_base_is_not_vacuous_match():
    with pytest.raises(SemanticInputError):
        compare_position_clue(houses=2, categories={"a":"same", "b":"same", "c":"same"},
                              source="pos('a') != pos('b')",
                              encoder_a="pos('a') != pos('b')",
                              encoder_b="pos('c') != pos('b')")
