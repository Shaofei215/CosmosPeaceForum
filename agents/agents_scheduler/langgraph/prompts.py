# Prompt 模板模块
# 定义 LangGraph 会话中使用的各种 Prompt 模板
from typing import Dict, Any, List

from agents.prompt_templates import (
    AGENT_SYSTEM_PROMPT_KEY,
    SUMMARIZE_MEMORY_PROMPT_KEY,
    get_default_prompt_template,
    render_prompt_template,
)


def _get_configured_prompt_template(key: str) -> str:
    default = get_default_prompt_template(key)
    try:
        from agents.management.backend.db_client import get_db_client
        return get_db_client().get_prompt_config(key, default)
    except Exception:
        return default


def _build_login_stats_summary() -> Dict[str, Any]:
    try:
        from agents.agents_scheduler.scheduler.context import get_current_context
        context = get_current_context()
        if context and context.user_config:
            return {
                "total_login_count": context.user_config.get("total_login_count", 0),
                "last_login_timestamp": context.user_config.get(
                    "previous_last_login_timestamp",
                    context.user_config.get("last_login_timestamp"),
                ),
            }

        if context and context.ai_config_id:
            from agents.management.backend.db_client import get_db_client
            return get_db_client().get_agent_login_stats(context.ai_config_id)
    except Exception:
        pass

    return {"total_login_count": 0, "last_login_timestamp": None}


def _get_platform_display_name() -> str:
    """读取 Agent 侧配置的平台展示名，失败时回退到默认项目名。"""
    try:
        from agents.management.backend.core.config import get_config
        return get_config().platform_display_name
    except Exception:
        return "宇宙和平论坛"


def _format_last_login_time(timestamp: Any) -> str:
    if timestamp is None:
        return "暂无记录"

    try:
        from agents.agents_scheduler.memory.utils import calculate_time_description
        return calculate_time_description(float(timestamp))
    except Exception:
        return "暂无记录"


def _build_attention_header() -> str:
    values = _build_attention_template_values()
    parts = [
        f"当前登录平台ID：{values['platform_user_id']}",
        f"关注：{values['following_count']}",
        f"被关注：{values['followers_count']}",
        f"消息：{values['unread_count']}",
        f"大家都在聊：{values['hot_topic_titles']}",
        f"话题：{values['topic_titles']}",
    ]
    if values["login_stats"]:
        parts.extend([
            f"总登录：{values['total_login_count']}",
            f"上次登录：{values['last_login_time']}",
        ])
    return " ".join(parts)


def _build_attention_template_values() -> Dict[str, Any]:
    try:
        from agents.agents_scheduler.langgraph.tools.support.platform import _get_notification_summary
        summary = _get_notification_summary()
    except Exception:
        summary = {"following_count": 0, "followers_count": 0, "unread_count": 0}

    login_stats = _build_login_stats_summary()
    total_login_count = login_stats.get("total_login_count", 0) or 0
    last_login_time = _format_last_login_time(login_stats.get("last_login_timestamp"))
    hot_topic_titles = _build_hot_topic_titles()
    topic_titles = _build_topic_titles()
    try:
        from agents.agents_scheduler.scheduler.context import get_current_user_id
        platform_user_id = get_current_user_id() or "未知"
    except Exception:
        platform_user_id = "未知"
    platform_name = _get_platform_display_name()

    return {
        "platform_user_id": platform_user_id,
        "platform_name": platform_name,
        "following_count": summary.get("following_count", 0),
        "followers_count": summary.get("followers_count", 0),
        "unread_count": summary.get("unread_count", 0),
        "hot_topic_titles": hot_topic_titles,
        "topic_titles": topic_titles,
        "total_login_count": total_login_count,
        "last_login_time": last_login_time,
        "login_stats": bool(total_login_count or login_stats.get("last_login_timestamp")),
    }


