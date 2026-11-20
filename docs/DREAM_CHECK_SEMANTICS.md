# Dream accountability: explicit next-cycle predicates, not guessed PASS

**Status:** source-only, standalone cross-check. This code neither edits nor
restarts the existing BETTERWITHAGE dream station/auditor or any Hugging Face
dataset, GPU job, provider or scheduled task. It is **not** a live evaluator,
trusted telemetry collector or authorization gate.

## Why

The user-supplied Vibe/Claude transcript contains a public
`szl.dream-audit/v1` snapshot dated 2026-11-19 08:33:33Z with
eight adjacent-pair records. One recorded measurable check was:

> Set a target utilization threshold (e.g., 80%) and adjust the number
> of serving models or resource allocation to ensure optimal utilization.

The next GPU observation was `0%`, yet the regex-based auditor returned
`PASS` because it interpreted the word `target` as **utilization <=80**.
The prose did not explicitly say whether 80% was a *minimum*, *maximum* or
*exact* target. A threshold without direction cannot be truthfully scored
PASS. If the intended policy was a minimum 80% GPU utilization, 0% is
a **failure**; if a maximum 80% is intended, the user must declare that
separately. In either case, drawing the comparator from keyword heuristics
is a source-level false-confidence risk. A successful HTTP 200 publishing
an audit band cannot prove its semantic correctness.

In a separate owner log, the auditor was still producing bands overnight:
106 graded pairs by Nov 20 03:32Z. This is liveness evidence, **not** proof
those verdicts were independently checked. We do not alter or delete
its previous receipt history.

## Replacement contract (proposal to the existing owner)

`szl_crosscheck.dream_predicate.review_next_cycle(plan, observation, now_utc)`
checks **only** an explicitly preregistered typed predicate:

- One immutable 64-hex dream-source digest and a declared different
  evaluator digest; digest syntax and difference are **not identity or
  signature verification**.
- One of `gpu_utilization_pct`, `gpu_temperature_c`,
  `gpu_power_w` with its exact unit, finite numeric threshold and an
  explicit comparator `ge/gt/le/lt/eq`. No natural-language fallback.
- The next observation must declare the same dream source, a distinct
  cycle digest, its own evidence digest and a timestamp after the
  check's issue time but before expiry. Source windows longer than
  one hour and observations older than ten minutes are not admitted.
- The observation's metric, unit and bounded numeric value must agree
  with the frozen plan. Missing, nonfinite, out-of-range, bool-valued,
  unbound or stale inputs all produce `HOLD`.
- `gpu_utilization_pct ge 80` paired with 0 is
  `DECLARED_PREDICATE_NOT_MET_UNATTESTED`. A bare text target
  or `operator=target` is `HOLD`. A clearly declared `le 80`
  with 0 can be reported as structurally met, **not** real telemetry
  authentication or evidence of resource efficiency.

Its sole favorable classification is
`DECLARED_PREDICATE_MET_UNATTESTED`. Every result always contains
`independent_measurement_verified=false`,
`evaluator_identity_authenticated=false`,
`pre_registration_proven=false`,
`training_improvement_proven=false`,
`source_or_runtime_change_authorized=false` and
`production_qualified=false`.

The caller can invent all digests, timestamps and readings. This module
is therefore a **format, arithmetic and temporal guard**; authenticated
independent data reads and owner countersign remain separate.

## Applicable world research without unlicensed code reuse

- [Google authors' self-improving harness framework](https://arxiv.org/abs/2611.22299):
  bounded diagnose→patch→verify rather than uncontrolled self-grading.
- [VERSE](https://arxiv.org/abs/2610.02616):
  execution replay and perturbation tests rather than generated labels.
- [Apache Arrow issue 53954](https://github.com/apache/arrow/issues/53954):
  the dream learner's separate PyArrow/NumPy import failure is already
  addressed by reviewable [GPU Bridge PR #302](https://github.com/szl-holdings/szl-gpu-bridge/pull/302).
  Dependency compatibility, actual training, and measurement semantics
  are **three separate** gates.

No upstream code was copied, and no claim of novelty, model
accuracy, GPU resource improvement or mathematical theorem follows.

## Controlled adoption path

The existing owner of the dream auditor (not this PR) should:

1. Preserve the old audit band and label its legacy natural-language
   verdicts `UNVERIFIED_LEGACY`, not silently relabel or delete them.
2. Pre-register explicit metric/operator/threshold/window in a versioned
   receipt **before** prompting a model for next-cycle actions.
3. Have a separate authorized telemetry reader capture next-cycle
   device/metric/process identity and timestamps, verify source binding,
   and produce an immutable signed receipt.
4. Use this comparator or equivalent reviewed source logic, with
   independent regression tests for the 0%-versus-80% case, reversed
   comparisons, missing operator, stale/missing cycles and falsified
   attribution. Only the owner may integrate the approved code into
   the existing scheduled auditor; **no second watcher**.
5. Promote improvements only after independent task/evaluator evidence,
   correct denominators and signed runtime readback. A structurally
   favorable typed comparison alone is insufficient.

### Source-owned CI tests

Run through the existing `szl-crosscheck` Python 3.11/3.12 GitHub
workflow, **not** as a local laptop suite:

```sh
python -m pytest tests/test_dream_predicate.py -v
```

The tests use synthetic values only; they do not call Hugging Face,
Ollama, Salad, Cloudflare or any agent.
