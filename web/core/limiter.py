import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# We use the same redis instance which is used to store build metadata
# and other cached data. To keep that data separate, we use db-1 of the
# redis instance instead of the default db-0.
REDIS_DB_NUMBER = 1
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"redis://{settings.redis_host}:{settings.redis_port}/{REDIS_DB_NUMBER}",
    strategy="fixed-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Response to send when a rate limit is exception is raised
    """
    response = JSONResponse(
        {"detail": "Too many requests. Try again after some time."},
        status_code=429
    )
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return response
