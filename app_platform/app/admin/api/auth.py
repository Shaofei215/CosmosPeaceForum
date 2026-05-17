from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app_platform.app.admin.api.deps import get_current_admin
from app_platform.app.admin.models.admin_user import PlatformAdminUser
from app_platform.app.admin.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminProfileUpdateRequest,
    AdminResponse,
)
from app_platform.app.admin.services import auth_service
from app_platform.app.api.deps import get_db

router = APIRouter(prefix="/auth", tags=["platform-admin-auth"])


@router.post("/login", response_model=AdminLoginResponse)
async def login(request: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = auth_service.authenticate_admin(db, request.username, request.password)
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    auth_service.update_last_login(db, admin)
    db.refresh(admin)
    return AdminLoginResponse(
        access_token=auth_service.create_admin_token(admin),
        admin=auth_service.admin_to_response(admin),
    )


@router.get("/me", response_model=AdminResponse)
async def me(current_admin: PlatformAdminUser = Depends(get_current_admin)):
    return auth_service.admin_to_response(current_admin)


@router.put("/profile", response_model=AdminResponse)
async def update_profile(
    request: AdminProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(get_current_admin),
):
    try:
        admin = auth_service.update_profile(db, current_admin, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return auth_service.admin_to_response(admin)

