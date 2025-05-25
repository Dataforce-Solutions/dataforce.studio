from fastapi.openapi.utils import get_openapi

from dataforce_studio.service import AppService


def custom_openapi(app: AppService) -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Dataforce Studio API",
        version="1.0.0",
        description="API docs for Dataforce Studio",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema
