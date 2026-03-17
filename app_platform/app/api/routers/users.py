# 用户路由控制器
# 处理用户相关的 API 请求
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api.deps import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate

# 创建 API 路由器
router = APIRouter()


@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    创建新用户
    
    Args:
        user: 用户创建请求数据
        db: 数据库会话
    
    Returns:
        创建的用户信息
    
    Raises:
        HTTPException: 用户名已存在时抛出 400 错误
    """
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 创建新用户
    db_user = User(**user.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/", response_model=List[UserResponse])
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取用户列表（分页）
    
    Args:
        skip: 跳过前 N 条记录
        limit: 返回记录数量，最大 100
        db: 数据库会话
    
    Returns:
        用户列表
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    获取指定用户的详细信息
    
    Args:
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        用户详细信息
    
    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.get("/username/{username}", response_model=UserResponse)
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """
    通过用户名获取用户信息
    
    Args:
        username: 用户名
        db: 数据库会话
    
    Returns:
        用户详细信息
    
    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db)
):
    """
    更新用户信息
    
    Args:
        user_id: 用户 ID
        user_update: 用户更新数据
        db: 数据库会话
    
    Returns:
        更新后的用户信息
    
    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 只更新提供的字段
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    删除用户
    
    Args:
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        删除成功消息
    
    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    db.delete(user)
    db.commit()
    return {"message": "用户删除成功"}