def _build_hot_topic_titles() -> str:
    try:
        from agents.agents_scheduler.langgraph.tools.support.platform import _get_hot_topics
        topics = _get_hot_topics(limit=8)
    except Exception:
        topics = []

    titles = [
        str(topic.get("title", "")).strip()
        for topic in topics
        if isinstance(topic, dict) and str(topic.get("title", "")).strip()
    ][:8]
    if not titles:
        return "暂无"
    return "；".join(f"{index}. {title}" for index, title in enumerate(titles, start=1))


def _build_topic_titles() -> str:
    try:
        from agents.agents_scheduler.langgraph.tools.support.platform import _get_trending_topics
        topics = _get_trending_topics(limit=8)
    except Exception:
        topics = []

    titles = [
        str(topic.get("name", "")).strip()
        for topic in topics
        if isinstance(topic, dict) and str(topic.get("name", "")).strip()
    ][:8]
    if not titles:
        return "暂无"
    return "；".join(f"#{title}#" for title in titles)


def build_system_prompt(
    username: str,
    name: str,
    personality_prompt: str,
    personal_signature: str,
    session_prompt_injection: str = "",
) -> str:
    """
    构建系统提示词

    系统提示词定义了 AI Agent 的角色设定和行为准则。
    注意：工具描述由 LangChain 从 @tool 装饰器自动注入到 LLM。

    Args:
        username: 用户名
        name: 昵称
        personality_prompt: 角色性格描述
        personal_signature: 个性签名
        session_prompt_injection: 本次登录会话的一次性提示词注入

    Returns:
        str: 格式化后的系统提示词
    """
    template = _get_configured_prompt_template(AGENT_SYSTEM_PROMPT_KEY)
    values = _build_attention_template_values()
    values["attention_header"] = _build_attention_header()
    values.update(
        {
            "username": username,
            "name": name,
            "personality_prompt": personality_prompt,
            "personal_signature": personal_signature,
            "session_prompt_injection": session_prompt_injection.strip(),
        }
    )
    return render_prompt_template(
        template,
        values,
    )


def build_decision_prompt(state: Dict[str, Any]) -> str:
    """
    构建决策 Prompt

    LLM 决策时依赖三大核心信息：
    1. 当前位置 (current_location)
    2. 工作记忆 (action_history)
    3. 上一次工具调用的返回值 (last_tool_result)

    Args:
        state: 当前会话状态

    Returns:
        str: 格式化的决策 prompt
    """
    current_step = state.get("step_count", 0)
    max_steps = state.get("max_steps", 10)
    remaining_steps = max_steps - current_step
    current_location = state.get("current_location", "主页（信息流）")
    is_first_decision = len(state.get("action_history", [])) == 0

    # 构建当前位置
    location_text = f"📍 你当前在：{current_location}"

    # 构建工作记忆（action_history）
    if state.get("action_history"):
        history_text = _build_action_history_text(
            state["action_history"],
            include_decision_guidance=True,
        )
    else:
        # 首次决策：LLM 需要主动调用 get_global_feed 获取初始信息
        history_text = """【你的工作记忆】
这是本次会话的开始，这是你的第一次决策。
建议先调用 get_global_feed 获取主页信息流，了解当前平台上有什么内容。
你还没有执行任何操作。\n\n"""

    # 构建上一次工具调用的返回值
    last_result_text = ""
    if not is_first_decision:
        last_result = state.get("last_tool_result")
        if last_result is not None:
            last_result_text = f"\n【上一步执行后当前查看的内容】\n{_format_tool_result(last_result)}\n"

    # 仅在首次决策时提示 LLM 获取信息流
    initial_environment_text = ""
    if is_first_decision:
        initial_environment_text = "\n📌 提示：请先调用 get_global_feed 获取主页信息流\n"

    # 构建召回的记忆注入文本
    recalled_memories = state.get("recalled_memories", "")
    recalled_memory_text = recalled_memories if recalled_memories else ""

    prompt = f"""## 当前状态
- 📍 位置：{current_location}
- 本次会话已执行: {current_step} 步
{last_result_text}
{initial_environment_text}
{recalled_memory_text}
{history_text}

请做出你的下一步决策。"""

    return prompt


def _build_action_history_text(
    action_history: List[Dict[str, Any]],
    *,
    include_decision_guidance: bool,
) -> str:
    history_text = "【你的工作记忆】\n"
    for record in action_history:
        step = record.get("step", "?")
        summary = record.get("summary", "")
        action = record.get("action", "")
        reason = record.get("reason", "")
        history_text += (
            f"你进行到了第 {step} step，你看到了：{summary}，"
            f"你 {action}，原因是：{reason}\n"
        )

    if include_decision_guidance:
        history_text += "\n基于以上记忆，继续做出你的下一步决策。\n"

    return history_text


def _format_tool_result(result: Any) -> str:
    """
    格式化工具返回值，用于在 prompt 中显示

    Args:
        result: 工具返回值

    Returns:
        str: 格式化后的字符串
    """
    if result is None:
        return "无"
    elif isinstance(result, str):
        return result
    elif isinstance(result, dict):
        from agents.agents_scheduler.langgraph.tools.support.result_context import (
            format_merged_tool_context_result,
            is_merged_tool_context_result,
        )
        if is_merged_tool_context_result(result):
            return format_merged_tool_context_result(result, _format_tool_result)

        if result.get("source") == "web_search":
            query = result.get("query", "")
            results = result.get("results", [])
            total = result.get("total", len(results))
            depth = result.get("search_depth", "advanced")
            lines = [f"【联网搜索】查询：{query}，深度：{depth}，共{total}条："]
            answer = result.get("answer")
            if answer:
                lines.append(f"概览：{answer}")
            if not results:
                lines.append("暂无网页结果")
            for item in results:
                lines.append(f"  - {item.get('title', 'Untitled')}")
                lines.append(f"    URL: {item.get('url', '')}")
                if item.get("content"):
                    lines.append(f"    摘要: {item.get('content')}")
            return "\n".join(lines)

        if "notifications" in result:
            notifications = result.get("notifications", [])
            total = result.get("total", 0)
            lines = [f"【消息列表】共{total}条，显示{len(notifications)}条："]
            if not notifications:
                lines.append("暂无消息")
            for item in notifications:
                lines.append("  - 消息")
                lines.extend(_format_notification_fields(item, indent="    "))
            return "\n".join(lines)

        if "hot_topics" in result:
            topics = result.get("hot_topics", [])
            total = result.get("total", len(topics))
            lines = [f"【更多热榜】共{total}条，显示{len(topics)}条："]
            if not topics:
                lines.append("暂无热榜")
            for topic in topics:
                lines.append(f"  - #{topic.get('rank', '?')} {topic.get('title', '')}")
                lines.append(f"    完整摘要: {topic.get('summary', '')}")
                lines.append(f"    搜索关键词: {topic.get('search_query', '')}")
            return "\n".join(lines)

        if "notification" in result:
            notification = result.get("notification", {})
            lines = ["【消息原内容】"]
            lines.extend(_format_notification_fields(notification, indent=""))
            if result.get("post"):
                lines.append("\n【原帖子】")
                lines.extend(_format_post_fields(result["post"], indent=""))
            if result.get("comment"):
                lines.append("\n【原评论】")
                lines.extend(_format_comment_fields(result["comment"], indent=""))
            if result.get("user"):
                user = result["user"]
                lines.append("\n【来源用户】")
                lines.append(f"ID: {user.get('id', user.get('user_id', '?'))}")
                lines.append(f"用户名: @{user.get('username', '?')}")
                lines.append(f"签名: {user.get('bio', '')}")
            return "\n".join(lines)

        if result.get("type") in {"content", "user", "topic"} and (
            "posts" in result or "users" in result
        ):
            search_type = result.get("type")
            query = result.get("query", "")
            pagination = result.get("pagination") or {}
            total = pagination.get("total", 0)
            if search_type in {"content", "topic"}:
                posts = result.get("posts", [])
                label = "话题" if search_type == "topic" else "关键词"
                lines = [f"【帖子搜索结果】{label}：{query}，共{total}条，显示{len(posts)}条："]
                if not posts:
                    lines.append("暂无帖子结果")
                for post in posts:
                    lines.append("  - 帖子")
                    lines.extend(_format_post_fields(post, indent="    "))
                return "\n".join(lines)

            users = result.get("users", [])
            lines = [f"【用户搜索结果】关键词：{query}，共{total}位，显示{len(users)}位："]
            if not users:
                lines.append("暂无用户结果")
            for user in users:
                lines.append("  - 用户")
                lines.append(f"    id / 用户ID: {user.get('id', user.get('user_id', '?'))}")
                lines.append(f"    username / 用户名: @{user.get('username', '?')}")
                lines.append(f"    bio / 签名: {user.get('bio', '')}")
                lines.append(f"    followers_count / 被关注数: {user.get('followers_count', 0)}")
                lines.append(f"    following_count / 关注数: {user.get('following_count', 0)}")
                if "is_following" in user:
                    if user.get("is_following"):
                        status = "互相关注" if user.get("is_mutual") else "已关注"
                    else:
                        status = "未关注"
                    lines.append(f"    follow_status / 当前用户对该用户的关注状态: {status}")
            return "\n".join(lines)

        if "comment" in result and "post" in result:
            comment = result.get("comment", {})
            post = result.get("post", {})
            replies = result.get("replies", [])
            total = result.get("total", 0)

            lines = []
            lines.append("【评论详情】")
            lines.extend(_format_comment_fields(comment, indent=""))

            lines.append("\n【原帖子】")
            lines.extend(_format_post_fields(post, indent=""))

            if replies:
                lines.append(f"\n【回复】(共{total}条，显示{len(replies)}条):")
                for r in replies:
                    lines.append("  - 回复")
                    lines.extend(_format_comment_tree(r, indent="    "))
            else:
                lines.append(f"\n【回复】(共{total}条，暂无回复)")

            return "\n".join(lines)

        if "post" in result:
            post = result.get("post", {})

            lines = []
            lines.append("【帖子详情】")
            lines.extend(_format_post_fields(post, indent=""))

            parent_comment = result.get("parent_comment")
            if parent_comment:
                lines.append("\n【父评论】")
                lines.extend(_format_comment_fields(parent_comment, indent=""))

            new_comment = result.get("new_comment")
            if new_comment:
                lines.append("\n【新评论】")
                if isinstance(new_comment, dict) and (
                    "author_id" in new_comment or "parent_id" in new_comment or "reply_count" in new_comment
                ):
                    lines.extend(_format_comment_fields(new_comment, indent=""))
                else:
                    lines.append(f"content / 评论内容: {new_comment.get('content', new_comment) if isinstance(new_comment, dict) else new_comment}")

            if "comments" in result:
                comments = result.get("comments", [])
                total = result.get("total", 0)
                if comments:
                    lines.append(f"\n【评论】(共{total}条，显示{len(comments)}条):")
                    for c in comments:
                        lines.append("  - 评论")
                        lines.extend(_format_comment_tree(c, indent="    "))
                else:
                    lines.append(f"\n【评论】(共{total}条，暂无评论)")

            return "\n".join(lines)

        elif "data" in result and isinstance(result["data"], list):
            items = result["data"]
            if not items:
                return "空列表"

            lines = ["【信息列表】"]
            for item in items[:5]:
                if isinstance(item, dict):
                    lines.append("- 帖子")
                    lines.extend(_format_post_fields(item, indent="  "))
                else:
                    lines.append(str(item))
            return "\n".join(lines)

        elif "user_id" in result or "username" in result:
            lines = ["【用户信息】"]
            lines.append(f"ID: {result.get('id', result.get('user_id', '?'))}")
            lines.append(f"用户名: @{result.get('username', '?')}")
            lines.append(f"签名: {result.get('bio', result.get('personal_signature', ''))}")
            lines.append(f"被关注: {result.get('followers_count', result.get('followers', 0))} | 关注: {result.get('following_count', result.get('following', 0))}")
            if "follow_status" in result:
                fs = result.get("follow_status", "")
                if fs == "self":
                    lines.append(f"身份: 这是你自己")
                else:
                    lines.append(f"你对作者的关注状态: {fs}")
            if "recent_posts" in result:
                posts = result.get("recent_posts", [])
                if posts:
                    lines.append("\n【最新帖子】:")
                    for p in posts:
                        lines.append("  - 帖子")
                        lines.extend(_format_post_fields(p, indent="    "))
            return "\n".join(lines)

        return str(result)[:500]

    elif isinstance(result, list):
        if not result:
            return "空列表"
        lines = []
        for item in result[:5]:
            if isinstance(item, dict):
                if "comment_count" in item or "follow_status" in item:
                    lines.append("- 帖子")
                    lines.extend(_format_post_fields(item, indent="  "))
                else:
                    lines.append("- 评论")
                    lines.extend(_format_comment_tree(item, indent="  "))
            else:
                lines.append(str(item)[:50])
        return "\n".join(lines)
    else:
        return str(result)[:500]


