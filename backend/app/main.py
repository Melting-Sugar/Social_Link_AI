import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    auth,
    conversations,
    recordings,
    records,
    statement_check,
    users,
    voice_profile,
)
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title="Social Link AI API")

# §5: frontend/backend are separate origins; refresh-token cookie needs
# credentials allowed and an explicit (not wildcard) origin list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(voice_profile.router)
app.include_router(conversations.router)
app.include_router(recordings.router)
app.include_router(records.router)
app.include_router(statement_check.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # §11.7: every expected failure mode already raises HTTPException with
    # a specific message at the point it happens — this is the safety net
    # for anything that wasn't anticipated, kept generic on purpose so we
    # never leak internals to the client.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "予期しないエラーが発生しました。しばらくしてからもう一度お試しください。"},
    )
