"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.core.config import get_settings
from app.db.database import init_db
from app.services.intent_service import get_intent_metrics, reset_intent_classifier
from app.services.retrieval_service import get_vector_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup and clean up on shutdown."""
    logger.info("Starting %s", settings.app_name)
    init_db()
    vector_store = get_vector_store()
    logger.info("Vector store ready with %s indexed chunks", vector_store.index.ntotal)

    metrics = get_intent_metrics()
    if metrics:
        logger.info(
            "Intent classifier metrics loaded | examples=%s accuracy=%.3f",
            metrics["training_examples"],
            metrics["accuracy"],
        )
    else:
        logger.warning("Intent classifier not trained yet. Run: python -m app.ml.train_model")
    reset_intent_classifier()
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Student Assistance Chatbot API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Return safe error messages without exposing internal stack traces."""
    logger.exception("Unhandled application error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring and Phase 1 verification."""
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    """Root endpoint with basic API information."""
    return {
        "message": settings.app_name,
        "docs": "/docs",
        "health": "/health",
    }
