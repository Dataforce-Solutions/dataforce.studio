class AuthError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class OrganizationLimitReachedError(Exception):
    def __init__(
        self, message: str = "Organization reached limits", status_code: int = 409
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)
