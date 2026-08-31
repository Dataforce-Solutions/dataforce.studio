from uuid import UUID

import pytest

from agent.agent_api import _deployment_descriptor
from agent.handlers.handler_instances import ms_handler
from agent.schemas import LocalDeployment
from agent.schemas.deployments import detect_model_kind
from agent.schemas.monitoring_query import ProfileStatus


@pytest.mark.parametrize(
    ("manifest", "expected"),
    [
        ({"producer_tags": ["luml.ai::kind_tabular:v1"]}, "tabular"),
        ({"producer_tags": ["luml.ai::kind_llm:v1"]}, "llm"),
        ({"variant": "pyfunc", "producer_tags": []}, "unknown"),
        (None, "unknown"),
    ],
)
def test_model_kind_comes_only_from_manifest_tags(
    manifest: dict[str, object] | None, expected: str
) -> None:
    assert detect_model_kind(manifest) == expected


def test_profile_and_framework_tags_do_not_imply_model_kind() -> None:
    manifest = {
        "variant": "pyfunc",
        "producer_tags": ["luml.ai::sklearn:v1", "luml.ai::tabular_monitoring:v1"],
    }

    assert detect_model_kind(manifest) == "unknown"


def test_unknown_kind_tag_version_does_not_imply_model_kind() -> None:
    assert detect_model_kind({"producer_tags": ["luml.ai::kind_tabular:v9"]}) == "unknown"


@pytest.mark.parametrize(
    ("manifest", "profile", "expected"),
    [
        ({"producer_tags": ["luml.ai::kind_tabular:v1"]}, None, "tabular"),
        ({"producer_tags": ["luml.ai::kind_llm:v1"]}, None, "llm"),
        (
            {"variant": "pyfunc", "producer_tags": []},
            {
                "profile_status": "ready",
                "feature_summaries": {"numerical_features": {"age": {}}},
            },
            "unknown",
        ),
    ],
)
def test_header_descriptor_uses_only_manifest_kind_tags(
    monkeypatch: pytest.MonkeyPatch,
    manifest: dict[str, object],
    profile: dict[str, object] | None,
    expected: str,
) -> None:
    deployment_id = "019f46e3-3aa1-7672-96a9-8c6d98ab25cd"
    monkeypatch.setitem(
        ms_handler.deployments,
        deployment_id,
        LocalDeployment(
            deployment_id=deployment_id,
            manifest=manifest,
            reference_profile=profile,
            profile_status=(ProfileStatus.READY if profile else ProfileStatus.ABSENT),
        ),
    )

    descriptor = _deployment_descriptor(UUID(deployment_id))

    assert descriptor is not None
    assert descriptor["model_kind"] == expected
