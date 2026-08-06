"""CityCare Clinic FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers.auth_controller import seed_doctor_if_missing
from app.core.config import get_settings
from app.core.database import close_mongo_connection, connect_to_mongo, ensure_indexes
from app.routes import appointment_routes, auth_routes, doctor_routes
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logger.info("Starting CityCare Clinic API…")
    await connect_to_mongo()
    await ensure_indexes()
    await seed_doctor_if_missing()
    logger.info(
        "Startup complete. CORS origins=%s DB=%s",
        settings.cors_origins_list,
        settings.mongodb_db_name,
    )
    yield
    await close_mongo_connection()
    logger.info("CityCare Clinic API shut down.")


app = FastAPI(
    title="CityCare Clinic API",
    description=(
        "Single-doctor appointment booking for CityCare Clinic, Dharampeth, Nagpur. "
        "JWT auth with patient/doctor roles. No double-booking via partial unique index."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(doctor_routes.router)
app.include_router(appointment_routes.router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "CityCare Clinic API"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )
