# szl-crosscheck

Two independent implementations of the same measurement disagree quietly more
often than teams admit. This package ends that: feed it the receipt chains from
**both** harnesses and get one verdict — `CONSISTENT`, `DIVERGENT` (with the
metric and max relative delta named), `INCOMPARABLE` (no shared MEASURED lanes),
or `INVALID` (a chain failed verification — fail closed).

Built to settle the duplicated bench layer in this org: the stdlib repos
(`szl-retrieval-bench`, `szl-engine-bench`, `szl-quant-bench`) and the FastAPI
planes (`retrieval-bench`, `frontier-bench`, `quant-curve`). Their receipt
formats differ: the retrieval HTTP runner returns an **unchained** RunReceipt,
while the stdlib runner uses a `self_hash` chain. Explicit adapters preserve
these native records inside an adapter-owned integrity envelope. This does
not claim that the HTTP service emitted a chain or attested the caller's context.

## Doctrine

- Both chains verify before anything is compared. Tampering voids the run.
- Measured results require matching machine identity, CPU, OS, Python version,
  dataset/model revision, parameters, and corpus/query/qrels hashes. Source
  repository commits are recorded separately so independent implementations
  can differ. These fields are declared evidence, not hardware attestation.
- Only shared MEASURED lanes with shared metric keys are compared.
- Divergence is always named: lane, metric, max relative delta.
- The dual receipt commits to both terminal hashes and every lane verdict —
  same chains, same tolerance, same receipt, any machine.

## Usage

```bash
pip install -e . pytest && python -m pytest tests/ -q
```

```python
import json
from szl_crosscheck import crosscheck

a = json.loads(open("stdlib-chain.json").read())
b = json.loads(open("plane-chain.json").read())
print(crosscheck(a, b, rel_tol=0.01)["verdict"])
```

## Scope

Python 3.11+, standard library only. Never re-measures; verifies and compares
what the harnesses already receipted. Numbers from different hardware remain
incomparable by design.

## Native BM25 adapters

`szl_crosscheck.adapters.stdlib_retrieval(chain, context)` validates the native
stdlib chain and requires its final `run.context` to equal the supplied context.
Its final `run.result` must be a measured BM25 result at the declared cutoff.
`fastapi_retrieval(response, context, captured_inputs)` checks the HTTP response's
dataset, qrels, model/config and result hashes, then binds all three captured
input hashes. The native HTTP response has no query hash: request capture is
caller-declared, not cryptographic proof that the server processed that query.
Both adapters compare only the shared nDCG@10 and Recall@10 by default; they
retain the complete native records, including non-compared metrics.

Context is an object containing `machine` (`identity`, `cpu`, `os`, `python`),
`dataset_revision`, `model_revision`, `parameters` (`top_k`, `k1`, `b`),
`input_hashes` (full SHA-256 values for `corpus`, `queries`, `qrels`) and
`source` (`repository` and full 40-character `commit`). Input hashes use UTF-8
JSON with sorted keys, compact separators, default ASCII escaping and no NaN.
Do not relabel fixture inputs as a real benchmark. Source commits and input
hashes support reproducibility; unsigned receipts do not prove signer identity.

## Recorded native run

`evidence/2026-09-05/crosscheck-native-scifact-20260905.json` records an actual
same-machine run over all 5,183 cached public SciFact documents and 300 test
queries. The FastAPI side was called using an actual loopback HTTP POST and
the ephemeral server was stopped afterward. With identical inputs and BM25
parameters, nDCG@10 was 0.6380 (stdlib) and 0.6643898053153046 (FastAPI).
The 3.972% relative difference is **DIVERGENT** at the declared 1% tolerance.
The native tokenizers differ; this receipt demonstrates the disagreement,
not interchangeability or a performance ranking. Full normalized input chains,
native records, source pins and input hashes are retained. CI recomputes both
the complete bundle hash and dual report; it does not rerun the corpus benchmark.

## License

Apache-2.0 — see LICENSE (same text as the org's other bench repos).
