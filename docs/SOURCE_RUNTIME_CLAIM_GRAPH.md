# Source-to-runtime claim graph — global frontier research and SZL review contract

**SOURCE-ONLY / NOT AN AUDITOR / NOT A SIGNATURE VERIFIER / NOT A PRODUCTION GATE.**
This is the first bounded implementation of a nine-stage **claim consistency**
checker in existing `szl-crosscheck`. It imports no third-party project code,
contacts no provider, reads no credentials, changes no service, and issues no
approval. A caller can fabricate *every* field. A `SOURCE_CLAIM_GRAPH_FOR_OWNER_REVIEW`
result is **not** release admission; all trust/authorization fields remain false.

## The specific production failure being addressed

A green GitHub CI job, signed OCI image, HF model card, successful health HTTP
response or paid API challenge is **not** equivalent to a source-bound working
product. In SZL's historical GPU-bridge evidence, a source image and a live
training worker diverged; a protected source merge did not establish an updated
serving image, exact checkpoint, independent backup or heldout quality. This
contract rejects **structurally mismatched declared evidence** across those
separate steps, instead of allowing a publisher to silently skip one.

This does not assert current provider recovery, completion or new source drift.
The actual owner must still read live GitHub/GHCR/Salad/Hugging Face/Cloudflare
and independently verify exact signer, file hashes, runtime process, rights and
negative-control outputs.

## Upstream leaders examined, provenance and what is reusable

