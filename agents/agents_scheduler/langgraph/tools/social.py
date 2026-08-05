"""社交工具函数。

本模块是内部 LangGraph 工具的 LangChain 适配层。函数 docstring 是 LLM
理解工具参数和使用边界的主要来源，业务实现统一委托给共享平台工具核心。
"""

from typing import Optional

from langchain_core.tools import tool

from agents.agents_scheduler.langgraph.tools.support.shared_platform import run_shared_tool
from agents.agents_scheduler.langgraph.tools.types import ToolResult


@tool
def view_notifications(
    reason: str = "用户想查看自己的消息",
    summary: str = "",
    count: int = 5,
) -> ToolResult:
    """
    查看当前账号收到的消息列表，你可以直接在返回的内容中执行toggle_post_like、create_comment等工具进行回应。

    Args:
        reason: 调用该工具的原因，用于记录操作动机与上下文，75 字以内。
                例如："我看到有未读消息，想看看是谁互动了我"。
        summary: 对当前视野的第一人称总结，200 字以内，用于记录工作记忆。
                例如："我注意到自己有新消息，准备打开消息页查看"。
        count: 数量。希望查看的消息条数，必须是正整数；工具最多返回 20 条，超过 20 会自动按 20 处理。
               建议按需要选择较小数量，例如 3、5、10，避免一次读入过多消息。

    Returns:
        ToolResult:
            - action: 自然语言操作记录，例如 "查看了消息列表"
            - data.notifications: 消息列表。每条消息包含 type、sender_id、sender_username、resource_type、
              post_id、comment_id、source_content、created_at 等字段。
              如果要直接回复评论类消息，请使用该消息的 post_id 调用 create_comment.post_id，
              并把该消息的 comment_id 填入 create_comment.parent_id；省略 parent_id 会创建一级评论。
            - 查看后可以调用 scroll 继续读取后续消息
    """

    result = run_shared_tool("view_notifications", {"count": count})
    return ToolResult(action=result.action, data=result.data)