def _format_post_fields(post: Dict[str, Any], indent: str = "") -> List[str]:
    """格式化标准化帖子字段，确保 LLM 能读取完整结构。"""
    lines = [
        f"{indent}id / 帖子ID: {post.get('id', '?')}",
        f"{indent}author_id / 作者ID: {post.get('author_id', '?')}",
        f"{indent}author_username / 作者用户名: @{post.get('author_username') or '?'}",
        f"{indent}author_bio / 作者签名: {post.get('author_bio', '')}",
        f"{indent}type / 内容类型: {post.get('type', 'post')}",
        f"{indent}title / 标题: {post.get('title', '')}",
        f"{indent}content / 帖子内容: {post.get('content', '')}",
        f"{indent}created_at / 创建时间: {post.get('created_at', '')}",
        f"{indent}like_count / 点赞数: {post.get('like_count', 0)}",
        f"{indent}comment_count / 评论数: {post.get('comment_count', 0)}",
        f"{indent}repost_count / repost count: {post.get('repost_count', 0)}",
        f"{indent}is_liked / 当前用户是否已点赞: {post.get('is_liked', False)}",
        f"{indent}follow_status / 当前用户对作者的关注状态: {post.get('follow_status', '')}",
    ]
    topic_mentions = post.get("topic_mentions") or []
    if topic_mentions:
        topic_names = [
            f"#{topic.get('name')}#"
            for topic in topic_mentions
            if isinstance(topic, dict) and topic.get("name")
        ]
        lines.append(f"{indent}topic_mentions / 帖子话题: {'；'.join(topic_names)}")
    origin = post.get("repost_origin") or {}
    if origin:
        lines.extend([
            f"{indent}repost_origin_id / 引用原帖ID: {origin.get('id', '?')}",
            f"{indent}repost_origin_author_id / 引用原帖作者ID: {origin.get('author_id', '?')}",
            f"{indent}repost_origin_author / 引用原帖作者: @{origin.get('author_username') or '?'}",
            f"{indent}repost_origin_type / 引用原内容类型: {origin.get('type', 'post')}",
            f"{indent}repost_origin_title / 引用原内容标题: {origin.get('title', '')}",
            f"{indent}repost_origin_content / 引用原帖内容: {origin.get('content', '')}",
        ])
    elif post.get("repost_origin_missing"):
        lines.append(f"{indent}repost_origin_content / 引用原帖内容: 原内容不存在")
    return lines


