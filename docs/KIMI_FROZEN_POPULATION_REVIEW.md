# Opt-in exact frozen-population gate for agentic peer-coding evaluations

**Source-only:** `review_frozen_harness_pair(evidence, expected_policy)` composes the existing `review_harness_pair` with an exact split-specific comparison against an independently declared candidate-case population. It does not alter `review_harness_pair`, v1 receipts, historic measurements, model weights, or production controllers.

The expectation has exactly three fields: `schema: "szl.harness-frozen-population/v1"`, `heldout_case_digests` and `regression_case_digests` (lists of unique lowercase 64-character SHA-256 hexadecimal identifiers). Bounds: at least 30 heldout and 5 regression cases, at most 512 combined. Identifiers cannot overlap across splits. Exact set equality—not aggregate counts—detects omissions, replacements and split swaps even when the original paired arithmetic gate would have returned `SOURCE_CANDIDATE_FOR_OWNER_REVIEW`.

A positive result includes a canonical SHA-256 of the *caller-provided expected population* and split-specific aggregate coverage counts without revealing case digests. The expectation hash is **not a signature, secure timestamp, independently verified dataset revision or proof of preregistration**. A positive source-only verdict requires both the original arithmetic gate and complete split-specific identity coverage, but all promotion/runtime authorization flags stay false.

## Independent admission still required

Freeze the expected case list with an independent evaluator **before** the candidate outputs or adaptation. Do not infer the expected list from the cases supplied in `evidence`; that would trivially defeat the guard. Independently verify receipt/plan signatures, evaluator custody, task rights, full run population, immutable source and environment, denominator and quality benchmarks before making promotion or training claims.

Kimi provided an initial globally unique two-split validator and suggested a same-size split-swap negative control. The independent reviewer added canonical policy hashing, aggregate-only mismatch diagnostics, compositional admission, malformed-data checks and conservative authorization flags. Synthetic source CI tests exercise exact coverage, omissions, equal-count split swaps, substitutes, duplicate IDs, invalid policy fields, stable digests, budget holds and immutable inputs.

No shell tool, worker process, autonomous scheduler, trainer, paid service or provider-write permission is introduced.

## Usage

```python
from szl_crosscheck.frozen_population import (
    FROZEN_POPULATION_SCHEMA, review_frozen_harness_pair,
)

policy = {
    "schema": FROZEN_POPULATION_SCHEMA,
    "heldout_case_digests": frozen_heldout_case_sha256,
    "regression_case_digests": frozen_regression_case_sha256,
}
verdict = review_frozen_harness_pair(existing_paired_evidence, policy)
assert verdict["promotion_authorized"] is False
assert verdict["runtime_change_authorized"] is False
```

The example names stand for separately held, predeclared data. This module never obtains or validates those sources itself.
