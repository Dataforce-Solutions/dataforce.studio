import uvicorn

from dataforce_studio.infra.exceptions import ServiceError
from dataforce_studio.infra.openapi import custom_openapi
from dataforce_studio.service import AppService
from fastapi import Request
from fastapi.responses import JSONResponse

app = AppService()

app.openapi = lambda: custom_openapi(app)


@app.exception_handler(ServiceError)
async def handle_service_error(request: Request, exc: ServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


if __name__ == "__main__":
    uvicorn.run("server:app")
