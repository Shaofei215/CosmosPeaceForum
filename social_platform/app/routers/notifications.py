"""
通知路由模块
处理用户互动消息的 API 请求
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Dict

from app.database import get_db
from app import crud, schemas
from app.models import NotificationType

router = APIRouter(prefix="/notifications", tags=["通知"])


@router.get("", response_model=List[Dict])
def get_notifications(
    user_id: int = Query(..., description="用户 ID"),
    limit: int = Query(20, ge=1, le=50, description="最大返回数量"),
    is_read: bool = Query(None, description="是否只返回已读/未读"),
    db: Session = Depends(get_db)
):
    """
    获取用户的通知消息列表（默认时间倒序）
    
    - **user_id**: 用户 ID
    - **limit**: 最大返回数量（1-50）
    - **is_read**: 是否只返回已读/未读（None 表示全部）
    """
    notifications = crud.get_user_notifications(
        db=db,
        user_id=user_id,
        limit=limit,
        is_read=is_read
    )
    
    # 转换为响应格式
    result = []
    for notif in notifications:
        notif_data = {
            "id": notif.id,
            "user_id": notif.user_id,
            "actor_id": notif.actor_id,
            "type": notif.type.value,
            "is_read": notif.is_read,
            "created_at": notif.created_at.isoformat() if notif.created_at else None,
        }
        
        # 添加关联对象信息
        if notif.actor:
            notif_data["actor"] = {
                "id": notif.actor.id,
                "username": notif.actor.username,
                "avatar": notif.actor.avatar
            }
        
        if notif.post:
            notif_data["post"] = {
                "id": notif.post.id,
                "content": notif.post.content[:100]
            }
        
        if notif.comment:
            notif_data["comment"] = {
                "id": notif.comment.id,
                "content": notif.comment.content[:100]
            }
        
        if notif.reply:
            notif_data["reply"] = {
                "id": notif.reply.id,
                "content": notif.reply.content[:80]
            }
        
        result.append(notif_data)
    
    return result


@router.post("/{notification_id}/read", response_model=Dict)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db)
):
    """
    标记通知为已读
    
    - **notification_id**: 通知 ID
    """
    notification = crud.mark_notification_read(db, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    return {
        "id": notification.id,
        "is_read": notification.is_read
    }


@router.post("/read-all", response_model=Dict)
def mark_all_notifications_as_read(
    user_id: int = Query(..., description="用户 ID"),
    db: Session = Depends(get_db)
):
    """
    标记用户的所有通知为已读
    
    - **user_id**: 用户 ID
    """
    count = crud.mark_all_notifications_read(db, user_id)
    return {"marked_count": count}


@router.get("/unread-count", response_model=Dict)
def get_unread_notifications_count(
    user_id: int = Query(..., description="用户 ID"),
    db: Session = Depends(get_db)
):
    """
    获取用户的未读通知数量
    
    - **user_id**: 用户 ID
    """
    count = crud.get_unread_notifications_count(db, user_id)
    return {"unread_count": count}
