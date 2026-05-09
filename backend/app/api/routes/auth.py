from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserProfile
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()


@router.post("/register", response_model=AuthResponse)
def register(request: RegisterRequest) -> dict:
    return auth_service.register(request.username, request.password)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest) -> dict:
    return auth_service.login(request.username, request.password)


@router.get("/me", response_model=UserProfile)
def me(current_user: dict = Depends(get_current_user)) -> dict:
    return auth_service.get_public_user(current_user["id"])
