from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user
from app.core.rate_limit import limiter, AUTH_LIMIT
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserProfile
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()


# A5：登录/注册 20 次/分钟
@router.post("/register", response_model=AuthResponse)
@limiter.limit(AUTH_LIMIT)
def register(request: Request, body: RegisterRequest) -> dict:
    return auth_service.register(body.username, body.password)


@router.post("/login", response_model=AuthResponse)
@limiter.limit(AUTH_LIMIT)
def login(request: Request, body: LoginRequest) -> dict:
    return auth_service.login(body.username, body.password)


@router.get("/me", response_model=UserProfile)
def me(current_user: dict = Depends(get_current_user)) -> dict:
    return auth_service.get_public_user(current_user["id"])
