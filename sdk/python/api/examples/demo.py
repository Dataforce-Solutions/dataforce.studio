from luml_api import LumlClient
from luml_api._types import ArtifactStatus, CollectionType

# Will use LUML API Production url "https://api.luml.ai"
# And search for LUML_API_KEY in .env
luml_simple = LumlClient()

# No default organization, orbit and collection are set
luml_without_defaults = LumlClient(api_key="luml_your_api_key_here")

# Recommended initialization with default resources.
# Resources initialized by their names
luml_with_defaults_names = LumlClient(
    api_key="luml_your_api_key_here",
    organization="My Organization",
    orbit="Default Orbit",
    collection="Default Collection",
)

# Recommended initialization with default resources.
# Resources initialized by their ids
luml = LumlClient(
    api_key="luml_your_api_key_here",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75",
)


def demo_client_defaults() -> None:
    # Get client defaults ids
    default_organization_id = luml.organization
    default_orbit_id = luml.orbit
    default_collection_id = luml.collection

    print(default_organization_id, default_orbit_id, default_collection_id)

    # Set default resources
    luml.organization = "0199c455-21ec-7c74-8efe-41470e29bae5"
    luml.orbit = "0199c455-21ed-7aba-9fe5-5231611220de"
    luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"

    print(luml.organization, luml.orbit, luml.collection)


def demo_organizations() -> None:
    # List all available organization for user
    all_my_organization = luml.organizations.list()
    print(f"All user organization: {all_my_organization}")

    # Get default organization
    default_org_details = luml.organizations.get()
    print(f"Default organization: {default_org_details}")

    # Get organization by name
    organization_by_name = luml.organizations.get("My Organization")
    print(f"Organization by name: {organization_by_name}")

    # Get organization by id
    organization_by_id = luml.organizations.get("0199c455-21ec-7c74-8efe-41470e29bae5")
    print(f"Organization by id: {organization_by_id}")


def demo_bucket_secrets() -> None:
    # Create a new bucket secret
    bucket_secret = luml.bucket_secrets.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-ml-artifacts-bucket",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        secure=True,
        region="us-east-1",
    )
    print(f"Created bucket secret: {bucket_secret}")

    # List all bucket secrets
    secrets = luml.bucket_secrets.list()
    print(f"Bucket secrets: {secrets}")

    # Get bucket secret by name
    secret = luml.bucket_secrets.get("my-ml-artifacts-bucket")
    print(f"Bucket secret by name: {secret}")

    # Get bucket secret by id
    secret = luml.bucket_secrets.get("0199c455-21ed-7aba-9fe5-5231611220de")
    print(f"Bucket secret by id: {secret}")

    # Update bucket secret
    updated_secret = luml.bucket_secrets.update(
        secret_id=bucket_secret.id, secure=False, region="us-west-2"
    )
    print(f"Updated bucket secret: {updated_secret}")

    # Delete bucket secret
    luml.bucket_secrets.delete("0199c455-21ed-7aba-9fe5-5231611220de")


