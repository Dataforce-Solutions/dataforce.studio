from lumlflow.flow.store.models import JsonValue


class DaemonRpcError(RuntimeError):
    def __init__(self, code: int, message: str, data: JsonValue = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data
