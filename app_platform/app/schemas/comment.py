from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app_platform.app.schemas.user import UserResponse


class CommentBase(BaseModel):
    content: str = Field(..., min_length=1)


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1)
    parent_id: Optional[int] = None
    repost: bool = False


class CommentUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1)


class CommentResponse(CommentBase):
    id: int
    post_id: int
    owner_id: int
    parent_id: Optional[int] = None
    like_count: int = 0
    reply_count: int = 0
    heat_score: float = 0
    created_at: datetime
    is_liked: bool = False
    owner: Optional[UserResponse] = None

    class Config:
        from_attributes = True


class CommentTreeResponse(CommentResponse):
    children: List["CommentTreeResponse"] = []

    class Config:
        from_attributes = True


CommentTreeResponse.model_rebuild()


class CommentLikeToggleResponse(BaseModel):
    is_liked: bool
    like_count: int

    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    items: List[CommentTreeResponse]
    total: int
    skip: int
    limit: int

    class Config:
        from_attributes = True
