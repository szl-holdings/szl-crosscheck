"""Synthetic fail-closed source/runtime evidence-graph tests. No providers used."""

from copy import deepcopy

from szl_crosscheck.runtime_claim_graph import (
    SCHEMA,
    STAGES,
    _bindings,
    _parents,
    review_release_graph,
)

NOW = "2026-11-20T03:00:00Z"


def fixture(profile="served_model"):
    stages = STAGES[profile]
    artifacts = {name: f"{i+1:064x}" for i, name in enumerate(stages)}
    bindings = {
        "source_revision": "a" * 40,
        "image_digest": artifacts["image"],
        "owner_lease_digest": "b" * 64,
    }
    if profile == "served_model":
        bindings.update(
            model_revision="c" * 40,
            dataset_revision="d" * 40,
            checkpoint_digest=artifacts["checkpoint"],
        )
    plan = {
        "schema": SCHEMA,
        "profile": profile,
        "source_revision": "a" * 40,
        "proposer_digest": "1" * 64,
        "expected_artifacts": artifacts,
        "bindings": bindings,
        "minimum_correct_cases": 80 if profile == "served_model" else 0,
        "minimum_evaluation_cases": 100 if profile == "served_model" else 0,
        "required_qualification_checks": 5,
        "maximum_runtime_age_seconds": 300,
    }
    claims = {
        "source": {"protected_reviewed_source": True},
        "ci": {"passed": 5, "required": 5, "qualification_skips": 0},
        "image": {
            "signature_checked": True,
            "provenance_subject_checked": True,
            "builder_identity_checked": True,
        },
        "provider": {
            "desired_replicas": 1,
            "running_instances": 1,
            "all_instances_observed": True,
            "pending_change": False,
            "instances": [
                {
                    "identity_digest": "3" * 64,
                    "image_digest": artifacts["image"],
                    "status": "running",
                }
            ],
        },
        "checkpoint": {
            "global_step": 120,
            "target_steps": 120,
            "full_optimizer_rng_scheduler": True,
            "opaque_bytes_readback": True,
        },
        "backup": {
            "independent_storage_readback": True,
            "matching_checkpoint_bytes": True,
        },
        "evaluation": {
            "attempted": 100,
            "correct": 85,
            "failed_negative_controls": 0,
            "heldout_frozen": True,
            "independent_evaluator": True,
        },
        "serving": {
            "authenticated_probe": True,
            "source_revision_readback": True,
            "tenant_boundary_negative_test": True,
            "uncertain_dispatch_replay_negative_test": True,
            "exact_request_receipt_binding": True,
        },
        "publication": {
            "bytes_read_back": True,
            "rights_reviewed": True,
            "claim_denominators_present": True,
        },
    }
    nodes = []
    for i, stage in enumerate(stages):
        nodes.append(
            {
                "stage": stage,
                "artifact_sha256": artifacts[stage],
                "bindings": {k: bindings[k] for k in _bindings(profile, stage)},
                "parents": {k: artifacts[k] for k in _parents(profile, stage)},
                "evidence_sha256": f"{i+100:064x}",
                "verifier_digest": "2" * 64,
                "observed_at_utc": NOW,
                "state": "PASS",
                "access_status": 200 if stage in (
                    "provider", "serving", "publication"
                ) else None,
                "claims": deepcopy(claims[stage]),
            }
        )
    return plan, nodes


def assess(plan, nodes, now=NOW):
    return review_release_graph(plan=plan, nodes=nodes, now_utc=now)


def node_at(nodes, stage):
    return next(x for x in nodes if x["stage"] == stage)


def test_model_claims_only_structurally_consistent():
    plan, nodes = fixture()
    result = assess(plan, nodes)
    assert result["verdict"] == "SOURCE_CLAIM_GRAPH_FOR_OWNER_REVIEW"
    assert result["compared_stages"] == 9
    assert result["source_content_consistent"] is True
    for key in (
        "external_attestation_verified", "actual_runtime_proven",
        "training_quality_proven", "deployment_authorized",
        "publication_authorized", "production_qualified",
    ):
        assert result[key] is False


