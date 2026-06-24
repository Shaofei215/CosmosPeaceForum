# 头像上传路由控制器
# 处理用户头像上传相关的 API 请求
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from social_platform.app.admin.services.moderation_guard import ensure_action_allowed
from social_platform.app.api.deps import get_db, get_current_user
from social_platform.app.domains.user import application as user_application
from social_platform.app.domains.user.models import User
from social_platform.app.domains.user.schemas import UserResponse

router = APIRouter()


@router.post(
    "/avatar",
    response_model=UserResponse,
    summary="上传用户头像",
    description="上传并更新当前用户的头像图片。",
)
async def upload_avatar(
    file: UploadFile = File(..., description="头像图片文件"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> User:
    """
    上传用户头像

    - **file**: 头像图片文件，支持 JPEG、PNG、GIF、WebP 格式
    - 最大文件大小：5MB

    需要认证：是的（Bearer Token）

    返回：更新后的用户信息

    错误：
    - 400：不支持的图片格式
    - 400：图片大小超过限制
    - 500：文件保存失败
    """
    ensure_action_allowed(db, current_user, "interaction")
    try:
        return await user_application.upload_user_avatar(db, current_user, file)
    except user_application.AvatarValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except user_application.UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except user_application.AvatarStorageError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/avatar",
    response_model=UserResponse,
    summary="删除用户头像",
    description="删除当前用户的头像，恢复为默认状态。",
)
async def delete_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> User:
    """
    删除用户头像

    需要认证：是的（Bearer Token）

    返回：更新后的用户信息

    错误：
    - 500：删除失败
    """
    ensure_action_allowed(db, current_user, "interaction")
    try:
        return await user_application.delete_user_avatar(db, current_user)
    except user_application.UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
