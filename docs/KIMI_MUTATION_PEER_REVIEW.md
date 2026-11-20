# Kimi × SZL: peer-coded mutation controls (source-only)

**Status:** Experimental, offline and non-authorizing. This is a preflight reviewer
for the existing szl_crosscheck.harness_evolution workflow, not a second evaluator,
autonomous agent, testing engine or deployment controller.

## What is different?

The paired evaluator compares baseline/candidate outcomes on held-out and regression
cases using an exact sign test and cost limits. It cannot tell whether the tests
would catch a plausible incorrect patch. The separate review_mutation_controls()
helper examines a declared frozen population of 5–32 distinct mutated variants
and their claimed test outcomes.

Research basis, without importing third-party code:

- [SWE-ABS, ICML 2026](https://proceedings.mlr.press/v306/yu26b.html):
  mutation-based adversarial tests expose false positives in coding agents.
- [SWE-agent, NeurIPS 2024](https://papers.nips.cc/paper_files/paper/2024/hash/5a7c947568c1b1328ccc5230172e1e7c-Abstract-Conference.html):
  purpose-built bounded agent-computer interfaces.
- [OpenHands Agent SDK, MLSys 2026](https://proceedings.mlsys.org/paper_files/paper/2026/hash/8ae9cf363ea625161f885b798c1f1f78-Abstract-Conference.html):
  lifecycle, sandboxing and source/runtime separation.

**Peer review:** Kimi K3.1 Pro was consulted through existing Ollama as an
advisory reviewer, using sanitized public research and contract summaries.
Its adversarial second review found a real false positive: a mutant can appear
killed because tests never collected or imported, not because an assertion
detected incorrect behavior. The source therefore requires the selected-test
population and execution environment hashes to match the declared plan,
positive exact executed-test counts, zero skips and an assertion failure phase
for killed mutants. Surviving mutants have phase none. These are still caller
assertions.

## Frozen inputs and refusals

review_mutation_controls(evidence) accepts only a strict in-memory object with
schema, plan, ownership, and controls. The preregistered plan declares 40-hex
source, test and evaluator revisions; full 64-hex test and runtime/dependency
identity digests; fixed selected-test population and count; and a canonical
SHA-256 of sorted unique mutation digests. Controls bind mutant and run receipt
hashes to the planned source/test/environment and explicit execution outcomes.

Typed HOLDs reject incomplete or duplicate mutations/receipts, changed source,
test population or runtime identity, unexecuted or skipped tests, collection/
import/setup failure masquerading as an assertion, failing baselines, or surviving
mutants. No private identifiers or prompts are echoed to results.

A structurally plausible record yields only SOURCE_CANDIDATE_FOR_OWNER_REVIEW.
It cannot prove preregistration, cryptographic provenance, evaluator independence,
semantic mutation quality, test execution, correctness or production safety.
All promotion, merge, runtime-change and signature/independence-verified flags
are false, always.

## Reproduce

Run: python -m pytest tests/test_mutation_controls.py -q
Then run the repository's normal full CI matrix.

The 24 synthetic tests cover invalid schemas, duplicate mutants/receipts,
changed test/runtime populations, skipped and collection-failure masquerades,
surviving mutants and permanent non-authorization.

No credentials, model execution privileges, new agent processes, task/service
installations, GPU training, checkpoints, Hugging Face/Cloudflare/PyPI releases,
branch-protection overrides, or Flagship54 edits are involved. Any real patch
requires independently authenticated sandbox execution and owner review.
