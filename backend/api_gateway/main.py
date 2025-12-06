"""API Gateway - Main entry point."""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import httpx
from shared.config.settings import settings
from shared.db.redis_client import redis_client
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for FastAPI app."""
    # Startup
    await redis_client.connect()
    logger.info("API Gateway started")
    yield
    # Shutdown
    await redis_client.disconnect()
    logger.info("API Gateway stopped")


app = FastAPI(
    title="Intervieu API Gateway",
    description="API Gateway for Intervieu microservices",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""
    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)
    
    # Get user ID from token if available
    user_id = None
    auth_header = request.headers.get("authorization")
    if auth_header:
        try:
            # Simple token extraction (full verification happens in services)
            from firebase_admin import auth
            token = auth_header.split(" ")[-1] if " " in auth_header else auth_header
            decoded = auth.verify_id_token(token)
            user_id = decoded.get("uid")
        except:
            # Use IP as fallback for unauthenticated requests
            user_id = request.client.host if request.client else "unknown"
    
    if user_id:
        key = f"rate_limit:{user_id}"
        try:
            current = await redis_client.get(key)
            if current:
                try:
                    current_count = int(current) if isinstance(current, (str, int)) else 0
                    if current_count >= settings.RATE_LIMIT_PER_MINUTE:
                        return JSONResponse(
                            status_code=429,
                            content={"error": "Rate limit exceeded"}
                        )
                except (ValueError, TypeError):
                    pass
            await redis_client.increment(key)
            await redis_client.set_expire(key, 60)
        except Exception as e:
            # If Redis is unavailable, log but don't block requests
            logger.warning(f"Rate limiting unavailable: {e}")
    
    response = await call_next(request)
    return response


# Service routing
@app.api_route("/api/users/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_users(request: Request, path: str):
    """Proxy requests to user-service."""
    async with httpx.AsyncClient() as client:
        url = f"{settings.USER_SERVICE_URL}/api/users/{path}"
        headers = dict(request.headers)
        # Remove host header to avoid issues
        headers.pop("host", None)
        
        try:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body(),
                timeout=30.0,
            )
            # Handle different response types
            if response.headers.get("content-type", "").startswith("application/json"):
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                )
            else:
                from fastapi.responses import Response
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
        except Exception as e:
            logger.error(f"Error proxying to user-service: {e}")
            raise HTTPException(status_code=502, detail="User service unavailable")


@app.api_route("/api/interviews/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_interviews(request: Request, path: str):
    """Proxy requests to interview-service."""
    async with httpx.AsyncClient() as client:
        url = f"{settings.INTERVIEW_SERVICE_URL}/api/interviews/{path}"
        headers = dict(request.headers)
        headers.pop("host", None)
        
        try:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body(),
                timeout=30.0,
            )
            if response.headers.get("content-type", "").startswith("application/json"):
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                )
            else:
                from fastapi.responses import Response
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
        except Exception as e:
            logger.error(f"Error proxying to interview-service: {e}")
            raise HTTPException(status_code=502, detail="Interview service unavailable")


@app.api_route("/api/reports/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_reports(request: Request, path: str):
    """Proxy requests to report-service."""
    async with httpx.AsyncClient() as client:
        url = f"{settings.REPORT_SERVICE_URL}/api/reports/{path}"
        headers = dict(request.headers)
        headers.pop("host", None)
        
        try:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body(),
                timeout=30.0,
            )
            if response.headers.get("content-type", "").startswith("application/json"):
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                )
            else:
                from fastapi.responses import Response
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
        except Exception as e:
            logger.error(f"Error proxying to report-service: {e}")
            raise HTTPException(status_code=502, detail="Report service unavailable")


@app.api_route("/api/analytics/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_analytics(request: Request, path: str):
    """Proxy requests to analytics-service."""
    async with httpx.AsyncClient() as client:
        url = f"{settings.ANALYTICS_SERVICE_URL}/api/analytics/{path}"
        headers = dict(request.headers)
        headers.pop("host", None)
        
        try:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body(),
                timeout=30.0,
            )
            if response.headers.get("content-type", "").startswith("application/json"):
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                )
            else:
                from fastapi.responses import Response
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
        except Exception as e:
            logger.error(f"Error proxying to analytics-service: {e}")
            raise HTTPException(status_code=502, detail="Analytics service unavailable")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "api-gateway"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_GATEWAY_HOST,
        port=settings.API_GATEWAY_PORT,
        reload=True,
    )