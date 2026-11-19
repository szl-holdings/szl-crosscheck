# Kimi and SZL: source-only harness-evolution evidence gate

**Scope:** This is an opt-in experimental source module for **independently owned** paired evaluation records. It is not an agent, scheduler, tool grant, model, inference server, deployment controller, benchmark runner, sanitizer or cryptographic attestation. It does not modify `crosscheck()`, existing verified receipt formats, existing workflows or currently admitted models.

## Independent prior art, exact observed sources

- Google authors Deep Shah and Nehal Kathrotia, [Harnesses That Improve Themselves](https://arxiv.org/abs/2611.22299), 17 Nov 2026: four harness elements (context/state, control, action interfaces, verification/recovery), with modular failure diagnosis and independent validation. This intake does **not** reproduce the paper's SWE-bench Lite results.
- Zekai Wang et al., [VERSE](https://arxiv.org/abs/2610.02616) and [author software](https://github.com/wzekai/VERSE/tree/d8ff0adab0cf82e13d7878f84ff84f823cb2f6c9): execute/replay/perturb candidate harness patches and test held-out cross-language generalization. No author code is imported.
- Hangfan Zhang et al., [Self-Harness](https://arxiv.org/abs/2606.09498): mine model-specific failures, propose minimal harness changes, validate on held-out Terminal-Bench tasks. Its reported gains are not SZL observations.
- NVIDIA, [Megatron Bridge checkpointing](https://docs.nvidia.com/nemo/megatron-bridge/latest/training/checkpointing.html): full training resume requires optimizer/RNG/dataloader state, unlike model-weight initialization; this **module does not verify training/checkpoint recovery**.
- [vLLM security](https://docs.vllm.ai/en/latest/usage/security/): `cache_salt` is *not* tenant isolation; request-scoped invariant keys and a shared process alone cannot prove SZL Second Brain multi-tenancy. This is a separate deployment test.

These are **engineering comparisons**, not allegations that authors' experiments are directly replicable on SZL's GPU fleet. The only code added in this PR is original, Python-standard-library arithmetic and synthetic tests.

## A single bounded Kimi experiment (the proposed collaboration)

The existing Kimi owner, **without adding a second local process**, proposes a **small, isolated Git branch** fixing one publicly evidenced harness failure. It must not edit its own evaluator, sealed tasks, tool-permission policy or owner review settings.

The independent evaluator owner freezes a plan and task population **before** any candidate output, with exact SHA256 task handles, approved model revision, baseline/candidate source commits, evaluator revision, declared candidate-family count (including unsuccessful or discarded candidates), task/token/tool ceilings, and at least **30 heldout plus 5 prior-capability regression cases**. Keep raw tasks and any private content with the authorized evaluator, not in GitHub. The evaluator independently replays both configurations on each exact case, producing caller-supplied `baseline_pass`, `candidate_pass`, tokens and tools.

To inspect **only the arithmetic**:

```python
from szl_crosscheck.harness_evolution import review_harness_pair

verdict = review_harness_pair({
    "schema": "szl.harness-evolution-pair/v1",
    "plan": plan,          # exact validated fields, already frozen externally
    "ownership": ownership,  # opaque proposer/evaluator digests (not identities)
    "pairs": paired_rows, # no prompts, only test digests and outcomes
})
assert verdict["promotion_authorized"] is False
```

A `SOURCE_CANDIDATE_FOR_OWNER_REVIEW` decision is **never approval**, even if the supplied records look mathematically convincing. It means only that:

1. the caller claims pre-registration and different proposer/evaluator IDs;
2. baseline and candidate are declared to use the same model, suite and evaluator but different harness revisions;
3. all required task IDs are unique and the minimum heldout/regression coverage is present;
4. no previously passing regression case becomes a failure;
5. all per-case token/tool ceilings and the declared aggregate token ratio are met;
6. heldout net wins meet the preregistered minimum; and
7. an **exact, one-sided paired discordance sign test** meets a Bonferroni-style candidate-family cap.

The arithmetic uses: `w = count(B_i=0,C_i=1)`, `l=count(B_i=1,C_i=0)`, `p = sum(comb(w+l,k), k=w..w+l) / 2**(w+l)`. The threshold checks `p * candidate_family_size <= familywise_alpha` using **integer arithmetic only**. This relies on an exchangeable-discordant-pairs null; correlated task outcomes, repeated use of a heldout set, peeking, selective candidate reporting or a misreported family size can invalidate its inferential meaning. Correction is a guardrail, not a substitute for independent experimental design. Missing required cases, extra fields, unsigned identities, malformed counts, wrong revisions or changed budget produce `HOLD` where represented by the typed input. The code cannot authenticate a supplied SHA, independently establish candidate originality or know that the plan was truly frozen.

All outputs explicitly set `trusted_evaluator_proven=false`, `plan_preregistration_proven=false`, `model_quality_proven=false`, `promotion_authorized=false`, `runtime_change_authorized=false`. Inputs may be fabricated; the module **does not certify their provenance or correctness**.

## Exact SZL evidence and ownership path

| Stage | Existing owner / authority | Exit evidence |
| --- | --- | --- |
| Claim/failure candidate | Kimi CTO agent, isolated worktree and one writer | Immutable public issue, original trace and bounded proposed patch |
| Candidate source | GitHub protected repository and independent reviewer | Clean exact-head diff, normal CI/CodeQL, reviewer approval |
| Execution | Existing authorized benchmark/sandbox owner | Model/environment source revision, independent heldout task digest and per-case outcomes |
| Arithmetic | `szl-crosscheck` source gate (this module) | `HOLD` or **source-only** owner-review candidate |
| Independent admission | `szl-receipt`, `szl-quant-witness`, Hatun policy | Signed/verified source+task+evaluation chain, no self-grading or missing denominator |
| Runtime | Existing A11oy/Hatun/Second Brain deployment owner | Exact deployed image/commit readback, authentication, rollback, negative controls |
| Cleanup | Owner-controlled workstation task list | Exact ticked paths only; dry-run preview, symlink and ownership verification, owner-authorized delete/readback |

A GitHub PR, signed image, SUCCESS check, chat response, model alias or hosted Space is **not** an executed heldout evaluation. This is an additional validation contract for candidate harness changes; it is **not** an instruction to launch a local Kimi model, change account permissions or bypass a `DIFFERENTIAL_NO_GO` gate.

## Running tests

These are small synthetic **CI** tests. Run through the source-owned GitHub workflow / an approved cloud environment, not BETTERWITHAGE while its memory guard restricts local test suites:

```sh
python -m pytest tests/test_harness_evolution.py -q
```

A successful offline test verifies deterministic semantics only; it must not be turned into a model-performance score or a public promotion claim.
