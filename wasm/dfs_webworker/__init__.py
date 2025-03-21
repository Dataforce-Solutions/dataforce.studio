from dfs_webworker.tabular import tabular_deallocate, tabular_predict, tabular_train
from dfs_webworker.types import FakeJsProxy


class Router:
    sync_routes = {}
    async_routes = {}

    @classmethod
    def add_route(cls, route, func, sync=True):
        if sync:
            cls.sync_routes[route] = func
        else:
            cls.async_routes[route] = func


Router.add_route("/tabular/train", tabular_train, sync=True)
Router.add_route("/tabular/predict", tabular_predict, sync=True)
Router.add_route("/tabular/deallocate", tabular_deallocate, sync=True)


async def invoke(route: str, payload: FakeJsProxy):
    try:
        unwrapped_payload = payload.to_py()
        if route in Router.sync_routes:
            return Router.sync_routes[route](**unwrapped_payload)
        elif route in Router.async_routes:
            return await Router.async_routes[route](**unwrapped_payload)
        raise ValueError(f"Route {route} not found")
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error_message": str(e),
        }


def ping():
    return "it works!"
