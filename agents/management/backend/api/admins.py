"""Management Backend - 管理员管理路由"""

from datetime import datetime
from agents.management.backend.core.timezone import local_now

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from agents.management.backend.api.deps import require_permission
from agents.management.backend.core.database import get_db
from agents.management.backend.core.security import get_password_hash
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.models.admin_session import AdminSession
from agents.management.backend.schemas import (
    AdminCreateRequest,
    AdminListResponse,
    AdminUpdateRequest,
    AdminUserResponse,
)
from agents.management.backend.services import auth_service
from agents.management.backend.services.log_service import create_log
from agents.management.backend.services.permissions import (
    PERMISSION_MANAGE_ADMINS,
    normalize_permissions,
)

router = APIRouter()


def _ensure_super_admin_boundary(
    current_admin: AdminUser,
    *,
    target_admin: AdminUser | None = None,
    requested_super_admin: bool | None = None,
) -> None:
    """阻止普通管理员创建、提升或修改超级管理员。

    Args:
        current_admin: 执行管理员管理操作的当前账号。
        target_admin: 更新或删除操作指向的现有管理员。
        requested_super_admin: 创建或更新请求中的超级管理员标记。

    Raises:
        HTTPException: 普通管理员试图触及超级管理员边界时抛出 403。
    """

    if current_admin.is_super_admin:
        return
    targets_super_admin = target_admin is not None and target_admin.is_super_admin
    if targets_super_admin or requested_super_admin is True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以创建或管理超级管理员",
        )


def _ensure_permission_delegation(
    current_admin: AdminUser,
    requested_permissions: list[str],
    *,
    existing_permissions: list[str] | None = None,
) -> None:
    """限制普通管理员只能变更自己已经拥有的权限。

    创建管理员时，所有待授予权限都必须属于操作者；更新管理员时，新增和撤销
    的权限差集都必须属于操作者，防止通过自己的账号或中间账号完成权限提升。

    Args:
        current_admin: 执行权限分配的当前管理员。
        requested_permissions: 请求保存到目标管理员的权限列表。
        existing_permissions: 目标管理员修改前的权限列表；创建时为空。

    Raises:
        HTTPException: 普通管理员试图变更自己不具备的权限时抛出 403。
    """

    if current_admin.is_super_admin:
        return

    operator_permissions = set(auth_service.parse_permissions(current_admin.permissions))
    requested = set(normalize_permissions(requested_permissions))
    existing = set(normalize_permissions(existing_permissions))
    unauthorized_changes = (requested ^ existing) - operator_permissions
    if unauthorized_changes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能授予或撤销当前账号不具备的权限",
        )


@router.get("/", response_model=AdminListResponse)
def list_admins(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    stmt = select(AdminUser)
    items = db.exec(
        stmt.order_by(AdminUser.created_at.desc()).offset(skip).limit(limit)
    ).all()
    total = len(db.exec(stmt).all())
    return AdminListResponse(
        items=[auth_service.admin_to_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    request: AdminCreateRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    _ensure_super_admin_boundary(
        current_admin,
        requested_super_admin=request.is_super_admin,
    )
    _ensure_permission_delegation(current_admin, request.permissions)

    if auth_service.get_admin_by_username(db, request.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    admin = AdminUser(
        username=request.username,
        email=str(request.email).lower() if request.email else None,
        password_hash=get_password_hash(request.password),
        permissions=auth_service.dump_permissions(request.permissions),
        is_active=request.is_active,
        is_super_admin=request.is_super_admin,
        must_change_credentials=False,
    )
    db.add(admin)
    db.flush()
    create_log(
        db,
        current_admin,
        "create_admin",
        "admin",
        admin.id,
        details={"username": admin.username, "is_super_admin": admin.is_super_admin},
    )
    db.refresh(admin)
    return auth_service.admin_to_response(admin)


@router.put("/{admin_id}", response_model=AdminUserResponse)
def update_admin(
    admin_id: int,
    request: AdminUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    admin = db.get(AdminUser, admin_id)
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="管理员不存在")

    _ensure_super_admin_boundary(
        current_admin,
        target_admin=admin,
        requested_super_admin=request.is_super_admin,
    )
    if request.permissions is not None:
        _ensure_permission_delegation(
            current_admin,
            request.permissions,
            existing_permissions=auth_service.parse_permissions(admin.permissions),
        )

    if request.permissions is not None:
        admin.permissions = auth_service.dump_permissions(request.permissions)
    if "email" in request.model_fields_set:
        admin.email = str(request.email).lower() if request.email else None
    if request.is_active is not None:
        if admin.id == current_admin.id and not request.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用当前账号")
        admin.is_active = request.is_active
    if request.is_super_admin is not None:
        if admin.id == current_admin.id and not request.is_super_admin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能取消自己的超级管理员权限")
        admin.is_super_admin = request.is_super_admin
    admin.updated_at = local_now()
    db.add(admin)
    db.flush()
    create_log(
        db,
        current_admin,
        "update_admin",
        "admin",
        admin_id,
        details={"username": admin.username},
    )
    db.refresh(admin)
    return auth_service.admin_to_response(admin)


@router.delete("/{admin_id}", status_code=status.HTTP_200_OK)
def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
) -> dict[str, str]:
    """永久删除指定管理员，并撤销其全部 Management 会话。

    Args:
        admin_id: 待删除管理员的数据库主键。
        db: 当前数据库会话。
        current_admin: 已通过管理员管理权限校验的操作者。

    Returns:
        dict[str, str]: 可供前端展示的删除成功消息。

    Raises:
        HTTPException: 目标不存在、尝试删除自己，或普通管理员尝试删除超级管理员。
    """

    admin = db.get(AdminUser, admin_id)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="管理员不存在")
    if admin.id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前账号")
    _ensure_super_admin_boundary(current_admin, target_admin=admin)

    sessions = db.exec(select(AdminSession).where(AdminSession.admin_id == admin_id)).all()
    for session in sessions:
        db.delete(session)

    deleted_username = admin.username
    db.delete(admin)
    db.flush()
    create_log(
        db,
        current_admin,
        "delete_admin",
        "admin",
        admin_id,
        details={"username": deleted_username},
    )
    return {"message": "管理员已删除"}