def test_edge_service_profile_is_distinct_and_conservative():
    plan, nodes = fixture("edge_service")
    result = assess(plan, nodes)
    assert result["verdict"] == "SOURCE_CLAIM_GRAPH_FOR_OWNER_REVIEW"
    assert result["compared_stages"] == 6
    assert result["production_qualified"] is False


def test_missing_stage_does_not_silently_shrink_population():
    plan, nodes = fixture()
    nodes.pop()
    assert assess(plan, nodes)["reason"] == "STAGE_POPULATION_INCOMPLETE"


def test_duplicate_or_unknown_stage_cannot_count_as_coverage():
    plan, nodes = fixture()
    nodes[1]["stage"] = nodes[0]["stage"]
    assert assess(plan, nodes)["reason"] == "NODE_STAGE_DUPLICATE_OR_UNKNOWN"
    plan, nodes = fixture()
    nodes[1]["stage"] = "stage-added-by-agent"
    assert assess(plan, nodes)["reason"] == "NODE_STAGE_DUPLICATE_OR_UNKNOWN"


def test_unexpected_schema_field_is_refused():
    plan, nodes = fixture()
    nodes[0]["force_release"] = True
    assert assess(plan, nodes)["reason"] == "NODE_SCHEMA_INVALID"
    plan, nodes = fixture()
    plan["emergency_bypass"] = True
    assert assess(plan, nodes)["reason"] == "PLAN_SCHEMA_INVALID"


def test_auth_denial_and_rate_limit_are_stop_not_retry():
    for code in (401, 403, 429):
        plan, nodes = fixture()
        node_at(nodes, "provider")["access_status"] = code
        result = assess(plan, nodes)
        assert result["reason"] == "ACCESS_DENIAL_OR_RATE_LIMIT_STOP"
        assert result["stage"] == "provider"


def test_http_success_not_a_substitute_for_runtime_evidence():
    plan, nodes = fixture()
    node_at(nodes, "provider")["claims"]["instances"] = []
    assert assess(plan, nodes)["reason"] == "PROVIDER_INSTANCE_LIST_MISMATCH"


def test_image_digest_must_match_deployed_instance():
    plan, nodes = fixture()
    node_at(nodes, "provider")["claims"]["instances"][0][
        "image_digest"
    ] = "f" * 64
    assert (
        assess(plan, nodes)["reason"]
        == "PROVIDER_INSTANCE_IDENTITY_OR_IMAGE_MISMATCH"
    )


def test_duplicate_instances_refused_even_if_group_claims_running():
    plan, nodes = fixture()
    p = node_at(nodes, "provider")["claims"]
    p["desired_replicas"] = 2
    p["running_instances"] = 2
    p["instances"].append(deepcopy(p["instances"][0]))
    assert (
        assess(plan, nodes)["reason"]
        == "PROVIDER_INSTANCE_IDENTITY_OR_IMAGE_MISMATCH"
    )


def test_running_and_desired_counts_not_compatible():
    plan, nodes = fixture()
    node_at(nodes, "provider")["claims"]["desired_replicas"] = 2
    assert assess(plan, nodes)["reason"] == "PROVIDER_INSTANCES_UNVERIFIED"


def test_pending_update_denies_unstable_runtime():
    plan, nodes = fixture()
    node_at(nodes, "provider")["claims"]["pending_change"] = True
    assert assess(plan, nodes)["reason"] == "PROVIDER_INSTANCES_UNVERIFIED"


def test_provider_runtime_readback_expires():
    plan, nodes = fixture()
    node_at(nodes, "provider")["observed_at_utc"] = "2026-11-20T02:40:00Z"
    result = assess(plan, nodes)
    assert result["reason"] == "RUNTIME_READBACK_STALE"
    assert result["stage"] == "provider"


def test_serving_runtime_readback_expires():
    plan, nodes = fixture("edge_service")
    node_at(nodes, "serving")["observed_at_utc"] = "2026-11-20T02:40:00Z"
    assert assess(plan, nodes)["reason"] == "RUNTIME_READBACK_STALE"


def test_future_or_unknown_clock_is_hold():
    plan, nodes = fixture()
    assert assess(plan, nodes, now="local-wall-clock")["reason"] == "CLOCK_UNOBSERVED"
    node_at(nodes, "provider")["observed_at_utc"] = "2026-11-20T03:02:00Z"
    assert assess(plan, nodes)["reason"] == "STAGE_CLOCK_UNOBSERVED"


def test_wrong_parent_hash_cannot_be_explained_by_a_green_ci():
    plan, nodes = fixture()
    node_at(nodes, "image")["parents"]["ci"] = "f" * 64
    assert assess(plan, nodes)["reason"] == "EVIDENCE_GRAPH_EDGE_MISMATCH"


def test_wrong_upstream_source_revision_denies_build():
    plan, nodes = fixture()
    node_at(nodes, "image")["bindings"]["source_revision"] = "f" * 40
    assert assess(plan, nodes)["reason"] == "STAGE_RELEASE_BINDING_MISMATCH"


def test_fabricated_extra_signoff_not_accepted():
    plan, nodes = fixture()
    node_at(nodes, "publication")["claims"]["manager_approved"] = True
    assert assess(plan, nodes)["reason"] == "PUBLICATION_CLAIMS_UNVERIFIED"


def test_source_not_reviewed_is_hold():
    plan, nodes = fixture()
    node_at(nodes, "source")["claims"]["protected_reviewed_source"] = False
    assert assess(plan, nodes)["reason"] == "SOURCE_REVIEW_UNVERIFIED"


def test_integer_one_does_not_count_as_protected_source_review():
    plan, nodes = fixture()
    node_at(nodes, "source")["claims"]["protected_reviewed_source"] = 1
    assert assess(plan, nodes)["reason"] == "SOURCE_REVIEW_UNVERIFIED"


def test_integer_one_does_not_count_as_independent_backup():
    plan, nodes = fixture()
    node_at(nodes, "backup")["claims"]["independent_storage_readback"] = 1
    assert assess(plan, nodes)["reason"] == "INDEPENDENT_BACKUP_UNVERIFIED"


def test_ci_skipped_qualification_cannot_be_green():
    plan, nodes = fixture()
    node_at(nodes, "ci")["claims"]["qualification_skips"] = 1
    assert assess(plan, nodes)["reason"] == "CI_INCOMPLETE_OR_SKIPPED"


def test_ci_count_boolean_and_missing_check_are_rejected():
    plan, nodes = fixture()
    node_at(nodes, "ci")["claims"]["passed"] = True
    assert assess(plan, nodes)["reason"] == "CI_INCOMPLETE_OR_SKIPPED"
    plan, nodes = fixture()
    node_at(nodes, "ci")["claims"]["passed"] = 4
    assert assess(plan, nodes)["reason"] == "CI_INCOMPLETE_OR_SKIPPED"


def test_image_not_signed_by_trusted_builder_is_hold():
    plan, nodes = fixture()
    node_at(nodes, "image")["claims"]["builder_identity_checked"] = False
    assert assess(plan, nodes)["reason"] == "SIGNED_IMAGE_UNVERIFIED"


def test_checkpoint_filename_alone_not_resume_proof():
    plan, nodes = fixture()
    node_at(nodes, "checkpoint")["claims"][
        "full_optimizer_rng_scheduler"
    ] = False
    assert assess(plan, nodes)["reason"] == "RESUMABLE_CHECKPOINT_UNVERIFIED"


def test_checkpoint_step_not_terminal_is_hold():
    plan, nodes = fixture()
    node_at(nodes, "checkpoint")["claims"]["global_step"] = 119
    assert assess(plan, nodes)["reason"] == "RESUMABLE_CHECKPOINT_UNVERIFIED"


def test_checkpoint_step_boolean_is_invalid():
    plan, nodes = fixture()
    node_at(nodes, "checkpoint")["claims"]["global_step"] = True
    assert assess(plan, nodes)["reason"] == "RESUMABLE_CHECKPOINT_UNVERIFIED"


def test_backup_requires_independent_byte_readback():
    plan, nodes = fixture()
    node_at(nodes, "backup")["claims"]["matching_checkpoint_bytes"] = False
    assert assess(plan, nodes)["reason"] == "INDEPENDENT_BACKUP_UNVERIFIED"


def test_negative_controls_can_block_high_accuracy():
    plan, nodes = fixture()
    node_at(nodes, "evaluation")["claims"]["failed_negative_controls"] = 1
    assert assess(plan, nodes)["reason"] == "HELDOUT_QUALITY_UNVERIFIED"


def test_failed_quality_floor_is_hold():
    plan, nodes = fixture()
    node_at(nodes, "evaluation")["claims"]["correct"] = 70
    assert assess(plan, nodes)["reason"] == "HELDOUT_QUALITY_UNVERIFIED"


def test_evaluation_attempt_count_not_vacuous():
    plan, nodes = fixture()
    node_at(nodes, "evaluation")["claims"]["attempted"] = 0
    assert assess(plan, nodes)["reason"] == "HELDOUT_QUALITY_UNVERIFIED"


def test_serving_tenant_negative_control_is_mandatory():
    plan, nodes = fixture()
    node_at(nodes, "serving")["claims"]["tenant_boundary_negative_test"] = False
    assert assess(plan, nodes)["reason"] == "SERVING_SECURITY_OR_SOURCE_UNVERIFIED"


def test_uncertain_dispatch_must_not_replay_paid_or_mutating_request():
    plan, nodes = fixture()
    serving = node_at(nodes, "serving")["claims"]
    serving["uncertain_dispatch_replay_negative_test"] = False
    assert assess(plan, nodes)["reason"] == "SERVING_SECURITY_OR_SOURCE_UNVERIFIED"


def test_request_to_receipt_binding_required_even_with_healthy_http():
    plan, nodes = fixture("edge_service")
    serving = node_at(nodes, "serving")["claims"]
    serving["exact_request_receipt_binding"] = False
    assert assess(plan, nodes)["reason"] == "SERVING_SECURITY_OR_SOURCE_UNVERIFIED"


def test_public_card_cannot_omit_rights_or_denominators():
    for key in ("rights_reviewed", "claim_denominators_present"):
        plan, nodes = fixture()
        node_at(nodes, "publication")["claims"][key] = False
        assert assess(plan, nodes)["reason"] == "PUBLICATION_CLAIMS_UNVERIFIED"


def test_self_certified_or_missing_verifier_is_hold():
    plan, nodes = fixture()
    node_at(nodes, "evaluation")["verifier_digest"] = plan["proposer_digest"]
    assert (
        assess(plan, nodes)["reason"]
        == "ARTIFACT_OR_INDEPENDENCE_BINDING_UNVERIFIED"
    )


def test_source_artifact_and_expected_population_are_fixed():
    plan, nodes = fixture()
    node_at(nodes, "source")["artifact_sha256"] = "f" * 64
    assert (
        assess(plan, nodes)["reason"]
        == "ARTIFACT_OR_INDEPENDENCE_BINDING_UNVERIFIED"
    )
    plan, nodes = fixture()
    del plan["expected_artifacts"]["publication"]
    assert assess(plan, nodes)["reason"] == "EXPECTED_ARTIFACT_SET_INVALID"


def test_context_profile_is_not_a_malleable_authority_override():
    plan, nodes = fixture()
    plan["profile"] = "anything"
    assert assess(plan, nodes)["reason"] == "PROFILE_INVALID"
    plan, nodes = fixture("edge_service")
    plan["minimum_correct_cases"] = 1
    assert assess(plan, nodes)["reason"] == "UNSCOPED_EVALUATION_POLICY"


def test_different_inputs_produce_no_secret_echo_and_no_mutation():
    plan, nodes = fixture()
    p0, n0 = deepcopy(plan), deepcopy(nodes)
    result = assess(plan, nodes)
    assert (plan, nodes) == (p0, n0)
    assert "private" not in str(result).lower()
    assert nodes[0]["evidence_sha256"] not in str(result)


def test_negative_stage_cannot_be_overridden_by_agent():
    plan, nodes = fixture()
    node_at(nodes, "publication")["state"] = "FAIL"
    assert assess(plan, nodes)["reason"] == "STAGE_NOT_PROVED"
