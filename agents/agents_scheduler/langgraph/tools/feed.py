"""Feed 工具函数。

本模块只保留内部 LangChain `@tool` 适配层。工具说明面向 LLM 保持完整，
平台调用、滚动状态语义和内容构建由共享平台工具核心维护。
"""

from langchain_core.tools import tool

from agents.agents_scheduler.langgraph.tools.support.shared_platform import run_shared_tool
from agents.agents_scheduler.langgraph.tools.types import ToolResult


@tool
def get_global_feed(
    feed_type: str = "recommended",
    seed: str = "default",
    reason: str = "",
    summary: str = "",
) -> ToolResult:
    """
    社交平台主页信息流获取，用于回到主页，不可连续调用，如要查看更多内容请调用 scroll

    获取指定类型的信息流顶端 5 条帖子。feed_type 可选：
    recommended（推荐，按热度排序）、latest（最新，按时间倒序）、following（关注的人，按推荐排序）。

    注意：此工具会自动从当前执行上下文获取认证信息（如有），用于获取点赞状态和关注状态。

    Args:
        feed_type: 信息流类型，必须是 "recommended"、"latest" 或 "following"。
                   也兼容 "hot"，会视为 "recommended"。
        seed: 推荐/关注流 Top-N 重排种子；scroll 会自动沿用这个 seed。
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要浏览主页信息流"、"查看最新动态"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我回到了主页，看到了5条最新帖子"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "浏览了主页信息流"
            - data: 包含 data 和 pagination 的字典

    Raises:
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("get_global_feed", {"feed_type": feed_type, "seed": seed, "count": 5})
    return ToolResult(action=result.action, data=result.data)


@tool
def expand_post(
    post_id: int,
    reason: str = "",
    summary: str = "",
) -> ToolResult:
    """
    展开查看帖子的完整内容

    获取指定帖子的完整信息。对于文章类型帖子，会返回 Markdown 全文。
    如需查看评论，请调用 view_post_comments；如需继续看后续评论，再调用 scroll。

    注意：此工具会自动从当前执行上下文获取认证信息（如有），用于获取点赞状态。

    Args:
        post_id: 目标帖子的 ID
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想阅读帖子的完整内容并查看热门评论"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在主页看到了这个帖子的预览，想点进来看看完整内容"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "展开了 @{author} 的帖子：{content}"
            - data: 包含 post 的字典

    Raises:
        NotFoundError: 帖子不存在
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("expand_post", {"post_id": post_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def view_post_comments(
    post_id: int,
    reason: str = "",
    summary: str = "",
    comment_count: int = 5,
    sort: str = "default",
    seed: str = "default",
) -> ToolResult:
    """
    查看指定帖子下的一级评论

    获取指定帖子下的第一批一级评论。之后继续调用 scroll，可查看后续一级评论。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        post_id: 目标帖子的 ID
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想查看这条帖子的评论"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我读完帖子后想看看评论区的讨论"等。
        comment_count: 要返回的一级评论数量，默认 5
        sort: 评论排序，default（推荐）或 latest（最新）
        seed: 默认评论流 Top-N 重排种子，同一 seed 下分页稳定

    Returns:
        ToolResult: 包含以下字段:
            - action: "查看了 @{author} 的帖子评论"
            - data: 包含 post, comments, total 的字典

    Raises:
        NotFoundError: 帖子不存在
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool(
        "view_post_comments",
        {"post_id": post_id, "comment_count": comment_count, "sort": sort, "seed": seed},
    )
    return ToolResult(action=result.action, data=result.data)


@tool
def expand_comment(
    post_id: int,
    comment_id: int,
    reason: str = "",
    summary: str = "",
    reply_count: int = 5,
) -> ToolResult:
    """
    展开查看评论及其回复

    获取指定评论的详细信息，以及该评论下的第一批回复。
    之后继续调用 scroll，可查看该评论下的后续回复。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        post_id: 评论所属帖子的 ID
        comment_id: 目标一级评论的 ID
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想查看这条评论及其回复"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在评论区看到了这条评论，想看看下面的回复"等。
        reply_count: 要返回的回复数量，默认 5

    Returns:
        ToolResult: 包含以下字段:
            - action: "展开了 @{comment_author} 的评论：{comment_content}（来自 @{post_author} 的帖子：{post_content}）"
            - data: 包含 post, comment, replies, total 的字典

    Raises:
        NotFoundError: 评论不存在
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool(
        "expand_comment",
        {"post_id": post_id, "comment_id": comment_id, "reply_count": reply_count},
    )
    return ToolResult(action=result.action, data=result.data)


@tool
def scroll(
    count: int = 5,
    reason: str = "",
    summary: str = "",
) -> ToolResult:
    """
    向下滑动当前页面，自动查看后续内容

    该工具不需要知道当前位置，会自动延续最近一次打开的可滚动页面：
    get_global_feed 之后继续加载主页信息流；search_platform 之后继续加载搜索结果；
    view_post_comments 之后继续加载一级评论；expand_comment 之后继续加载该评论下的回复；
    get_user_profile 之后继续加载用户主页帖子。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        count: 本次查看数量，默认 5，范围 1-20。
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要继续往下看"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看完了当前页面，想看看后面还有什么"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "向下滑动浏览了更多内容"
            - data: 后续帖子、评论或回复

    Raises:
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("scroll", {"count": count})
    return ToolResult(action=result.action, data=result.data)
