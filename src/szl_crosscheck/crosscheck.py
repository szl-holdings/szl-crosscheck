"""szl-crosscheck: two independent harnesses' receipt chains in, one truth verdict out.

Doctrine:
- Both chains must verify. A broken chain voids the run (fail closed).
- Only shared MEASURED lanes are compared. Disjoint lane sets are
  INCOMPARABLE, never forced.
- Divergence names the metric and the max relative delta. No silent passes.
- The dual receipt commits to both terminal hashes + every lane verdict.
"""
from __future__ import annotations
import hashlib, json
from typing import Any, Dict, List, Tuple

GENESIS = "0" * 64

def canonical(o: Any) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)

def verify_chain(receipts: List[Dict[str, Any]]) -> Tuple[bool, str]:
    if not receipts:
        return False, "empty chain"
    prev = GENESIS
    for i, r in enumerate(receipts):
        if r.get("prev_hash") != prev:
            return False, f"link broken at receipt {i}"
        payload = {k: v for k, v in r.items() if k not in ("prev_hash", "chain_hash")}
        expected = hashlib.sha256((prev + canonical(payload)).encode()).hexdigest()
        if r.get("chain_hash") != expected:
            return False, f"payload tampered at receipt {i}"
        prev = r["chain_hash"]
    return True, f"chain valid ({len(receipts)} receipts)"

def _measured_lanes(chain: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    lanes: Dict[str, Dict[str, float]] = {}
    for r in chain:
        for res in (r.get("results") or []):
            if isinstance(res, dict) and res.get("runs") and isinstance(res.get("metrics"), dict):
                lane = str(res.get("engine") or res.get("lane") or res.get("name") or "run")
                lanes[lane] = {k: float(v) for k, v in res["metrics"].items() if isinstance(v, (int, float))}
    return lanes

def crosscheck(chain_a: List[Dict[str, Any]], chain_b: List[Dict[str, Any]],
               rel_tol: float = 0.01) -> Dict[str, Any]:
    """Compare two independent implementations' receipt chains over shared lanes."""
    ok_a, det_a = verify_chain(chain_a)
    ok_b, det_b = verify_chain(chain_b)
    if not ok_a:
        return {"verdict": "INVALID", "reason": f"chain A: {det_a}"}
    if not ok_b:
        return {"verdict": "INVALID", "reason": f"chain B: {det_b}"}
    la, lb = _measured_lanes(chain_a), _measured_lanes(chain_b)
    shared = sorted(set(la) & set(lb))
    if not shared:
        return {"verdict": "INCOMPARABLE", "reason": "no shared MEASURED lanes",
                "a_lanes": sorted(la), "b_lanes": sorted(lb)}
    verdicts = []
    overall = "CONSISTENT"
    for lane in shared:
        common = sorted(set(la[lane]) & set(lb[lane]))
        if not common:
            verdicts.append({"lane": lane, "verdict": "INCOMPARABLE", "reason": "no shared metric keys"})
            continue
        worst, worst_k = 0.0, None
        for k in common:
            va, vb = la[lane][k], lb[lane][k]
            delta = abs(va - vb) / max(abs(va), abs(vb), 1e-12)
            if delta > worst:
                worst, worst_k = delta, k
        v = "CONSISTENT" if worst <= rel_tol else "DIVERGENT"
        if v == "DIVERGENT":
            overall = "DIVERGENT"
        verdicts.append({"lane": lane, "verdict": v, "max_rel_delta": round(worst, 6),
                         "worst_metric": worst_k, "metrics_compared": len(common)})
    a_term, b_term = chain_a[-1]["chain_hash"], chain_b[-1]["chain_hash"]
    dual = hashlib.sha256(canonical({"a": a_term, "b": b_term,
                                     "verdicts": verdicts, "tol": rel_tol}).encode()).hexdigest()
    return {"verdict": overall, "lanes": verdicts, "tolerance": rel_tol,
            "a_terminal": a_term[:16], "b_terminal": b_term[:16], "dual_receipt": dual,
            "label": "cross-implementation verification - two chains, one truth test"}
