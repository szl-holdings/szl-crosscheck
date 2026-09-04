# szl-crosscheck

Two independent implementations of the same measurement disagree quietly more
often than teams admit. This package ends that: feed it the receipt chains from
**both** harnesses and get one verdict — `CONSISTENT`, `DIVERGENT` (with the
metric and max relative delta named), `INCOMPARABLE` (no shared MEASURED lanes),
or `INVALID` (a chain failed verification — fail closed).

Built to settle the duplicated bench layer in this org: the stdlib repos
(`szl-retrieval-bench`, `szl-engine-bench`, `szl-quant-bench`) and the FastAPI
planes (`retrieval-bench`, `frontier-bench`, `quant-curve`) both emit
hash-chained receipts. Run both on the same hardware and corpus, crosscheck
the chains, and the dual receipt tells you whether the two stacks agree —
no assertion, just recomputation.

## Doctrine

- Both chains verify before anything is compared. Tampering voids the run.
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

## License

Apache-2.0 — see LICENSE (same text as the org's other bench repos).
