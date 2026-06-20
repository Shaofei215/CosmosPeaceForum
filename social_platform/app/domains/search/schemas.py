from typing import Literal

from pydantic import BaseModel

from social_platform.app.domains.user.schemas import UserResponse


SearchType = Literal["content", "user", "topic"]


class SearchMeta(BaseModel):
    """搜索投影 API schema的分页元信息，供 API adapter 做参数校验和响应序列化。"""
    type: SearchType
    query: str


class UserSearchItem(UserResponse):
    """搜索投影 API schema的列表项，供 API adapter 做参数校验和响应序列化。"""
    is_following: bool = False
    is_followed_by: bool = False
    is_mutual: bool = False
