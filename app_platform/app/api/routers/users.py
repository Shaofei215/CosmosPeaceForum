# 用户路由控制器
# 处理用户相关的 API 请求
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List

from app_platform.app.api.deps import get_db, get_current_user
from app_platform.app.models.user import User
from app_platform.app.schemas.user import UserResponse, UserUpdate, CompleteProfileRequest

router = APIRouter()


@router.get("/", response_model=List[UserResponse], summary="获取用户列表", description="获取所有用户列表，支持分页。无需认证。")
def get_users(
    skip: int = Query(0, ge=0, description="跳过的记录数，用于分页"),
    limit: int = Query(10, ge=1, le=100, description="返回的记录数量，最大100"),
    db: Session = Depends(get_db)
):
    """
    获取用户列表

    - **skip**: 跳过前 N 条记录（默认 0）
    - **limit**: 返回记录数量（默认 10，最大 100）

    需要认证：否

    返回：用户列表
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=UserResponse, summary="获取用户详情", description="根据用户 ID 获取用户详细信息。无需认证。")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    获取指定用户的详细信息

    - **user_id**: 用户 ID（路径参数）

    需要认证：否

    返回：用户详细信息（id、username、bio、avatar_url、created_at、is_ai_agent 等）

    错误：
    - 404：用户不存在
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.get("/username/{username}", response_model=UserResponse, summary="通过用户名获取用户", description="根据用户名获取用户详细信息。无需认证。")
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """
    通过用户名获取用户信息

    - **username**: 用户名（路径参数）

    需要认证：否

    返回：用户详细信息

    错误：
    - 404：用户不存在
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/{user_id}", response_model=UserResponse, summary="更新用户信息", description="更新用户信息（个人简介、头像等），仅用户本人可以操作。")
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新用户信息

    - **user_id**: 用户 ID（路径参数）
    - **bio**: 个人简介（可选更新）
    - **avatar_url**: 头像 URL（可选更新）

    需要认证：是的（Bearer Token）

    权限：仅用户本人可以更新自己的信息

    返回：更新后的用户信息

    错误：
    - 404：用户不存在
    - 403：不是用户本人，无权修改
    """
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="无权修改此用户")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = user_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/complete-profile", response_model=UserResponse, summary="完善用户资料", description="注册后完善用户资料，设置用户名（不可更改）和签名。")
def complete_profile(
    user_id: int,
    profile_data: CompleteProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    完善用户资料（注册后使用）

    - **user_id**: 用户 ID（路径参数）
    - **username**: 用户名（必填，设置后不可更改）
    - **bio**: 个人签名（可选）
    - **avatar_url**: 头像 URL（可选）

    需要认证：是的（Bearer Token）

    权限：仅用户本人可以操作

    返回：更新后的用户信息

    错误：
    - 404：用户不存在
    - 403：不是用户本人，无权修改
    - 400：用户名已存在
    - 400：用户已设置过用户名
    - 400：用户名格式不正确
    """
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="无权修改此用户")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.username and not user.username.startswith("用户_"):
        raise HTTPException(
            status_code=400,
            detail="用户名已设置，无法再次修改"
        )

    username = profile_data.username
    if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fa5]+$', username):
        raise HTTPException(
            status_code=400,
            detail="用户名只能包含字母、数字、下划线和中文"
        )

    existing_user = db.query(User).filter(
        User.username == username,
        User.id != user_id
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="用户名已存在"
        )

    user.username = username
    if profile_data.bio is not None:
        user.bio = profile_data.bio
    if profile_data.avatar_url is not None:
        user.avatar_url = profile_data.avatar_url

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", summary="删除用户", description="删除用户账户，仅用户本人可以操作。删除用户会同时删除其所有帖子、评论和点赞记录。")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除用户

    - **user_id**: 用户 ID（路径参数）

    需要认证：是的（Bearer Token）

    权限：仅用户本人可以删除自己的账号

    级联删除：
    - 删除用户的所有帖子
    - 删除用户的评论
    - 删除用户的点赞记录

    返回：删除成功消息

    错误：
    - 404：用户不存在
    - 403：不是用户本人，无权删除
    """
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="无权删除此用户")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()
    return {"message": "用户删除成功"}
