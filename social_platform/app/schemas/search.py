from typing import Literal

from pydantic import BaseModel

from social_platform.app.schemas.user import UserResponse


SearchType = Literal["content", "user"]


class SearchMeta(BaseModel):
    type: SearchType
    query: str


class UserSearchItem(UserResponse):
    is_following: bool = False
    is_followed_by: bool = False
    is_mutual: bool = False
