"""Auth routes — thin layer over controllers."""

from fastapi import APIRouter

from app.controllers import auth_controller
from app.schemas.user_schema import LoginRequest, SignupRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=UserOut, status_code=201)
async def signup(payload: SignupRequest):
    """Register a new patient. Role is always patient regardless of request body."""
    return await auth_controller.signup(payload)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    """Login and receive a JWT access token (expires in 1 hour)."""
    return await auth_controller.login(payload)
