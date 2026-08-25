"""The model-kind heuristic against the artifact generations that actually exist."""

from agent.schemas.deployments import detect_model_kind


def test_classic_with_profile_is_ml_whatever_the_variant() -> None:
    profile = {"profile_status": "ready", "feature_summaries": {"numerical_features": {"x": {}}}}
    assert detect_model_kind({"variant": "pyfunc"}, profile) == "ml"
    assert detect_model_kind({"variant": "default"}, profile) == "ml"


def test_default_variant_without_profile_is_ml() -> None:
    assert detect_model_kind({"variant": "default"}, None) == "ml"


def test_early_sklearn_pyfunc_is_ml_not_llm() -> None:
    # The February experiment packaging: pyfunc wrapper, no profile, sklearn named
    # in the producer tags — a classic model in an LLM-shaped coat.
    manifest = {"variant": "pyfunc", "producer_tags": ["luml.ai::sklearn:v1"]}
    assert detect_model_kind(manifest, None) == "ml"


def test_pyfunc_without_profile_or_classic_tags_is_llm() -> None:
    manifest = {"variant": "pyfunc", "producer_tags": ["lisa.ai::llm_router:v1"]}
    assert detect_model_kind(manifest, None) == "llm"


def test_missing_manifest_defaults_to_ml() -> None:
    assert detect_model_kind(None, None) == "ml"
    assert detect_model_kind({}, None) == "ml"


def test_placeholder_profile_does_not_count_as_a_baseline() -> None:
    manifest = {"variant": "pyfunc", "producer_tags": ["lisa.ai::llm_router:v1"]}
    assert detect_model_kind(manifest, {"profile_status": "placeholder"}) == "llm"
