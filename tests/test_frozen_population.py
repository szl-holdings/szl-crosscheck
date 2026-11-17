"""Frozen eligible identities cannot be inferred from an agreeing observed subset.

Synthetic development cases, not model evaluations or independent operator runs.
The subset oracle is set equality over test-owned pairs, not production helpers.
"""
import copy
import hashlib
import itertools

import pytest

from szl_crosscheck.crosscheck import canonical, crosscheck, seal
from szl_crosscheck.adapters import fastapi_retrieval, stdlib_retrieval
from test_crosscheck import A, B, CONTEXT, make_chain
from test_adapters import sample

POLICY = {"bm25": ["ndcg10", "mrr"], "dense": ["ndcg10"]}


def checked(a=A, b=B, *, policy=POLICY, tolerance=0.01):
    return crosscheck(a, b, rel_tol=tolerance, required_metrics=policy)


def test_full_frozen_population_is_explicit_and_non_authorizing():
    report = checked()
    assert report['schema'] == 'szl.crosscheck.v3'
    assert report['verdict'] == 'CONSISTENT'
    assert report['population']['expected_count'] == 3
    assert report['population']['complete'] is True
    assert report['population']['comparison_complete'] is True
    assert report['execution_authorized'] is False
    assert report['population']['assurance'] == 'CALLER_DECLARED_POLICY_NOT_INDEPENDENT_ATTESTATION'


def test_default_mode_keeps_historical_schema_and_no_new_fields():
    report = crosscheck(A, B)
    assert report == crosscheck(A, B, required_metrics=None)
    assert report['schema'] == 'szl.crosscheck.v2'
    assert 'population' not in report
    assert 'execution_authorized' not in report


@pytest.mark.parametrize('side', ['a', 'b', 'both'])
def test_removed_disagreeing_lane_cannot_yield_frozen_consistency(side):
    left = make_chain('a', {'keep': {'value': 1}, 'drop': {'value': 1}})
    right = make_chain('b', {'keep': {'value': 1}, 'drop': {'value': 2}})
    policy = {'keep': ['value'], 'drop': ['value']}
    assert checked(left, right, policy=policy)['verdict'] == 'DIVERGENT'
    truncated = make_chain('partial', {'keep': {'value': 1}})
    if side in ('a', 'both'):
        left = truncated
    if side in ('b', 'both'):
        right = truncated
    # The old shared-only contract remains supported, but is not full coverage.
    assert crosscheck(left, right)['verdict'] == 'CONSISTENT'
    report = checked(left, right, policy=policy)
    assert report['verdict'] == 'INCOMPARABLE'
    assert report['population']['comparison_complete'] is False
    assert ['drop', 'value'] in report['population']['a' if side == 'a' else 'b']['missing']


@pytest.mark.parametrize('left,right', [
    ({'left': {'x': 1}}, {'right': {'x': 1}}),
    ({'left': {'wrong': 1}}, {'left': {'x': 1}}),
    ({'right': {'x': 1}}, {'right': {'x': 1}}),
    ({'left': {'x': 1, 'extra': 1}}, {'left': {'x': 1, 'extra': 1}}),
])
def test_equal_counts_or_agreeing_extras_never_substitute_for_expected_ids(left, right):
    report = checked(make_chain('a', left), make_chain('b', right), policy={'left': ['x']})
    assert report['verdict'] == 'INCOMPARABLE'
    assert report['population']['complete'] is False


def test_known_requested_disagreement_survives_missing_other_evidence():
    left = make_chain('a', {'one': {'x': 1}, 'two': {'x': 1}})
    right = make_chain('b', {'one': {'x': 2}})
    report = checked(left, right, policy={'one': ['x'], 'two': ['x']}, tolerance=0)
    assert report['verdict'] == 'DIVERGENT'
    assert report['population']['comparison_complete'] is False
    assert report['population']['b']['missing'] == [['two', 'x']]
    assert report['lanes'][0]['worst_metric'] == 'x'


def test_unrequested_difference_is_not_presented_as_requested_divergence():
    a = make_chain('a', {'one': {'x': 1, 'extra': 1}})
    b = make_chain('b', {'one': {'x': 1, 'extra': 2}})
    report = checked(a, b, policy={'one': ['x']}, tolerance=0)
    assert report['verdict'] == 'INCOMPARABLE'
    assert report['lanes'][0]['deltas'] == {'x': 0.0}
    assert report['population']['a']['unexpected'] == [['one', 'extra']]


@pytest.mark.parametrize('chains', [(A, B), (seal({'results': []}), seal({'results': []}))])
def test_explicit_empty_population_is_unavailable_not_vacuous_success(chains):
    report = checked(*chains, policy={})
    assert report['verdict'] == 'INCOMPARABLE'
    assert report['population']['expected_count'] == 0
    assert not report['population']['complete']
    assert not report['population']['comparison_complete']


