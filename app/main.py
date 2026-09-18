import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.routes import audit, auth, executions, health, organizations, secrets, webhooks, workflows
from app.core.config import settings
from app.observability.metrics import HTTP_LATENCY, HTTP_REQUESTS

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Multi-tenant workflow automation platform with durable background execution, "
        "versioned DAGs, RBAC, idempotent webhooks and observability."
    ),
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    route_path = request.scope.get("route").path if request.scope.get("route") else request.url.path
    HTTP_REQUESTS.labels(request.method, route_path, response.status_code).inc()
    HTTP_LATENCY.labels(request.method, route_path).observe(elapsed)
    return response


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(executions.router, prefix="/api/v1")
app.include_router(secrets.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