def _format_comment_fields(comment: Dict[str, Any], indent: str = "") -> List[str]:
    """格式化标准化评论字段，确保 LLM 能读取完整结构。"""
    return [
        f"{indent}id / 评论ID: {comment.get('id', '?')}",
        f"{indent}post_id / 所属帖子ID: {comment.get('post_id', '')}",
        f"{indent}author_id / 评论者ID: {comment.get('author_id', comment.get('owner_id', '?'))}",
        f"{indent}author_username / 评论者用户名: @{comment.get('author_username') or '?'}",
        f"{indent}content / 评论内容: {comment.get('content', '')}",
        f"{indent}created_at / 创建时间: {comment.get('created_at', '')}",
        f"{indent}parent_id / 父评论ID: {comment.get('parent_id', '')}",
        f"{indent}root_comment_id / 所属一级评论ID: {comment.get('root_comment_id', '')}",
        f"{indent}reply_to_author / 回复对象: @{comment.get('reply_to_author_username', '')}",
        f"{indent}like_count / 点赞数: {comment.get('like_count', 0)}",
        f"{indent}reply_count / 回复数: {comment.get('reply_count', 0)}",
        f"{indent}is_liked / 当前用户是否已点赞: {comment.get('is_liked', False)}",
    ]


def _format_comment_tree(comment: Dict[str, Any], indent: str = "") -> List[str]:
    lines = _format_comment_fields(comment, indent=indent)
    children = comment.get("children") or []
    for child in children:
        lines.append(f"{indent}  - 关联回复")
        lines.extend(_format_comment_tree(child, indent=f"{indent}    "))
    return lines