@pytest.mark.parametrize('policy', [
    [], 'all', True, 1,
    {'': ['x']}, {' lane': ['x']}, {'lane ': ['x']}, {1: ['x']},
    {'lane': []}, {'lane': 'x'}, {'lane': ('x',)}, {'lane': [True]},
    {'lane': ['']}, {'lane': ['x', 'x']}, {'lane': [' x']},
    {'x' * 257: ['x']}, {'lane': ['x' * 257]},
    {str(n): ['x'] for n in range(257)},
    {'lane': [str(n) for n in range(4097)]},
])
def test_malformed_or_over_budget_policy_is_invalid(policy):
    report = checked(policy=policy)
    assert report['verdict'] == 'INVALID'
    assert 'dual_receipt' not in report


def test_population_order_is_not_identity_and_input_is_not_mutated():
    original = copy.deepcopy(POLICY)
    reordered = {'dense': ['ndcg10'], 'bm25': ['mrr', 'ndcg10']}
    assert checked(policy=original) == checked(policy=reordered)
    assert original == POLICY


def test_policy_and_coverage_are_committed_into_dual_receipt():
    report = checked()
    unhashed = {k: v for k, v in report.items() if k != 'dual_receipt'}
    assert hashlib.sha256(canonical(unhashed).encode()).hexdigest() == report['dual_receipt']
    mutated = copy.deepcopy(unhashed)
    mutated['population']['b']['matched_count'] = 0
    assert hashlib.sha256(canonical(mutated).encode()).hexdigest() != report['dual_receipt']
    policy = {k: report['population'][k] for k in ('schema', 'required_metrics')}
    assert hashlib.sha256(canonical(policy).encode()).hexdigest() == report['population']['policy_sha256']


def test_non_measured_lane_cannot_fill_a_required_population():
    payload = {'context': copy.deepcopy(CONTEXT), 'results': [
        {'lane': 'one', 'state': 'SAMPLE', 'metrics': {'x': 1}},
        {'lane': 'two', 'state': 'MEASURED', 'metrics': {'x': 1}},
    ]}
    chain = seal(payload)
    report = checked(chain, chain, policy={'one': ['x'], 'two': ['x']})
    assert report['verdict'] == 'INCOMPARABLE'
    assert report['population']['a']['missing'] == [['one', 'x']]


def test_context_mismatch_is_not_complete_comparison_even_with_matching_ids():
    b = make_chain('b', {'bm25': {'ndcg10': .42, 'mrr': .38}, 'dense': {'ndcg10': .51}})
    payload = {k: copy.deepcopy(v) for k, v in b[0].items() if k not in ('chain_hash', 'prev_hash')}
    payload['context']['machine']['identity'] = 'different-fixture'
    report = checked(b=seal(payload))
    assert report['verdict'] == 'INCOMPARABLE'
    assert report['population']['complete'] is True
    assert report['population']['comparison_complete'] is False
    assert report['lanes'] == []


def test_tampering_still_invalid_before_population_assessment():
    b = copy.deepcopy(B)
    b[0]['results'][0]['metrics']['mrr'] = 999
    assert checked(b=b)['verdict'] == 'INVALID'


def test_existing_native_adapters_feed_the_same_population_contract():
    inputs, context, chain, native = sample()
    a = stdlib_retrieval(chain, context)
    b = fastapi_retrieval(native, context, inputs)
    report = checked(a, b, policy={'bm25': ['ndcg@10', 'recall@10']})
    assert report['population']['complete'] is True
    assert report['population']['comparison_complete'] is True
    assert report['population']['expected_count'] == 2
    assert report['execution_authorized'] is False


def test_exhaustive_subset_pairs_match_independent_set_oracle():
    identities = (('a', 'x'), ('a', 'y'), ('b', 'x'), ('b', 'y'))
    required = {'a': ['x', 'y'], 'b': ['x', 'y']}

    def selected(mask):
        return {pair for index, pair in enumerate(identities) if mask & (1 << index)}

    def chain_for(pairs):
        rows = {}
        for lane, metric in sorted(pairs):
            rows.setdefault(lane, {})[metric] = 1
        return make_chain('synthetic-subset', rows)

    full = set(identities)
    for left, right in itertools.product(range(16), repeat=2):
        a, b = selected(left), selected(right)
        report = checked(chain_for(a), chain_for(b), policy=required)
        expected_complete = a == b == full
        assert (report['verdict'] == 'CONSISTENT') is expected_complete, (left, right)
        assert report['population']['comparison_complete'] is expected_complete
        assert report['population']['a']['matched_count'] == len(a)
        assert report['population']['b']['matched_count'] == len(b)
        assert set(map(tuple, report['population']['a']['missing'])) == full - a
        assert set(map(tuple, report['population']['b']['missing'])) == full - b
