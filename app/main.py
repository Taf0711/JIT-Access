from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import logging

from app.config import settings
from app.api import requests as requests_api
from app.api import grants as grants_api
from app.api import tokens as tokens_api
from app.api import protected as protected_api
from app.api import break_glass as break_glass_api
from app.api import audit as audit_api
from app.api import resources as resources_api
from app.middleware.gateway import gateway_auth_middleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="JIT Access & Policy Gateway",
    description="Just-In-Time Access Management System with Policy Enforcement",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Metrics middleware (must be first to capture all requests)
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    from app.services.metrics import metrics_service
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # Extract endpoint pattern (remove query params and IDs)
    path = request.url.path
    endpoint = path
    for part in path.split('/'):
        if part.isdigit():
            endpoint = endpoint.replace(part, '{id}')
    
    # Record metrics
    metrics_service.record_http_request(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code,
        duration=duration
    )
    
    return response


# Gateway auth middleware (must be before timing middleware)
@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    return await gateway_auth_middleware(request, call_next)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Health check endpoints
@app.get("/health", tags=["Health"])
def health_check():
    """Basic health check"""
    return {"status": "healthy", "service": "jit-access"}


@app.get("/health/ready", tags=["Health"])
def readiness_check():
    """Readiness check - verify database connectivity"""
    try:
        from app.db import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "error": str(e)}
        )


# Include API routers
app.include_router(resources_api.router, prefix=settings.API_V1_PREFIX)
app.include_router(requests_api.router, prefix=settings.API_V1_PREFIX)
app.include_router(grants_api.router, prefix=settings.API_V1_PREFIX)
app.include_router(tokens_api.router, prefix=settings.API_V1_PREFIX)
app.include_router(break_glass_api.router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_api.router, prefix=settings.API_V1_PREFIX)
app.include_router(protected_api.router)  # Protected routes (no prefix)


# Metrics endpoint
@app.get("/metrics", tags=["Metrics"])
def metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Root endpoint
@app.get("/", tags=["Root"])
def root():
    return {
        "message": "JIT Access & Policy Gateway API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

