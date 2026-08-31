"""What the dashboard header knows about a deployment comes from the Platform record."""

from agent.schemas import DeploymentMetadata


class TestDeploymentMetadata:
    def test_metadata_carries_the_header_identity(self) -> None:
        metadata = DeploymentMetadata.from_platform(
            {
                "name": "insurance regression",
                "status": "active",
                "artifact_name": "insurance_regression_v2",
                "orbit_name": "Default Orbit",
                "satellite_name": "satellite",
                "inference_url": "/deployments/x",
            }
        )

        assert metadata.name == "insurance regression"
        # the orbit's name is what the header calls the environment
        assert metadata.environment == "Default Orbit"
        assert metadata.satellite == "satellite"

    def test_a_record_without_an_orbit_name_leaves_the_environment_empty(self) -> None:
        metadata = DeploymentMetadata.from_platform({"name": "x", "status": "active"})

        assert metadata.environment is None
