"""外部 Agent 工具协议模型。

这些模型定义 `/external/v1` 的稳定请求、发现和响应结构。工具参数以独立
Pydantic 模型校验，响应统一包裹为 `{ok, tool, action, data, meta}`，便于外部
Agent 宿主按机器字段处理错误与分页游标。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolExecutionRequest(BaseModel):
    """工具执行请求体。

    Args:
        arguments: 当前工具的 JSON 参数。Token、当前用户、来源证明和 Prompt 原因都不允许放入这里。
    """

    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolMeta(BaseModel):
    """工具响应元信息。

    Args:
        request_id: 当前网关请求 ID。
        schema_version: 外部工具协议版本。
        scroll_cursor: 下一次 `scroll` 可使用的签名游标。
        has_more: 当前读取结果是否还有后续内容。
    """

    request_id: str
    schema_version: str = "1"
    scroll_cursor: str | None = None
    has_more: bool = False


class ToolExecutionResponse(BaseModel):
    """工具执行成功响应。"""

    ok: bool = True
    tool: str
    action: str
    data: dict[str, Any]
    meta: ToolMeta


class ToolErrorResponse(BaseModel):
    """工具执行失败响应。"""

    ok: bool = False
    error_code: str
    message: str
    tool: str | None = None
    meta: ToolMeta


class ToolDefinition(BaseModel):
    """工具发现接口返回的单个工具定义。"""

    name: str
    description: str
    kind: Literal["read", "write"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    error_codes: list[str]


class ToolListResponse(BaseModel):
    """工具发现接口响应。"""

    schema_version: str = "1"
    tools: list[ToolDefinition]


class FeedArguments(BaseModel):
    """主页信息流读取参数。"""

    feed_type: Literal["recommended", "latest", "following", "hot", "recommend"] = "recommended"
    seed: str = Field(default="default", max_length=64)
    count: int = Field(default=5, ge=1, le=20)


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

    Args:
        scroll_cursor: 上一次读取工具返回的签名游标。
        count: 本次读取数量。
    """

    scroll_cursor: str = Field(..., min_length=16)
    count: int = Field(default=5, ge=1, le=20)


class UserProfileArguments(BaseModel):
    """用户主页读取参数。"""

    user_id: int = Field(..., gt=0)
    post_count: int = Field(default=5, ge=1, le=20)


class SearchArguments(BaseModel):
    """平台搜索参数。"""

    type: Literal["content", "user", "topic"]
    query: str = Field(..., min_length=1, max_length=100)
    count: int = Field(default=5, ge=1, le=20)


class NotificationListArguments(BaseModel):
    """通知列表读取参数。"""

    count: int = Field(default=5, ge=1, le=20)
    type: str | None = Field(default=None, max_length=64)


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


class ToggleCommentLikeArguments(CommentArguments):
    """评论点赞切换参数。"""


class ToggleFollowArguments(BaseModel):
    """关注切换参数。"""

    user_id: int = Field(..., gt=0)
