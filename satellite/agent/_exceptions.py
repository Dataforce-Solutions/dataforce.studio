class ContainerNotFoundError(Exception):
    def __init__(self, container_id: str) -> None:
        self.container_id = container_id
        super().__init__(f"Container '{container_id}' not found")


class ContainerNotRunningError(Exception):
    def __init__(self, container_id: str, current_status: str) -> None:
        self.container_id = container_id
        self.current_status = current_status
        super().__init__(f"Container '{container_id}' is not running (status: {current_status})")


class DeploymentNotHostedError(Exception):
    code: str = "deployment_not_hosted"
    detail: str = "Deployment not found on this Satellite"

    def __init__(self) -> None:
        super().__init__(self.detail)
