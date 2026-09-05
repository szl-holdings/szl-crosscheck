"""Verify complete inputs before comparing compatible measurements."""
import hashlib
import json
import math
import re

GENESIS = "0" * 64


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def verify_chain(receipts):
    if not isinstance(receipts, list) or not receipts:
        return False, "empty or malformed chain"
    previous = GENESIS
    try:
        for index, receipt in enumerate(receipts):
            if not isinstance(receipt, dict) or receipt.get("prev_hash") != previous:
                return False, f"link broken at receipt {index}"
            payload = {k: v for k, v in receipt.items() if k not in ("prev_hash", "chain_hash")}
            expected = hashlib.sha256((previous + canonical(payload)).encode()).hexdigest()
            if receipt.get("chain_hash") != expected:
                return False, f"payload tampered at receipt {index}"
            previous = expected
    except (ValueError, TypeError, OverflowError):
        return False, "receipt contains non-JSON or nonfinite values"
    return True, previous


def seal(payload):
    """Create an integrity envelope; this is not identity attestation."""
    payload = json.loads(canonical(payload))
    if "prev_hash" in payload or "chain_hash" in payload:
        raise ValueError("payload cannot supply chain fields")
    return [{**payload, "prev_hash": GENESIS,
             "chain_hash": hashlib.sha256((GENESIS + canonical(payload)).encode()).hexdigest()}]


def validate_context(context):
    if not isinstance(context, dict):
        raise ValueError("missing measurement context")
    for key in ("machine", "dataset_revision", "model_revision", "parameters", "input_hashes", "source"):
        if key not in context or not context[key]:
            raise ValueError(f"missing context.{key}")
    if not isinstance(context["machine"], dict) or not all(
        context["machine"].get(k) for k in ("identity", "cpu", "os", "python")
    ):
        raise ValueError("machine must bind identity, cpu, os, and python")
    if not isinstance(context["parameters"], dict):
        raise ValueError("parameters must be an object")
    hashes = context["input_hashes"]
    if not isinstance(hashes, dict) or not all(
        isinstance(hashes.get(k), str) and re.fullmatch(r"[0-9a-f]{64}", hashes[k])
        for k in ("corpus", "queries", "qrels")
    ):
        raise ValueError("input_hashes must bind corpus, queries, and qrels")
    source = context["source"]
    if not isinstance(source, dict) or not source.get("repository") or not (
        isinstance(source.get("commit"), str) and re.fullmatch(r"[0-9a-f]{40}", source["commit"])
    ):
        raise ValueError("source must name repository and full commit")
    return {k: v for k, v in context.items() if k != "source"}


def _measurements(chain):
    lanes, contexts, sources = {}, [], []
    for receipt in chain:
        results = receipt.get("results", [])
        if not isinstance(results, list):
            raise ValueError("results must be a list")
        for result in results:
            if not isinstance(result, dict):
                raise ValueError("result must be an object")
            if result.get("state") != "MEASURED":
                continue
            context = receipt.get("context")
            contexts.append(validate_context(context))
            sources.append(context["source"])
            lane, metrics = result.get("lane"), result.get("metrics")
            if not isinstance(lane, str) or not lane or lane in lanes:
                raise ValueError("missing or ambiguous duplicate measured lane")
            if not isinstance(metrics, dict) or not metrics:
                raise ValueError("MEASURED requires nonempty metrics")
            if not all(isinstance(k, str) and type(v) in (int, float) and math.isfinite(v)
                       for k, v in metrics.items()):
                raise ValueError("metrics must be finite numbers, not booleans or strings")
            lanes[lane] = metrics
    if contexts and any(c != contexts[0] for c in contexts[1:]):
        raise ValueError("mixed measurement contexts within a chain")
    return lanes, contexts[0] if contexts else None, sources


def crosscheck(chain_a, chain_b, rel_tol=0.01):
    if type(rel_tol) not in (int, float) or not math.isfinite(rel_tol) or rel_tol < 0:
        return {"verdict": "INVALID", "reason": "tolerance must be finite and nonnegative"}
    for name, chain in (("A", chain_a), ("B", chain_b)):
        valid, detail = verify_chain(chain)
        if not valid:
            return {"verdict": "INVALID", "reason": f"chain {name}: {detail}"}
    try:
        lanes_a, context_a, sources_a = _measurements(chain_a)
        lanes_b, context_b, sources_b = _measurements(chain_b)
    except (ValueError, TypeError, OverflowError) as error:
        return {"verdict": "INVALID", "reason": str(error)}
    report = {"schema": "szl.crosscheck.v2", "tolerance": rel_tol,
              "a_terminal": chain_a[-1]["chain_hash"], "b_terminal": chain_b[-1]["chain_hash"],
              "sources": {"a": sources_a, "b": sources_b}, "lanes": [],
              "honesty": "UNSIGNED_HONEST; integrity does not prove accuracy or identity"}
    shared = sorted(set(lanes_a) & set(lanes_b))
    if context_a != context_b:
        report.update(verdict="INCOMPARABLE", reason="machine, inputs, model, or parameters differ")
    elif not shared:
        report.update(verdict="INCOMPARABLE", reason="no shared MEASURED lanes")
    else:
        for lane in shared:
            common = sorted(set(lanes_a[lane]) & set(lanes_b[lane]))
            if not common:
                report["lanes"].append({"lane": lane, "verdict": "INCOMPARABLE",
                                        "reason": "no shared metric keys"})
                continue
            deltas = {}
            for key in common:
                a, b = lanes_a[lane][key], lanes_b[lane][key]
                scale = max(abs(a), abs(b), 1e-12)
                deltas[key] = abs(a / scale - b / scale)
            worst = max(deltas, key=deltas.get)
            report["lanes"].append({"lane": lane,
                                    "verdict": "CONSISTENT" if deltas[worst] <= rel_tol else "DIVERGENT",
                                    "max_rel_delta": deltas[worst], "worst_metric": worst,
                                    "metrics_compared": len(common), "deltas": deltas})
        verdicts = {row["verdict"] for row in report["lanes"]}
        report["verdict"] = ("DIVERGENT" if "DIVERGENT" in verdicts else
                             "INCOMPARABLE" if "INCOMPARABLE" in verdicts else "CONSISTENT")
    report["dual_receipt"] = hashlib.sha256(canonical(report).encode()).hexdigest()
    return report
