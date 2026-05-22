# 头像上传路由控制器
# 处理用户头像上传相关的 API 请求
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from social_platform.app.api.deps import get_db, get_current_user
from social_platform.app.models.user import User
from social_platform.app.schemas.user import UserResponse
from social_platform.app.services.avatar_service import (
    validate_avatar_file,
    save_avatar_file,
    delete_avatar_file,
)
from social_platform.app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/avatar", response_model=UserResponse, summary="上传用户头像", description="上传并更新当前用户的头像图片。")
async def upload_avatar(
    file: UploadFile = File(..., description="头像图片文件"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
    try:
        validate_avatar_file(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    old_avatar_url = current_user.avatar_url

    try:
        avatar_url = await save_avatar_file(file, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"头像上传失败：{str(e)}")

    if old_avatar_url:
        await delete_avatar_file(old_avatar_url)

    current_user.avatar_url = avatar_url
    db.commit()
    db.refresh(current_user)

    return current_user


@router.delete("/avatar", response_model=UserResponse, summary="删除用户头像", description="删除当前用户的头像，恢复为默认状态。")
async def delete_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除用户头像

    需要认证：是的（Bearer Token）

    返回：更新后的用户信息

    错误：
    - 500：删除失败
    """
    old_avatar_url = current_user.avatar_url

    if old_avatar_url:
        await delete_avatar_file(old_avatar_url)

    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)

    return current_user
