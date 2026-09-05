import hashlib
import json
from pathlib import Path

from szl_crosscheck.crosscheck import canonical, crosscheck


def test_recorded_native_scifact_dual_receipt_recomputes():
    path = Path(__file__).resolve().parents[1] / "evidence/2026-09-05/crosscheck-native-scifact-20260905.json"
    bundle = json.loads(path.read_text(encoding="utf-8"))
    receipt = bundle.pop("receipt")
    assert hashlib.sha256(canonical(bundle).encode()).hexdigest() == receipt
    assert crosscheck(bundle["stdlib_chain"], bundle["fastapi_chain"], 0.01) == bundle["dual_report"]
    assert bundle["dual_report"]["verdict"] == "DIVERGENT"
    assert bundle["queries"] == 300 and bundle["corpus_size"] == 5183
    assert bundle["negative_control"]["verdict"] == "INVALID"
