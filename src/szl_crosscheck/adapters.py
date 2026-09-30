"""Explicit native retrieval adapters. All native receipts remain in the envelope.

The FastAPI runner emits an unchained RunReceipt. This adapter creates its
normalized integrity envelope; it does not claim the HTTP service emitted one.
"""
import hashlib
import json

from .crosscheck import GENESIS, canonical, seal, validate_context


def _native_digest(value, *, ensure_ascii=True, compact=True):
    options = {"sort_keys": True, "ensure_ascii": ensure_ascii, "allow_nan": False}
    if compact:
        options["separators"] = (",", ":")
    return hashlib.sha256(json.dumps(value, **options).encode()).hexdigest()


def stdlib_retrieval(chain, context, metric_keys=("ndcg@10", "recall@10")):
    validate_context(context)
    if not isinstance(chain, list) or not chain:
        raise ValueError("empty stdlib chain")
    previous = GENESIS
    for receipt in chain:
        if not isinstance(receipt, dict) or receipt.get("prev_hash") != previous:
            raise ValueError("broken native stdlib chain")
        payload = {k: v for k, v in receipt.items() if k != "self_hash"}
        if receipt.get("self_hash") != _native_digest(payload, ensure_ascii=False):
            raise ValueError("tampered native stdlib receipt")
        previous = receipt["self_hash"]
    record = chain[-1].get("run", {})
    if record.get("context") != context:
        raise ValueError("stdlib native receipt must bind the supplied context")
    result = record.get("result", {})
    if result.get("state") != "MEASURED" or result.get("lane") != "bm25":
        raise ValueError("adapter requires a measured BM25 result")
    if result.get("k") != context["parameters"].get("top_k"):
        raise ValueError("stdlib cutoff differs from context")
    return seal({"harness": "stdlib-retrieval", "context": context,
                 "native_schema": "ReceiptChain.self_hash", "native_chain": chain,
                 "results": [{"state": "MEASURED", "lane": "bm25",
                              "metrics": {k: result["aggregate"][k] for k in metric_keys}}]})


def fastapi_retrieval(run, context, inputs, metric_keys=("ndcg@10", "recall@10")):
    validate_context(context)
    if not isinstance(run, dict) or not isinstance(inputs, dict):
        raise ValueError("native response and captured inputs must be objects")
    if run.get("status") != "MEASURED" or run.get("lane") != "sparse_bm25":
        raise ValueError("adapter requires a measured sparse_bm25 HTTP response")
    for key in ("corpus", "queries", "qrels"):
        if hashlib.sha256(canonical(inputs[key]).encode()).hexdigest() != context["input_hashes"][key]:
            raise ValueError(f"{key} input hash mismatch")
    query_hash_supplied = "query_hash" in run
    native_bindings = [("dataset_hash", "corpus"), ("qrels_hash", "qrels")]
    if query_hash_supplied:
        native_bindings.append(("query_hash", "queries"))
    for native_key, input_key in native_bindings:
        if run.get(native_key) != _native_digest(inputs[input_key], compact=False):
            raise ValueError(f"native {native_key} mismatch")
    parameters = context["parameters"]
    model = f"bm25-k1={parameters['k1']}-b={parameters['b']}"
    if (run.get("model_revision") != model or run.get("model_revision") != context["model_revision"]
            or run.get("config", {}).get("top_k") != parameters["top_k"]):
        raise ValueError("native model/config differs from context")
    if run.get("result_hash") != _native_digest(run.get("metrics"), compact=False):
        raise ValueError("native result hash mismatch")
    limitations = ["HTTP response has no native chain; matching hashes do not prove execution, accuracy, or identity"]
    if not query_hash_supplied:
        limitations.append("Legacy HTTP response omits query_hash; query binding relies on captured request inputs")
    return seal({"harness": "fastapi-retrieval", "context": context,
                 "native_schema": "RunReceipt (unchained HTTP response)", "native_run": run,
                 "context_assurance": "CALLER_DECLARED_CAPTURE",
                 "native_query_hash_state": "MATCHED" if query_hash_supplied else "UNVERIFIED_LEGACY",
                 "native_limitations": limitations,
                 "results": [{"state": "MEASURED", "lane": "bm25",
                              "metrics": {k: run["metrics"][k] for k in metric_keys}}]})