def demo_orbits() -> None:
    # Create a new orbit
    orbit = luml.orbits.create(
        name="ML Production Orbit",
        bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    print(f"Created orbit: {orbit}")

    # Get Orbit by name
    orbit_by_name = luml.orbits.get("ML Production Orbit")
    print(f"Orbit by name: {orbit_by_name}")

    # Get Orbit by id
    orbit_by_id = luml.orbits.get("0199c455-21ed-7aba-9fe5-5231611220de")
    print(f"Orbit by id: {orbit_by_id}")

    # List all orbits
    orbits = luml.orbits.list()
    print(f"Orbits: {orbits}")

    # Update orbit
    updated_orbit = luml.orbits.update(name="ML Production Environment")
    print(f"Updated orbit: {updated_orbit}")

    # Delete Orbit
    luml.orbits.delete("0199c455-21ed-7aba-9fe5-5231611220de")


def demo_collections() -> None:
    # Create a artifact collection
    collection = luml.collections.create(
        name="Production artifacts",
        description="Trained artifacts ready for production deployment",
        type=CollectionType.MODEL,
        tags=["production", "ml", "artifacts"],
    )
    print(f"Created collection: {collection}")

    # Get default collection
    default_collection = luml.collections.get()
    print(f"Get Default Collection Details: {default_collection}")

    # Get collection by name
    collection_by_name = luml.collections.get("Production artifacts")
    print(f"Collection by name: {collection_by_name}")

    # Get collection by id
    collection_by_id = luml.collections.get("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"Collection by id: {collection_by_id}")

    # List all collections in the orbit
    collections = luml.collections.list()
    print(f"Collection: {collections}")

    # Update collection with new tags
    updated_collection = luml.collections.update(
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        description="Updated: Production-ready ML artifacts",
    )
    print(f"Updated collection: {updated_collection}")

    # Delete collection
    luml.collections.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")


def demo_artifacts() -> None:
    # Create new artifact artifact record with upload URL
    artifact_created = luml.artifacts.create(
        file_name="customer_churn_artifact.fnnx",
        extra_values={"accuracy": 0.95, "precision": 0.92, "recall": 0.88},
        manifest={"version": "1.0", "framework": "xgboost"},
        file_hash="abc123def456",
        file_index={"layer1": (0, 1024), "layer2": (1024, 2048)},
        size=1048576,
        name="Customer Churn Predictor",
        description="XGBoost artifact predicting customer churn probability",
        tags=["xgboost", "churn", "production"],
    )
    print(f"Created artifact: {artifact_created}")

    # List all artifact artifacts in the collection
    artifacts = luml.artifacts.list()
    print(f"All artifacts in collection: {artifacts}")

    # Get artifact by ID
    artifact_by_id = luml.artifacts.get("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"artifact by id: {artifact_by_id}")

    # Get artifact by name
    artifact_by_name = luml.artifacts.get("Customer Churn Predictor")
    print(f"artifact by name: {artifact_by_name}")

    # Get artifact from specific collection
    artifact_by_id_collection = luml.artifacts.get(
        "0199c455-21ee-74c6-b747-19a82f1a1e75",
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    )
    print(f"artifact by id: {artifact_by_id_collection}")

    # Update artifact metadata
    updated_artifact = luml.artifacts.update(
        artifact_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        description="Updated: Advanced churn prediction artifact",
        tags=["xgboost", "churn", "production", "v2.1"],
        status=ArtifactStatus.UPLOADED,
    )
    print(f"Updated artifact: {updated_artifact}")

    # Get download URL
    download_url = luml.artifacts.download_url("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"artifact Download URL: {download_url}")

    # Get delete URL
    delete_url = luml.artifacts.delete_url("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"artifact Delete URL: {delete_url}")

    # Upload a artifact file (example - file should exist)
    uploaded_artifact = luml.artifacts.upload(
        file_path="/path/to/your/artifact.dfs",
        name="Customer Churn Predictor",
        description="XGBoost artifact predicting customer churn probability",
        tags=["xgboost", "churn", "production"],
    )
    print(f"Uploaded artifact: {uploaded_artifact}")

    # Download artifact
    luml.artifacts.download("0199c455-21ee-74c6-b747-19a82f1a1e75", "output.dfs")

    # Delete artifact permanently
    luml.artifacts.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")


def demo_deployments() -> None:
    # List all deployments in the default orbit, with their monitoring mode
    all_deployments = luml.deployments.list()
    print(f"All deployments: {all_deployments}")

    # Get deployment by name
    deployment_by_name = luml.deployments.get("My Deployment")
    print(f"Deployment by name: {deployment_by_name}")

    # Get deployment by id
    deployment_by_id = luml.deployments.get("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"Deployment by id: {deployment_by_id}")


def demo_monitoring() -> None:
    # Monitoring sections of one deployment, read from its Satellite directly.
    # The Satellite's address is resolved from the deployment record itself,
    # so the name or id of the deployment is all it takes.
    monitoring = luml.deployments.monitoring("My Deployment")

    # Identity of the deployment as the dashboard header shows it
    header = monitoring.header()
    print(f"Header: {header}")

    # Status cards, alert banners, runtime series and top drifted features
    overview = monitoring.overview(window="7d")
    print(f"Overview: {overview}")

    # Request counts, error rate, latency percentiles and the outcome breakdown
    runtime = monitoring.runtime(window="24h")
    print(f"Runtime: {runtime}")

    # Per-feature validity checks; pass feature= for one feature's trends
    data_quality = monitoring.data_quality(feature="age")
    print(f"Data quality: {data_quality}")

    # PSI ranking, distributions, and the multivariate panel
    feature_drift = monitoring.feature_drift(severity="critical")
    print(f"Feature drift: {feature_drift}")

    # Did the model's outputs shift against the training reference
    output_drift = monitoring.output_drift(window="7d")
    print(f"Output drift: {output_drift}")

    # The profile the deployment is compared against
    reference_profile = monitoring.reference_profile()
    print(f"Reference profile: {reference_profile}")

    # Open and acknowledged alerts, grouped by metric family
    alerts = monitoring.alerts(window="7d", severity="critical")
    print(f"Alerts: {alerts}")

    # The local request log: one row per inference call
    traces = monitoring.traces(limit=20)
    print(f"Traces: {traces}")

    slowest = monitoring.traces(sort="latency", order="desc", limit=5)
    print(f"Slowest calls: {slowest}")

    # One call with its full payloads and span tree
    trace = monitoring.trace("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"Trace: {trace}")

    # Whether monitoring itself is keeping up — not a metric about the model
    worker = monitoring.worker()
    print(f"Worker health: {worker}")


if __name__ == "__main__":
    print("\n--------------------------------\n")
    demo_client_defaults()
    print("\n--------------------------------\n")
    demo_organizations()
    print("\n--------------------------------\n")
    demo_bucket_secrets()
    print("\n--------------------------------\n")
    demo_orbits()
    print("\n--------------------------------\n")
    demo_collections()
    print("\n--------------------------------\n")
    demo_artifacts()
    print("\n--------------------------------\n")
    demo_deployments()
    print("\n--------------------------------\n")
    demo_monitoring()