| Region / upstream primary authority | Exact lesson transferable to SZL | What remains original, licensed and unproved |
| --- | --- | --- |
| **Global SLSA v1.2** — [provenance specification](https://slsa.dev/spec/v1.2/build-provenance), [verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts) | Bind an exact source, approved builder, build parameters, resolved dependencies and artifact subject; *verify* attestation rather than merely storing it. | The present module implements **none** of SLSA signature verification. Its `signature_checked` is an untrusted caller assertion. |
| **Sigstore / Cosign** — [verification guide](https://docs.sigstore.dev/cosign/verifying/verify/) | Verify signed OCI image digest, certificate identity, OIDC issuer, bundle and builder expectations independently. | A SHA-256 string alone is never a certificate, and a verifier digest is not an authentication step. |
| **Argo CD / GitOps** — [core concepts](https://argo-cd.readthedocs.io/en/stable/core_concepts/) | Distinguish desired Git state, observed live state, synchronization and health. All are independent. | No Argo CD is installed or required by this PR; neither health nor exact source matching is inferred from a `RUNNING` label. |
| **United States — VERSE** — [arXiv](https://arxiv.org/abs/2610.02616) and [source](https://github.com/wzekai/VERSE) | Candidate edits require execution replay, perturbation, withheld cases and regression evidence; avoid self-certifying agent improvements. | No VERSE code is imported and no Kimi/Mistral benchmark is reproduced. Existing paired `harness_evolution.py` is a distinct first-stage check. |
| **China — verl / HybridFlow** — [open project](https://github.com/verl-project/verl), [DeepSeek R1](https://www.nature.com/articles/s41586-025-09422-z) | Separate reward verification, RL trajectory identity, training artifacts and independent heldout admission. | No GRPO training or model improvement is authorized or claimed. |
| **South Korea — KAIST KORMo** — [source and reproducibility artifacts](https://kaist-mlplab.github.io/kormo/) | Publish code, dataset rights, filtering, recipes, checkpoints and logs separately; retain complete denominator and negative outcomes. | SZL is not ingesting the KORMo corpus or claiming Korean-English performance. |
| **Ireland — Lero AIware** — [research program](https://aiware-lero.github.io/) | Independent adversarial validation, fault localization, runtime monitoring and industrial-context reproducibility. | This Python source graph is not live telemetry or an independent evaluator. |
| **vLLM serving/security** — [tenant boundary](https://docs.vllm.ai/en/stable/usage/security/) | A shared-process cache salt is **not** tenant isolation; test tenant authentication, negative cross-tenant queries, and process isolation when required. | The `tenant_boundary_negative_test` flag is merely an untrusted declared outcome until an independent gateway/serving audit verifies it. |

### Public code and license snapshots inspected for this intake

The following GitHub main revisions were returned by the connected source
reader around 2026-11-20 02:30 UTC. A LICENSE-file header was inspected where
noted; this is **not** a dependency license audit, and a moving `main` can
change after observation.

| Project | Observed GitHub commit | Root license file | Suggested SZL role |
| --- | --- | --- | --- |
| [VERSE](https://github.com/wzekai/VERSE) | `d8ff0adab0cf82e13d7878f84ff84f823cb2f6c9` | MIT | Reproducibility protocol for failure replay and agent patch regression |
| [verl](https://github.com/verl-project/verl) | `3a909894862c9d298073618e742e2f3ce51e86fc` | Apache-2.0 | Separately admitted GRPO/rollout experimentation, **not** this gate |
| [vLLM](https://github.com/vllm-project/vllm) | `898a7c68c2d1e869ebde2ce25ffbfc1e253bf0b4` | Apache-2.0 | Actual inference identities and tenant-isolation negative tests |
| [SGLang](https://github.com/sgl-project/sglang) | `f913bf9aa1b6f9d428b3d521b72c42ed1d00292e` | Apache-2.0 | Alternative serving baseline under same hardware and traffic |
| [Cosign](https://github.com/sigstore/cosign) | `339a3ca85413b4d89a49daf1eb554591c93ee365` | Apache-2.0 | External signed OCI digest verification, not a Python bool |
| [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector) | `0c7a74cd0a4ab1c70834c91b67942eaaa9065825` | Apache-2.0 | Separate event/trace identities, not a proof of physical execution |
| [Megatron Bridge](https://github.com/NVIDIA-NeMo/Megatron-Bridge) | `e0c16412af81f26f67a79ea450c9bc70c64a8c08` | Apache-2.0 | Full optimizer/RNG/dataloader checkpoint completeness criteria |

Use exact revisions only after verifying author identity, LICENSE and NOTICE
at that same commit, transitive dependencies, model/data usage rights and a
source-owned test. **No bytes from these upstream repositories are vendored or
executed in this PR.** KORMo/AIware references above are research practices,
not dependency import candidates.

**Reuse policy:** Open-source means investigate and reuse under the specific
license and dependency/security terms, **not** take another project's name,
authorship or code. Verify exact upstream Git commit, copyright/license,
dataset permissions and redistribution boundaries before vendoring anything.
This PR contains newly written standard-library source and synthetic tests.

## Two distinct bounded populations

`review_release_graph(plan=..., nodes=..., now_utc="YYYY-MM-DDTHH:MM:SSZ")`
accepts a fixed declared profile, not an arbitrary positive list.

| Profile | Required source-bound claim stages | What remains outside this implementation |
| --- | --- | --- |
| `edge_service` | source → CI → signed image → provider instance list → authenticated serving → public-card/rights readback | Workers WAF/DNS, x402 settlement, PyPI wheel provenance, Neon migration/RLS and financial billing |
| `served_model` | same source/CI/image/provider, plus complete resumable checkpoint → independent byte-matched backup → independent heldout evaluation → serving → model-card/source/rights readback | Owner signature and policy, provider-level trust anchors, trainer process identity, complete tokenizer/config/revision rights, GPU accuracy replication, production ATO |

All stages are **mandatory for their own profile**, with a fixed acyclic
parent-dependency graph. The plan lists the exact expected content digests and
immutable bindings. A stage must declare a consistent SHA-256 artifact,
source revision and expected predecessor fingerprints. Runtime readbacks have a
5-minute default in the synthetic fixture; the caller can choose 30–3600 seconds
for a documented operating cadence. HTTP 401/403/429 results cause an explicit
stop, not fallback credentials or endpoint hopping. The provider list requires
distinct instance identities, exact image digests, stable desired/running counts
and zero pending changes. Failed evaluation controls, missing heldout cases,
missing backup or unsafely skipped CI qualification gates cause `HOLD`.

The stage claims are **not** proof of actual external verification. The graph
cannot query Salad, verify OCI/Cosign signatures, test model weights, inspect
private datasets, determine if a model can serve traffic, or confirm the
source was truly reviewed. All inputs are untrusted data. The strongest
successful classification is `SOURCE_CLAIM_GRAPH_FOR_OWNER_REVIEW` with
`deployment_authorized=false`, `production_qualified=false`,
`training_quality_proven=false` and `external_attestation_verified=false`.

## What a real owner must provide before any deployment

1. **GitHub:** protected source SHA, signature/DCO/independent reviews, exact
   head checks and **all required** qualification checks observed, with no
   skipped mandatory jobs. A check marked green is not the runtime witness.
2. **Build:** externally verified SLSA provenance and Cosign signer/builder
   identity, immutable image digest and actual contents bound to protected
   source. Never infer this from a Dockerfile or a successful image-build job.
3. **Provider:** authenticated desired + all actual instance readback with
   image digest on every relevant instance, owner lease, UTC clock and a
   fresh running-process/step witness. A group PATCH HTTP 200 alone is
   neither deployed state nor training progress. Leave Flagship54 shutdown
   to its existing sole guard.
4. **Training/preservation:** full trainer/optimizer/RNG/scheduler state,
   terminal steps, immutable checkpoint byte manifests, independent backup
   readback and an approved resume canary. Never deserialize opaque
   optimizer/pickle payloads during auditing.
5. **Evaluation:** correct immutable model/dataset binding, pre-registered
   heldout criteria, complete attempted-task denominator, negative controls,
   independent evaluator, baselines, uncertainty and observed quality.
6. **Serving/publication:** authenticated route, negative security/tenant
   test, **no automatic replay of uncertain non-idempotent requests**, exact
   request→producer→receipt binding, source image/model revision readback,
   authorized claim/rights review and final public card/endpoint byte
   readback. In particular, [szl-router #153](https://github.com/szl-holdings/szl-router/pull/153)
   is a real **Kimi + Mistral reviewed source candidate**, whose protected
   source checks passed, for stopping replay after a POST may have reached a
   worker. It remains separate from observed Cloudflare settlement, paid
   inference, and a deployed route. A changed source response label is not
   proof a particular request executed exactly once. PyPI, Cloudflare,
   Neon, Hugging Face and billing each have their own separate publisher
   and production gates; none can be proven by this source module.

### Precise mathematical status

This is typed **source evidence consistency**, not a Lean theorem. The
published SZL formula mapping lists F1 replay, F4 DAG, F7 FIFO, F11 ledger,
F12 coupling, F18 recovery, F19 entropy budget and F22 append-only. This
module checks a **small declared DAG** and integer count consistency, not
proofs of those eight formula implementations. Unconditional Λ uniqueness
was disproved as stated; conditional Theorem U is distinct. No novel
mathematical result or "better than all leaders" claim follows.

### Test procedure

Normal source-owned GitHub CI (Python 3.11/3.12), **not** a new laptop
job, runs:

```sh
python -m pytest tests/test_runtime_claim_graph.py -v
```

Synthetic fixtures are expressly marked, and tests never make provider
requests. They reject skipped stages, malformed source versions, mismatched
parent hashes, stale runtime evidence, unauthorized access, unreviewed
source, unsigned image claim, incomplete providers, defective checkpoints,
backup drift, failed heldout controls, serving isolation gaps, and unreviewed
publication. Successful tests are **software-contract verification only**.

If any real deployment report relies on this source-only verdict as proof
of release authorization, the report must be corrected and held.
