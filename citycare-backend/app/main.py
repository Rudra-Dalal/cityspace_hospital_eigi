"""CityCare — Multi-Tenant Hospital Platform API entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers.auth_controller import seed_doctor_if_missing
from app.core.config import get_settings
from app.core.database import close_mongo_connection, connect_to_mongo, ensure_indexes
from app.core.migrate import run_migrations
from app.routes import appointment_routes, auth_routes, doctor_routes, patient_routes
from app.routes import admin_routes, manager_routes, ai_routes, prescription_routes, patient_ai_routes, voice_routes
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logger.info("Starting CityCare Hospital Platform API…")
    await connect_to_mongo()
    await ensure_indexes()
    await seed_doctor_if_missing()   # seeds doctor + super_admin accounts
    await run_migrations()           # idempotent data migrations
    logger.info(
        "Startup complete. CORS origins=%s DB=%s",
        settings.cors_origins_list,
        settings.mongodb_db_name,
    )
    yield
    await close_mongo_connection()
    logger.info("CityCare Hospital Platform API shut down.")


app = FastAPI(
    title="CityCare Hospital Platform API",
    description=(
        "Multi-tenant hospital appointment booking platform. "
        "Roles: super_admin | hospital_manager | doctor | customer. "
        "JWT auth with hospital-scoped RBAC."
    ),
    version="2.0.0",
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

# Patient discovery and core routes
app.include_router(patient_routes.router)
app.include_router(auth_routes.router)
app.include_router(doctor_routes.router)
app.include_router(appointment_routes.router)

# Multi-tenant and clinical routes
app.include_router(admin_routes.router)
app.include_router(manager_routes.router)
app.include_router(ai_routes.router)
app.include_router(prescription_routes.router)
app.include_router(patient_ai_routes.router)
app.include_router(voice_routes.router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "CityCare Hospital Platform API", "version": "2.0.0"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )
