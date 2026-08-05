"""信息流领域 API 响应模型。

本模块定义 feed 读模型对 HTTP API 和其他读侧领域暴露的 DTO。它只描述公开
响应结构，不承载数据库事实或写侧业务流程。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from social_platform.app.domains.post.schemas import (
    MentionUser,
    PollResponse,
    RepostChainAuthor,
    RepostOriginPost,
)
from social_platform.app.domains.topic.schemas import TopicMention


class PostFeedItem(BaseModel):
    """信息流中的帖子响应项。

    Args:
        id: 帖子 ID。
        title: 文章标题，普通帖子可为空。
        type: 帖子类型，当前支持 ``post`` 和 ``article``。
        content: 帖子正文。
        created_at: 帖子创建时间。
        author_id: 作者用户 ID。
        author_name: 作者用户名。
        author_avatar: 作者头像 URL。
        author_bio: 作者简介。
        created_by_agent: 帖子是否由 Agent 通道创建。
        author_is_following: 当前用户是否关注作者。
        author_is_followed_by: 作者是否关注当前用户。
        author_is_mutual: 当前用户与作者是否互相关注。
        like_count: 点赞总数。
        dislike_count: 点踩总数。
        comment_count: 评论总数。
        repost_count: 转发总数。
        coin_count: 收到的硬币总数。
        heat_score: 缓存热度分数。
        is_liked: 当前用户是否点赞。
        is_disliked: 当前用户是否点踩。
        is_coined: 当前用户是否已经投币。
        repost_source_type: 转发源类型。
        repost_source_id: 转发源 ID。
        repost_root_post_id: 转发根帖 ID。
        repost_chain: 转发链文本。
        repost_chain_authors: 转发链中可跳转作者列表。
        mention_users: 正文中提及到的用户列表。
        topic_mentions: 正文中使用到的话题列表。
        repost_origin: 转发根帖摘要。
        repost_origin_missing: 转发源是否已缺失。
        poll: 帖子附带的投票统计；无投票时为空。
    """

    id: int
    title: str | None = None
    type: str = "post"
    content: str
    created_at: datetime
    author_id: int
    author_name: str
    author_avatar: str | None = None
    author_bio: str | None = None
    created_by_agent: bool = False
    author_is_following: bool = False
    author_is_followed_by: bool = False
    author_is_mutual: bool = False
    like_count: int = 0
    dislike_count: int = 0
    comment_count: int = 0
    repost_count: int = 0
    coin_count: int = 0
    heat_score: float = 0
    is_liked: bool = False
    is_disliked: bool = False
    is_coined: bool = False
    repost_source_type: str | None = None
    repost_source_id: int | None = None
    repost_root_post_id: int | None = None
    repost_chain: str | None = None
    repost_chain_authors: list[RepostChainAuthor] = Field(default_factory=list)
    mention_users: list[MentionUser] = Field(default_factory=list)
    topic_mentions: list[TopicMention] = Field(default_factory=list)
    repost_origin: RepostOriginPost | None = None
    repost_origin_missing: bool = False
    poll: PollResponse | None = None

    class Config:
        """启用 Pydantic ORM 属性读取，保持旧 feed 响应序列化兼容。"""

        from_attributes = True