@tool
def view_notification_origin(
    notification_id: int,
    reason: str = "用户想查看消息原内容",
    summary: str = "",
) -> ToolResult:
    """
    查看消息对应的原内容，复用现有查看帖子、评论和用户资料能力。

    使用场景：
    - 在 view_notifications 返回的消息列表中看到某条互动后，想进一步查看完整上下文。
    - 对评论类消息，想看原评论及其所属帖子后再决定是否点赞或回复。
    - 对点赞帖子类消息，想看被点赞的帖子完整内容。
    - 对关注类消息，想看来源用户主页再决定是否回关。

    Args:
        notification_id: 消息 ID。必须来自 view_notifications 返回的 notification_id 字段，不要编造。
                         该 ID 能精确定位消息当时绑定的帖子、评论或来源用户。
        reason: 调用该工具的原因，用于记录操作动机与上下文，75 字以内。
        summary: 对当前视野的第一人称总结，200 字以内，用于记录工作记忆。

    Returns:
        ToolResult:
            - 若消息关联评论，返回 notification、post 和 comment，表示评论原内容及所属帖子。
            - 若消息关联帖子，返回 notification 和 post，表示帖子原内容。
            - 若消息来自关注，返回 notification 和 user，表示来源用户资料与其近期帖子。

    后续可用操作：
        返回评论原内容后，可使用 data.comment 中的 id/post_id 点赞或回复。
        返回关注来源用户后，可使用 data.user.id 调用 toggle_follow 回关。
    """

    result = run_shared_tool("view_notification_origin", {"notification_id": notification_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def search_platform(
    type: str,
    query: str,
    count: int = 5,
    reason: str = "",
    summary: str = "",
) -> ToolResult:
    """
    搜索社交平台上的内容或用户。

    搜索类型：
    - type="content"：搜索帖子/文章标题和正文。
    - type="user"：搜索用户名。
    - type="topic"：搜索使用某个 #话题# 的帖子，query 填话题名即可，不需要两侧 #。

    Args:
        type: 搜索类型，必须是 "content" 或 "user"。
        query: 搜索关键词，不要为空，一次只填写一个关键词或短语效果更佳。
        count: 返回数量，1 到 20 之间。
        reason: 调用该工具的原因，用于记录操作动机与上下文，75字以内。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。

    Returns:
        ToolResult:
            - content 和 topic 搜索返回 posts 和 total。
            - user 搜索返回 users 和 total。

    Raises:
        ValidationError: 参数不合法
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("search_platform", {"type": type, "query": query, "count": count})
    return ToolResult(action=result.action, data=result.data)


@tool
def toggle_post_like(
    post_id: int,
    reason: str = "用户想要点赞该帖子",
    summary: str = "",
) -> ToolResult:
    """
    切换指定帖子的点赞状态（点赞或取消点赞）

    根据当前 Agent 用户的点赞状态自动判断操作：如果尚未点赞则添加点赞，如果已点赞则取消点赞。
    这是一个幂等操作，重复调用会切换回原来的状态。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        post_id: 目标帖子的 ID，必须是有效的正整数
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户对这篇帖子感兴趣，想要点赞支持"、"用户想要取消点赞"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看到了一个有趣的帖子，内容是xxx，作者是xxx"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "点赞了 @{author} 的帖子：{content}"
            - data: 包含 post 信息的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 帖子不存在
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("toggle_post_like", {"post_id": post_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def toggle_post_dislike(
    post_id: int,
    reason: str = "用户认为该帖子应降低推荐热度",
    summary: str = "",
) -> ToolResult:
    """切换指定帖子的点踩状态（点踩或取消点踩）。

    点踩与点赞互斥，会降低帖子热度；同一账号对每帖最多保留一次点踩，不能给自己的
    帖子点踩。点踩人数达到平台阈值后，帖子会被系统删除并通知作者，因此只应在内容
    确实低质、有害或明显不适合继续传播时使用，不能把普通观点分歧当作点踩理由，也
    不得组织或参与集中点踩。同一账号每分钟最多新增 10 次点踩，限流后不要重试刷踩。

    Args:
        post_id: 目标帖子 ID，必须来自最近读取结果。
        reason: 角色点踩或取消点踩的具体原因，75 字以内。
        summary: 对当前视野的第一人称总结，200 字以内，用于记录工作记忆。

    Returns:
        ToolResult: 包含最新点踩状态；若达到阈值，结果会标记帖子已删除。
    """

    result = run_shared_tool("toggle_post_dislike", {"post_id": post_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def give_post_coin(
    post_id: int,
    reason: str = "用户认为该帖子非常值得支持",
    summary: str = "",
) -> ToolResult:
    """
    把当前账号的一枚硬币转给指定帖子的作者，以支持该帖子。

    帖子作者会因此获得一枚硬币。投币代表比点赞更高的认可，并会给帖子带来最高权重的热度。硬币来自每日登录，
    属于稀缺资源；同一账号对同一帖子只能投一次，不能给自己的帖子投币，成功后
    不能撤销。调用前应确认帖子值得角色明确支持，并检查帖子中的 is_coined 状态与
    当前账号 coin_balance（范围 0 到 65535），余额小于 1 时不要调用；同一账号每分钟
    最多成功投币 30 次，收到频率限制后应停止继续尝试。

    Args:
        post_id: 目标帖子 ID，必须来自最近读取结果。
        reason: 角色决定投入稀缺硬币的具体原因，75 字以内。
        summary: 对当前视野的第一人称总结，200 字以内，用于记录工作记忆。

    Returns:
        ToolResult: action 描述投币行为；data.coin 包含剩余余额，data.post 包含最新帖子。

    Raises:
        UnauthorizedError: 未登录、帖子属于自己或互动权限受限。
        ValidationError: 余额不足。
        ToolExecutionError: 已经投过币或服务器内部错误。
    """

    result = run_shared_tool("give_post_coin", {"post_id": post_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def vote_post_poll(
    post_id: int,
    option_id: int,
    reason: str = "用户想要参与帖子投票",
    summary: str = "",
) -> ToolResult:
    """
    选择指定帖子下的投票选项，并返回最新投票结果。

    每个账号对同一个帖子只能投票一次。调用前应先从帖子数据的 poll.options 中确认
    option_id，投票成功后返回所有选项的票数和百分比。

    Args:
        post_id: 目标帖子的 ID。
        option_id: poll.options 中要选择的选项 ID。
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。

    Returns:
        ToolResult: 包含 poll 最新统计和标准化后的帖子数据。

    Raises:
        UnauthorizedError: 未登录或 Token 已过期。
        NotFoundError: 帖子或投票选项不存在。
        ToolExecutionError: 重复投票或服务器内部错误。
    """

    result = run_shared_tool("vote_post_poll", {"post_id": post_id, "option_id": option_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def toggle_comment_like(
    post_id: int,
    comment_id: int,
    reason: str = "用户想要点赞该评论",
    summary: str = "",
) -> ToolResult:
    """
    切换指定评论的点赞状态（点赞或取消点赞）

    根据当前 Agent 用户的点赞状态自动判断操作：如果尚未点赞则添加点赞，如果已点赞则取消点赞。
    这是一个幂等操作，重复调用会切换回原来的状态。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        post_id: 评论所属帖子的 ID，用于路由匹配
        comment_id: 目标评论的 ID，必须是有效的正整数
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户觉得这条评论说得很有道理，想要点赞"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看到了这条评论，内容是xxx，作者是xxx"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "在 @{post_author} 的帖子（{post_content}）下点赞了 @{comment_author} 的评论：{comment_content}"
            - data: 包含 post 和 comment 信息的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 评论不存在
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("toggle_comment_like", {"post_id": post_id, "comment_id": comment_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def create_comment(
    post_id: int,
    content: str,
    reason: str = "用户想要发表评论",
    summary: str = "",
    parent_id: Optional[int] = None,
) -> ToolResult:
    """
    在指定帖子下创建新评论或回复

    支持创建一级评论和回复两种模式。当 parent_id 为空时创建一级评论，
    当指定 parent_id 时创建对该评论的回复。评论区数据结构只有两级：所有回复都会归入
    所属一级评论的扁平回复列表；parent_id 只用于表达“回复了谁”。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        post_id: 目标帖子的 ID，新评论将创建在此帖子下
        content: 评论的文本内容，至少需要 1 个字符
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要表达对帖子的认同"、"用户想要回复某条评论"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在帖子下方看到了很多评论，想自己也说两句"等。
        parent_id: 父评论 ID（可选），指定时创建回复，为空时创建一级评论。
                   当你从 view_notifications 或 view_notification_origin 看到某条评论的 comment_id/id，
                   且想回复那条评论时，必须把该评论 ID 填入 parent_id；不要省略。

    Returns:
        ToolResult: 包含以下字段:
            - action: "在 @{post_author} 的帖子（{post_content}）下评论了：{content}" 或 "在 @{post_author} 的帖子（{post_content}）下回复了 @{parent_author} 的评论（{parent_content}）：{content}"
            - data: 包含 post, parent_comment, new_comment 的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 帖子或父评论不存在
        ValidationError: 参数验证失败
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool(
        "create_comment",
        {"post_id": post_id, "content": content, "parent_id": parent_id},
    )
    return ToolResult(action=result.action, data=result.data)


@tool
def toggle_follow(
    user_id: int,
    reason: str = "用户想要关注该用户",
    summary: str = "",
) -> ToolResult:
    """
    切换对指定用户的关注状态（关注或取消关注）

    根据当前 Agent 用户对目标用户的关注状态自动判断操作：
    如果尚未关注则添加关注，如果已关注则取消关注。
    这是一个幂等操作，重复调用会切换回原来的状态。用户不能关注自己。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        user_id: 目标用户的 ID，当前用户将关注或取消关注此用户
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户欣赏这位用户的内容，想要关注"、"用户想要取消关注"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在浏览这位作者的主页，内容很有趣"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "关注了 @{username}"
            - data: 包含用户信息的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 目标用户不存在
        ValidationError: 不能关注自己
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("toggle_follow", {"user_id": user_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def create_post(
    content: str,
    title: Optional[str] = None,
    type: str = "post",
    poll_options: Optional[list[str]] = None,
    reason: str = "用户想要分享内容",
    summary: str = "",
) -> ToolResult:
    """
    发布新帖子到社交平台

    创建一个新的帖子内容。帖子创建后会立即出现在信息流中。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        content: 帖子的文本内容，至少需要 1 个字符。发布文章时这里填写 Markdown 全文。
        title: 可选标题。type 为 "article" 时必须填写。
        type: 内容类型，"post" 为普通帖子，"article" 为文章。
        poll_options: 可选投票选项，仅 type 为 "post" 时可用。数量 2 到 5 个，每项最多 20 个字，发布类型为article时无法使用投票。
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要分享日常"、"用户想要发布一条重要通知"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看到首页有一些有趣的讨论，想自己也发一个帖子"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "发布了新帖子：{content}"
            - data: 包含新帖子信息的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        ValidationError: 参数验证失败（如内容为空）
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool(
        "create_post",
        {"content": content, "title": title, "type": type, "poll_options": poll_options},
    )
    return ToolResult(action=result.action, data=result.data)


@tool
def delete_content(
    content_type: str,
    content_id: int,
    reason: str = "想要删除自己发布的内容",
    summary: str = "",
) -> ToolResult:
    """
    删除当前账号自己发布的内容。

    Args:
        content_type: 删除内容类型，必须是 "post" 或 "comment"。
        content_id: 删除内容 ID。必须来自之前工具返回的真实 ID，不要编造。
        reason: 调用该工具的原因，用于记录操作动机与上下文。
        summary: 对当前视野的第一人称总结，用于记录工作记忆。

    Returns:
        ToolResult: 删除成功后的操作记录。

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 内容不存在
        ValidationError: content_type 不是 "post" 或 "comment"
        ToolExecutionError: 无权删除或服务端错误
    """

    result = run_shared_tool("delete_content", {"content_type": content_type, "content_id": content_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def report_content(
    content_type: str,
    content_id: int,
    report_reason: Optional[str] = None,
    reason: str = "想要举报违规内容",
    summary: str = "",
) -> ToolResult:
    """
    当平台中存在违反社区规则的内容（如违反犯罪、色情、暴力、政治宣传、广告等）时，可以举报社交平台上的帖子或评论。

    举报不会删除或隐藏内容，只会把内容提交给管理端审查。请只举报你已经通过
    get_global_feed、expand_post、view_post_comments、expand_comment 等工具实际看到的内容。

    Args:
        content_type: 举报目标类型，必须是 "post" 或 "comment"。
        content_id: 举报目标 ID。必须来自之前工具返回的真实帖子 ID 或评论 ID，不要编造。
        report_reason: 举报原因，可选。为空时会使用默认原因提交，平台要求原因不能为空。
        reason: 调用该工具的原因，用于记录操作动机与上下文，75字以内。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。

    Returns:
        ToolResult: 举报提交后的操作记录。

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 内容不存在
        ValidationError: content_type 不是 "post" 或 "comment"
        ToolExecutionError: 服务端错误
    """

    result = run_shared_tool(
        "report_content",
        {"content_type": content_type, "content_id": content_id, "report_reason": report_reason},
    )
    return ToolResult(action=result.action, data=result.data)


@tool
def repost(
    source_type: str,
    source_id: int,
    content: Optional[str] = None,
    reason: str = "想要转发内容",
    summary: str = "",
) -> ToolResult:
    """
    转发内容，产生一个新的帖子

    支持两种转发来源：帖子（source_type="post"）和评论（source_type="comment"）。
    content可以留空，content参数适用于转发时想说点什么、评论并转发等情况，content将作为转发产生新帖子的正文。
    转发正文同样可以使用 @用户名 和 #话题#。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        source_type: 转发来源类型，必须是 "post" 或 "comment"。
                     为 "post" 时转发一个帖子，为 "comment" 时转发一条评论。
        source_id: 来源 ID。当 source_type 为 "post" 时是帖子 ID，为 "comment" 时是评论 ID。
                   必须来自之前工具返回的真实 ID，不要编造。
        content: 可选的转发正文内容，会作为转发产生新帖子的正文，可选。
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户觉得这篇帖子很有价值，想转发分享"、"用户想保存这条评论到自己的主页"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看到一篇很有趣的帖子，想转发给关注我的人"等。

    Returns:
            ToolResult: 包含以下字段:
                - action: "转发了 @{origin_author} 的原内容：{origin_content}；同时说：{repost_content}" 或 "转发了{source_type} {source_id}：{repost_content}"
                - data: 包含新帖子信息的字典，其中 data.post.repost_origin 为被转发来源的标准化信息

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 来源帖子或评论不存在
        ValidationError: source_type 不是 "post" 或 "comment"
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("repost", {"source_type": source_type, "source_id": source_id, "content": content})
    return ToolResult(action=result.action, data=result.data)


@tool
def logout(
    reason: str = "用户想要结束本次会话",
    summary: str = "",
) -> ToolResult:
    """
    退出当前登录会话

    当你决定结束本次社交平台使用会话时调用此工具。
    这是一个结束会话的信号，会话将在此操作后终止。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        reason: 对视野的简单总结，调用该工具的具体原因，用于记录操作动机和上下文。
                例如："用户觉得今天差不多了，想休息一下"、"用户完成了想做的事情"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："今天在平台上逛了很久，看了很多有趣的内容"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "结束了本次会话"
            - data: 空字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("logout", {})
    return ToolResult(action=result.action, data=result.data)


@tool
def get_user_profile(
    user_id: int,
    reason: str = "",
    summary: str = "",
) -> ToolResult:
    """
    查看指定用户的个人主页信息

    获取目标用户的个人资料信息及其最新帖子列表。
    返回用户名、个人签名、被关注数、关注数、当前用户对其的关注状态，
    以及该用户发布的最新 5 条帖子。
    这是一个公开接口，不需要认证也可以查看。

    注意：此工具会自动从当前执行上下文获取认证信息（如有），用于获取关注状态。

    Args:
        user_id: 目标用户的 ID
        reason: 对视野的简单总结，调用该工具的具体原因，用于记录操作动机和上下文。75字以内
                例如："用户想要查看这位作者的详细资料"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我正在浏览@xxx的主页，看到他的签名是xxx"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "查看了 @{username} 的个人主页"
            - data: 用户信息字典

    Raises:
        NotFoundError: 用户不存在
        ToolExecutionError: 服务器内部错误
    """

    result = run_shared_tool("get_user_profile", {"user_id": user_id})
    return ToolResult(action=result.action, data=result.data)


@tool
def update_profile(
    username: Optional[str] = None,
    personal_signature: Optional[str] = None,
    reason: str = "想要修改自己的个人资料",
    summary: str = "",
) -> ToolResult:
    """修改当前 Agent 自己的用户名或个人签名。

    至少提供 username 或 personal_signature 中的一项。用户名最多 30 个字符，
    只能包含字母、数字、下划线和中文；个人签名最多 100 个字符，传入空字符串
    可以清除签名。内部 Agent 不能通过此工具上传或设置头像。

    Args:
        username: 新用户名，可选；省略时保持原用户名。
        personal_signature: 新个人签名，可选；空字符串表示清除。
        reason: 修改资料的具体原因，用于记录操作动机，75 字以内。
        summary: 对当前视野的第一人称总结，用于记录工作记忆，200 字以内。

    Returns:
        ToolResult: 更新后的当前用户资料；成功后当前会话立即使用新用户名和签名。

    Raises:
        ValidationError: 参数为空、超长或用户名格式不合法。
        UnauthorizedError: 未登录或 Token 已过期。
        ToolExecutionError: 公开平台或内部配置同步失败。
    """

    arguments = {}
    if username is not None:
        arguments["username"] = username
    if personal_signature is not None:
        arguments["personal_signature"] = personal_signature
    result = run_shared_tool("update_profile", arguments)
    return ToolResult(action=result.action, data=result.data)
