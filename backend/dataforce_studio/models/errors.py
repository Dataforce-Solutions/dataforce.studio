

class OrganizationNotFoundError(Exception):
    def __init__(
        self, message: str = "Organization not found", status_code: int = 404
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)
