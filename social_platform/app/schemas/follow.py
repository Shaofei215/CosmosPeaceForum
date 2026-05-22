# 关注数据验证模型（Pydantic Schemas）
# 定义关注数据的请求和响应格式
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from social_platform.app.schemas.response import PaginationInfo


class FollowToggleResponse(BaseModel):
    """
    关注操作响应模型
    用于关注/取消关注操作的 API 响应

    Attributes:
        user_id: 被操作的用户 ID
        is_following: 操作后的关注状态，True 表示已关注，False 表示未关注
        followers_count: 被操作用户的粉丝数
        following_count: 当前用户的关注数

    Note:
        - is_following 为 True 表示刚刚完成关注操作
        - is_following 为 False 表示刚刚完成取消关注操作
    """
    user_id: int = Field(..., description="被操作的用户 ID")
    is_following: bool = Field(..., description="操作后的关注状态")
    followers_count: int = Field(..., description="被操作用户的粉丝数")
    following_count: int = Field(..., description="当前用户的关注数")


class FollowStatusResponse(BaseModel):
    """
    关注状态响应模型
    用于查询当前用户与目标用户之间的关注关系

    Attributes:
        user_id: 目标用户 ID
        is_following: 当前用户是否关注了目标用户
        is_followed_by: 目标用户是否关注了当前用户
        is_mutual: 是否互相关注（双向关注）

    Example:
        - A 关注 B，B 未关注 A：is_following=True, is_followed_by=False, is_mutual=False
        - A 和 B 互相关注：is_following=True, is_followed_by=True, is_mutual=True
        - A 未关注 B，B 也未关注 A：is_following=False, is_followed_by=False, is_mutual=False
    """
    user_id: int = Field(..., description="目标用户 ID")
    is_following: bool = Field(..., description="当前用户是否关注了目标用户")
    is_followed_by: bool = Field(..., description="目标用户是否关注了当前用户")
    is_mutual: bool = Field(..., description="是否互相关注（双向关注）")


class FollowUserItem(BaseModel):
    """
    关注列表/粉丝列表中的用户项模型
    用于展示关注列表或粉丝列表中的单个用户信息

    Attributes:
        id: 用户 ID
        username: 用户名
        bio: 个人简介
        avatar_url: 头像 URL
        is_following: 当前用户是否关注了此用户（仅在粉丝列表中有意义）
        is_followed_by: 此用户是否关注了当前用户（仅在关注列表中有意义）
        created_at: 关注时间

    Note:
        - 在关注列表中，is_following 始终为 True
        - 在粉丝列表中，is_followed_by 始终为 True
    """
    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    bio: Optional[str] = Field(None, description="个人简介")
    avatar_url: Optional[str] = Field(None, description="头像 URL")
    is_following: bool = Field(False, description="当前用户是否关注了此用户")
    is_followed_by: bool = Field(False, description="此用户是否关注了当前用户")
    created_at: datetime = Field(..., description="关注时间")

    class Config:
        from_attributes = True


class FollowListData(BaseModel):
    """
    关注/粉丝列表数据模型
    用于包装关注列表或粉丝列表的响应数据

    Attributes:
        items: 用户列表
        pagination: 分页信息
    """
    items: list[FollowUserItem] = Field(default_factory=list, description="用户列表")
    pagination: PaginationInfo = Field(..., description="分页信息")