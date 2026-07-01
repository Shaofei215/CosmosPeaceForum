"""共享平台工具参数模型。

这些模型是内部 LangGraph 工具与外部 Agent 网关共同维护的参数契约。内部
`reason`、`summary`、Token、当前用户和来源证明不属于共享参数模型。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmptyArguments(BaseModel):
    """无参数工具参数。"""


class FeedArguments(BaseModel):
    """主页信息流读取参数。"""

    feed_type: Literal["recommended", "latest", "following", "hot", "recommend"] = "recommended"
    seed: str = Field(default="default", max_length=64)


class PostIdArguments(BaseModel):
    """帖子 ID 参数。"""

    post_id: int = Field(..., gt=0)


class ViewPostCommentsArguments(PostIdArguments):
    """一级评论读取参数。"""

    comment_count: int = Field(default=5, ge=1, le=20)
    sort: Literal["default", "latest"] = "default"
    seed: str = Field(default="default", max_length=64)


class CommentArguments(PostIdArguments):
    """评论详情参数。"""

    comment_id: int = Field(..., gt=0)


class ExpandCommentArguments(CommentArguments):
    """评论展开参数。"""

    reply_count: int = Field(default=5, ge=1, le=20)


class ScrollArguments(BaseModel):
    """滚动参数。

    外部 HTTP 协议中的签名 `scroll_cursor` 由外部 adapter 处理，共享核心只消费
    解码后的 cursor state。
    """

    count: int = Field(default=5, ge=1, le=20)


class UserProfileArguments(BaseModel):
    """用户主页读取参数。"""

    user_id: int = Field(..., gt=0)


class SearchArguments(BaseModel):
    """平台搜索参数。"""

    type: Literal["content", "user", "topic"]
    query: str = Field(..., min_length=1, max_length=100)
    count: int = Field(default=5, ge=1, le=20)


class NotificationListArguments(BaseModel):
    """通知列表读取参数。"""

    count: int = Field(default=5, ge=1, le=20)


class NotificationOriginArguments(BaseModel):
    """通知来源读取参数。"""

    notification_id: int = Field(..., gt=0)


class CreatePostArguments(BaseModel):
    """发帖参数。"""

    content: str = Field(..., min_length=1, max_length=20000)
    title: str | None = Field(default=None, max_length=200)
    type: Literal["post", "article"] = "post"
    poll_options: list[str] | None = Field(default=None, min_length=2, max_length=5)


class CreateCommentArguments(PostIdArguments):
    """评论或回复参数。"""

    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: int | None = Field(default=None, gt=0)


class TogglePostLikeArguments(PostIdArguments):
    """帖子点赞切换参数。"""


class VotePostPollArguments(PostIdArguments):
    """帖子投票参数。"""

    option_id: int = Field(..., gt=0)


class ToggleCommentLikeArguments(CommentArguments):
    """评论点赞切换参数。"""


class ToggleFollowArguments(BaseModel):
    """关注切换参数。"""

    user_id: int = Field(..., gt=0)


class DeleteContentArguments(BaseModel):
    """删除内容参数。"""

    content_type: Literal["post", "comment"]
    content_id: int = Field(..., gt=0)


class ReportContentArguments(DeleteContentArguments):
    """举报内容参数。"""

    report_reason: str | None = Field(default=None, max_length=500)


class RepostArguments(BaseModel):
    """转发内容参数。"""

    source_type: Literal["post", "comment"]
    source_id: int = Field(..., gt=0)
    content: str | None = Field(default=None, max_length=20000)
