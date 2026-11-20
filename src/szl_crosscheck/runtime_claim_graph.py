"""Pure, non-authorizing source-to-runtime release-claim graph comparator.

Structural comparison only. Inputs can be fabricated; SHA strings, verifier
identities, success booleans and source revisions are NOT authenticated here.
No provider API, secrets, source code execution, network, files, or subprocesses.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

SCHEMA = "szl.source-runtime-claim-graph/v1"
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z\Z")

STAGES = {
    "edge_service": ("source", "ci", "image", "provider", "serving", "publication"),
    "served_model": (
        "source", "ci", "image", "provider", "checkpoint",
        "backup", "evaluation", "serving", "publication",
    ),
}
PARENTS = {
    "source": (),
    "ci": ("source",),
    "image": ("source", "ci"),
    "provider": ("image",),
    "checkpoint": ("provider",),
    "backup": ("checkpoint",),
    "evaluation": ("checkpoint", "backup"),
    "serving": ("provider", "evaluation"),
    "publication": ("serving", "evaluation"),
}
BINDINGS = {
    "source": ("source_revision",),
    "ci": ("source_revision",),
    "image": ("source_revision", "image_digest"),
    "provider": ("image_digest", "owner_lease_digest"),
    "checkpoint": ("model_revision", "dataset_revision", "checkpoint_digest"),
    "backup": ("checkpoint_digest",),
    "evaluation": ("model_revision", "dataset_revision", "checkpoint_digest"),
    "serving": ("model_revision",),
    "publication": ("model_revision", "source_revision"),
}
PLAN_KEYS = {
    "schema", "profile", "source_revision", "proposer_digest",
    "expected_artifacts", "bindings", "minimum_correct_cases",
    "minimum_evaluation_cases", "required_qualification_checks",
    "maximum_runtime_age_seconds",
}
NODE_KEYS = {
    "stage", "artifact_sha256", "bindings", "parents",
    "evidence_sha256", "verifier_digest", "observed_at_utc",
    "state", "access_status", "claims",
}
RUNTIME_STAGES = {"provider", "serving"}
ACCESS_STOP = {401, 403, 429}


def _hold(reason: str, *, stage: str | None = None) -> dict:
    """Never echo potentially private claim content, paths or group names."""
    result = {
        "schema": SCHEMA,
        "verdict": "HOLD",
        "reason": reason,
        "source_content_consistent": False,
        "external_attestation_verified": False,
        "actual_runtime_proven": False,
        "training_quality_proven": False,
        "deployment_authorized": False,
        "publication_authorized": False,
        "production_qualified": False,
    }
    if stage is not None:
        result["stage"] = stage
    return result


def _sha(value: object, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and bool(pattern.fullmatch(value))


def _utc(value: object) -> datetime | None:
    if type(value) is not str or not _TIME.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _count(value: object, *, minimum: int = 0, maximum: int = 1_000_000) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _parents(profile: str, stage: str) -> tuple[str, ...]:
    if profile == "edge_service" and stage == "serving":
        return ("provider",)
    if profile == "edge_service" and stage == "publication":
        return ("serving",)
    return PARENTS[stage]


def _bindings(profile: str, stage: str) -> tuple[str, ...]:
    if profile == "edge_service" and stage in ("serving", "publication"):
        return ("source_revision", "image_digest") if stage == "serving" else (
            "source_revision",
        )
    return BINDINGS[stage]


def _extra(stage: str, values: object, plan: dict) -> str | None:
    if type(values) is not dict:
        return "STAGE_CLAIMS_INVALID"
    if stage == "source":
        return None if values == {"protected_reviewed_source": True} else "SOURCE_REVIEW_UNVERIFIED"
    if stage == "ci":
        if set(values) != {"passed", "required", "qualification_skips"}:
            return "CI_COUNTS_UNOBSERVED"
        if (
            not _count(values["passed"], minimum=1)
            or not _count(values["required"], minimum=1)
            or values["passed"] != values["required"]
            or values["required"] < plan["required_qualification_checks"]
            or values["qualification_skips"] != 0
            or type(values["qualification_skips"]) is not int
        ):
            return "CI_INCOMPLETE_OR_SKIPPED"
        return None
    if stage == "image":
        keys = {"signature_checked", "provenance_subject_checked", "builder_identity_checked"}
        return None if set(values) == keys and all(values[k] is True for k in keys) else "SIGNED_IMAGE_UNVERIFIED"
    if stage == "provider":
        if set(values) != {
            "desired_replicas", "running_instances", "all_instances_observed",
            "pending_change",
        }:
            return "PROVIDER_COUNTS_UNOBSERVED"
        if (
            not _count(values["desired_replicas"], minimum=1, maximum=64)
            or not _count(values["running_instances"], minimum=1, maximum=64)
            or values["running_instances"] > values["desired_replicas"]
            or values["all_instances_observed"] is not True
            or values["pending_change"] is not False
        ):
            return "PROVIDER_INSTANCES_UNVERIFIED"
        return None
    if stage == "checkpoint":
        if set(values) != {
            "global_step", "target_steps", "full_optimizer_rng_scheduler",
            "opaque_bytes_readback",
        }:
            return "TRAINER_STATE_UNOBSERVED"
        if (
            not _count(values["global_step"], minimum=1)
            or values["global_step"] != values["target_steps"]
            or type(values["target_steps"]) is not int
            or values["full_optimizer_rng_scheduler"] is not True
            or values["opaque_bytes_readback"] is not True
        ):
            return "RESUMABLE_CHECKPOINT_UNVERIFIED"
        return None
    if stage == "backup":
        return None if values == {
            "independent_storage_readback": True,
            "matching_checkpoint_bytes": True,
        } else "INDEPENDENT_BACKUP_UNVERIFIED"
    if stage == "evaluation":
        if set(values) != {
            "attempted", "correct", "failed_negative_controls",
            "heldout_frozen", "independent_evaluator",
        }:
            return "EVALUATION_DENOMINATOR_UNOBSERVED"
        if (
            not _count(values["attempted"], minimum=plan["minimum_evaluation_cases"])
            or not _count(values["correct"])
            or values["correct"] > values["attempted"]
            or values["correct"] < plan["minimum_correct_cases"]
            or type(values["failed_negative_controls"]) is not int
            or values["failed_negative_controls"] != 0
            or values["heldout_frozen"] is not True
            or values["independent_evaluator"] is not True
        ):
            return "HELDOUT_QUALITY_UNVERIFIED"
        return None
    if stage == "serving":
        keys = {"authenticated_probe", "source_revision_readback", "tenant_boundary_negative_test"}
        return None if set(values) == keys and all(values[k] is True for k in keys) else "SERVING_SECURITY_OR_SOURCE_UNVERIFIED"
    if stage == "publication":
        keys = {"bytes_read_back", "rights_reviewed", "claim_denominators_present"}
        return None if set(values) == keys and all(values[k] is True for k in keys) else "PUBLICATION_CLAIMS_UNVERIFIED"
    return "UNKNOWN_STAGE"


def review_release_graph(*, plan: object, nodes: object, now_utc: str) -> dict:
    """Compare a caller's declared release evidence; never authorize production.

    The returned positive verdict is only a structural *candidate for review*.
    Without separate trusted signed source, provider, signer, scope, and
    evaluator readbacks this function cannot certify any real-world claim.
    """
    now = _utc(now_utc)
    if now is None:
        return _hold("CLOCK_UNOBSERVED")
    if type(plan) is not dict or set(plan) != PLAN_KEYS or plan.get("schema") != SCHEMA:
        return _hold("PLAN_SCHEMA_INVALID")
    profile = plan["profile"]
    if type(profile) is not str or profile not in STAGES:
        return _hold("PROFILE_INVALID")
    stages = STAGES[profile]
    if not _sha(plan["source_revision"], _SHA40):
        return _hold("SOURCE_REVISION_INVALID")
    if not _sha(plan["proposer_digest"], _SHA64):
        return _hold("PROPOSER_IDENTITY_INVALID")
    if (
        not _count(plan["required_qualification_checks"], minimum=1, maximum=10000)
        or not _count(plan["maximum_runtime_age_seconds"], minimum=30, maximum=3600)
        or not _count(plan["minimum_evaluation_cases"], minimum=0, maximum=100000)
        or not _count(plan["minimum_correct_cases"], minimum=0, maximum=100000)
    ):
        return _hold("POLICY_LIMITS_INVALID")
    if profile == "served_model":
        if (
            plan["minimum_evaluation_cases"] < 1
            or plan["minimum_correct_cases"] > plan["minimum_evaluation_cases"]
        ):
            return _hold("HELDOUT_POLICY_INVALID")
    elif plan["minimum_evaluation_cases"] != 0 or plan["minimum_correct_cases"] != 0:
        return _hold("UNSCOPED_EVALUATION_POLICY")

    expected = plan["expected_artifacts"]
    if (
        type(expected) is not dict
        or set(expected) != set(stages)
        or any(not _sha(v, _SHA64) for v in expected.values())
    ):
        return _hold("EXPECTED_ARTIFACT_SET_INVALID")
    bindings = plan["bindings"]
    wanted = {"source_revision", "image_digest", "owner_lease_digest"}
    if profile == "served_model":
        wanted |= {"model_revision", "dataset_revision", "checkpoint_digest"}
    if type(bindings) is not dict or set(bindings) != wanted:
        return _hold("RELEASE_BINDING_SCHEMA_INVALID")
    for key in wanted:
        pattern = _SHA40 if key.endswith("revision") else _SHA64
        if not _sha(bindings[key], pattern):
            return _hold("RELEASE_BINDING_DIGEST_INVALID")
    if bindings["source_revision"] != plan["source_revision"]:
        return _hold("SOURCE_BINDING_MISMATCH")

    if type(nodes) is not list or len(nodes) != len(stages):
        return _hold("STAGE_POPULATION_INCOMPLETE")
    by_stage = {}
    for node in nodes:
        if type(node) is not dict or set(node) != NODE_KEYS:
            return _hold("NODE_SCHEMA_INVALID")
        name = node["stage"]
        if type(name) is not str or name not in stages or name in by_stage:
            return _hold("NODE_STAGE_DUPLICATE_OR_UNKNOWN")
        by_stage[name] = node
    for stage in stages:
        node = by_stage[stage]
        code = node["access_status"]
        if type(code) is int and code in ACCESS_STOP:
            return _hold("ACCESS_DENIAL_OR_RATE_LIMIT_STOP", stage=stage)
        if code is not None and (type(code) is not int or code != 200):
            return _hold("PROVIDER_READBACK_NOT_SUCCESS", stage=stage)
        if node["state"] != "PASS" or type(node["state"]) is not str:
            return _hold("STAGE_NOT_PROVED", stage=stage)
        if (
            not _sha(node["artifact_sha256"], _SHA64)
            or node["artifact_sha256"] != expected[stage]
            or not _sha(node["evidence_sha256"], _SHA64)
            or not _sha(node["verifier_digest"], _SHA64)
            or node["verifier_digest"] == plan["proposer_digest"]
        ):
            return _hold("ARTIFACT_OR_INDEPENDENCE_BINDING_UNVERIFIED", stage=stage)
        t = _utc(node["observed_at_utc"])
        if t is None or t > now + timedelta(seconds=30):
            return _hold("STAGE_CLOCK_UNOBSERVED", stage=stage)
        if stage in RUNTIME_STAGES and (
            t < now - timedelta(seconds=plan["maximum_runtime_age_seconds"])
        ):
            return _hold("RUNTIME_READBACK_STALE", stage=stage)
        keys = _bindings(profile, stage)
        wanted_bindings = {key: bindings[key] for key in keys}
        if type(node["bindings"]) is not dict or node["bindings"] != wanted_bindings:
            return _hold("STAGE_RELEASE_BINDING_MISMATCH", stage=stage)
        parent_names = _parents(profile, stage)
        expected_parents = {p: expected[p] for p in parent_names}
        if type(node["parents"]) is not dict or node["parents"] != expected_parents:
            return _hold("EVIDENCE_GRAPH_EDGE_MISMATCH", stage=stage)
        reason = _extra(stage, node["claims"], plan)
        if reason is not None:
            return _hold(reason, stage=stage)
    result = _hold("CLAIM_GRAPH_CONSISTENT_BUT_NOT_INDEPENDENTLY_ATTESTED")
    result["verdict"] = "SOURCE_CLAIM_GRAPH_FOR_OWNER_REVIEW"
    result["source_content_consistent"] = True
    result["profile"] = profile
    result["compared_stages"] = len(stages)
    return result