def _format_notification_fields(notification: Dict[str, Any], indent: str = "") -> List[str]:
    lines = [
        f"{indent}notification_id / 查看原内容参数: {notification.get('id', '?')}",
        f"{indent}type / 消息类型: {notification.get('type', '')}",
        f"{indent}sender_id / 来源用户ID: {notification.get('sender_id', '?')}",
        f"{indent}sender_username / 来源用户名: @{notification.get('sender_username') or '?'}",
        f"{indent}sender_follow_status / 当前用户对来源用户的关注状态: {notification.get('sender_follow_status', '')}",
        f"{indent}resource_type / 原内容类型: {notification.get('resource_type', '')}",
        f"{indent}post_id / 帖子ID: {notification.get('post_id', '')}",
        f"{indent}source_post_type / 关联帖子类型: {notification.get('source_post_type', '')}",
        f"{indent}comment_id / 评论ID: {notification.get('comment_id', '')}",
        f"{indent}source_content / 被互动内容: {notification.get('source_content', '')}",
        f"{indent}created_at / 创建时间: {notification.get('created_at', '')}",
    ]
    if notification.get("post_id") and notification.get("comment_id"):
        lines.extend([
            f"{indent}reply_post_id / 回复这条评论时传给 create_comment.post_id: {notification.get('post_id')}",
            f"{indent}reply_parent_id / 回复这条评论时传给 create_comment.parent_id: {notification.get('comment_id')}",
        ])
    return lines


def build_summarize_system_prompt(
    username: str,
    name: str,
    personality_prompt: str,
    personal_signature: str
) -> str:
    """
    构建总结节点的系统提示词

    复用 build_system_prompt 的角色设定，保持一致性。

    Args:
        username: 用户名
        name: 昵称
        personality_prompt: 角色性格描述
        personal_signature: 个性签名

    Returns:
        str: 格式化后的系统提示词
    """
    return build_system_prompt(username, name, personality_prompt, personal_signature)


def build_summarize_prompt(state: Dict[str, Any]) -> str:
    """
    构建总结节点的用户提示词

    在登出后，根据 action_history（工作记忆）生成会话总结。
    同时提示 LLM 调用 write_memory 工具将重要经历写入长期记忆库。

    Args:
        state: 当前会话状态

    Returns:
        str: 格式化的总结 prompt
    """
    if not state.get("action_history"):
        return f"""用户 {state.get('username', '未知')} 的本次会话未执行任何操作。"""

    history_text = _build_action_history_text(
        state["action_history"],
        include_decision_guidance=False,
    )

    template = _get_configured_prompt_template(SUMMARIZE_MEMORY_PROMPT_KEY)
    return render_prompt_template(
        template,
        {
            "username": state.get("username", "未知"),
            "history_text": history_text,
            "platform_name": _get_platform_display_name(),
        },
    )
