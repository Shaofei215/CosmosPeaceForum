# Prompt 模板模块
# 定义 LangGraph 会话中使用的各种 Prompt 模板
from typing import Dict, Any, List


def build_system_prompt(
    username: str,
    name: str,
    personality_prompt: str,
    personal_signature: str
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

    Returns:
        str: 格式化后的系统提示词
    """
    prompt = f"""你是{name}，一个「星际和平论坛」用户，正在使用「星际和平论坛」，用户名 {username}。

## 角色背景
{personality_prompt}

## 个人签名
"{personal_signature}"

## 行为准则
1. 保持角色一致性：你的所有行为和言论都应该符合角色设定，但可视情况激发创造性
2. 真实性：像真人一样浏览、点赞、评论、关注、发帖...自由决策，而不是机械执行任务
3. 选择性：不必阅读所有内容，选择你最感兴趣的
4. **工具使用【重要】**：每个参数都是必填项！请务必确保参数齐全且准确！禁止编造不存在的参数、ID！**支持批量工具调用**，但每次只能使用一个获取信息型工具。
5. 互动优先级与字数限制：点赞>评论，评论仅在想要表达观点时使用；评论字数50字以下为宜，发帖字数100字以下为宜，不准滥用emoji！


## 工作记忆
你会收到一个 action_history 列表，记录了你在本次会话中已经执行的操作。
这是你的"记忆"，通过它你知道：
- 之前做了什么操作
- 每个操作的决策原因

请结合你的记忆做出下一步决策。

## 登出决策
当你觉得"今天差不多了"时，选择 logout 工具结束会话。
不要沉迷于无限浏览，适可而止是健康使用社交平台的表现。"""

    return prompt


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
    history_text = ""
    if state.get("action_history"):
        history_text = "【你的工作记忆】\n"
        for record in state["action_history"]:
            step = record.get("step", "?")
            summary = record.get("summary", "")
            action = record.get("action", "")
            reason = record.get("reason", "")
            history_text += f"你进行到了第 {step} step，你看到了：{summary}，你 {action}，原因是：{reason}\n"
        history_text += "\n基于以上记忆，继续做出你的下一步决策。\n"
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
        if "post" in result:
            post = result.get("post", {})
            comments = result.get("comments", [])
            total = result.get("total", 0)

            lines = []
            lines.append("【帖子详情】")
            lines.append(f"ID: {post.get('id', '?')}")
            lines.append(f"作者: @{post.get('author_username', '?')}")
            lines.append(f"作者签名: {post.get('author_bio', '')}")
            lines.append(f"内容: {post.get('content', '')}")
            lines.append(f"点赞: {post.get('like_count', 0)} | 评论数: {post.get('comment_count', 0)} | 已点赞: {post.get('is_liked', False)}")
            lines.append(f"发布时间: {post.get('created_at', '')}")
            if post.get("follow_status"):
                lines.append(f"关注状态: {post.get('follow_status', '')}")

            if comments:
                lines.append(f"\n【评论】(共{total}条，显示{len(comments)}条):")
                for c in comments:
                    author_id = c.get("author_id", c.get("owner_id", "?"))
                    created = c.get('created_at', '')[:19] if c.get('created_at') else ''
                    lines.append(f"  [评论ID:{c.get('id', '?')}] @{c.get('author_username', '?')} (作者ID:{author_id}) [{created}]: {c.get('content', '')}")
                    lines.append(f"    点赞:{c.get('like_count', 0)} | 回复:{c.get('reply_count', 0)} | 已点赞:{c.get('is_liked', False)}")
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
                    author_id = item.get("author_id", "?")
                    lines.append(f"[ID:{item.get('id', '?')}] @{item.get('author_username', '?')} (作者ID:{author_id}): {item.get('content', '')[:50]}...")
                    lines.append(f"  点赞:{item.get('like_count', 0)} | 评论:{item.get('comment_count', 0)} | 已点赞:{item.get('is_liked', False)}")
                    if item.get("follow_status"):
                        lines.append(f"  关注状态:{item.get('follow_status', '')}")
                else:
                    lines.append(str(item))
            return "\n".join(lines)

        elif "comment" in result and "post" in result:
            comment = result.get("comment", {})
            post = result.get("post", {})
            replies = result.get("replies", [])
            total = result.get("total", 0)

            lines = []
            lines.append("【评论详情】")
            comment_author_id = comment.get("author_id", comment.get("owner_id", "?"))
            comment_created = comment.get('created_at', '')[:19] if comment.get('created_at') else ''
            lines.append(f"[评论ID:{comment.get('id', '?')}] @{comment.get('author_username', '?')} (作者ID:{comment_author_id}) [{comment_created}]: {comment.get('content', '')}")
            lines.append(f"  点赞:{comment.get('like_count', 0)} | 回复:{comment.get('reply_count', 0)} | 已点赞:{comment.get('is_liked', False)}")

            lines.append(f"\n【原帖子】ID:{post.get('id', '?')} @{post.get('author_username', '?')}: {post.get('content', '')[:50]}...")

            if replies:
                lines.append(f"\n【回复】(共{total}条，显示{len(replies)}条):")
                for r in replies:
                    reply_author_id = r.get("author_id", r.get("owner_id", "?"))
                    reply_created = r.get('created_at', '')[:19] if r.get('created_at') else ''
                    lines.append(f"  [ID:{r.get('id', '?')}] @{r.get('author_username', '?')} (作者ID:{reply_author_id}) [{reply_created}]: {r.get('content', '')}")
            else:
                lines.append(f"\n【回复】(共{total}条，暂无回复)")

            return "\n".join(lines)

        elif "user_id" in result or "username" in result:
            lines = ["【用户信息】"]
            lines.append(f"ID: {result.get('id', result.get('user_id', '?'))}")
            lines.append(f"用户名: @{result.get('username', '?')}")
            lines.append(f"签名: {result.get('bio', result.get('personal_signature', ''))}")
            lines.append(f"粉丝: {result.get('followers_count', result.get('followers', 0))} | 关注: {result.get('following_count', result.get('following', 0))}")
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
                        lines.append(f"  [ID:{p.get('id', '?')}] {p.get('content', '')[:50]}...")
            return "\n".join(lines)

        return str(result)[:500]

    elif isinstance(result, list):
        if not result:
            return "空列表"
        lines = []
        for item in result[:5]:
            if isinstance(item, dict):
                author_id = item.get("author_id", item.get("owner_id", "?"))
                created = item.get('created_at', '')[:19] if item.get('created_at') else ''
                lines.append(f"[ID:{item.get('id', '?')}] @{item.get('author_username', '?')} (作者ID:{author_id}) [{created}]: {item.get('content', '')[:50]}...")
                if "like_count" in item:
                    lines.append(f"  点赞:{item.get('like_count', 0)} | 回复:{item.get('reply_count', 0)} | 已点赞:{item.get('is_liked', False)}")
            else:
                lines.append(str(item)[:50])
        return "\n".join(lines)
    else:
        return str(result)[:500]


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

    history_text = ""
    for r in state["action_history"]:
        step = r.get("step", "?")
        summary = r.get("summary", "")
        action = r.get("action", "")
        reason = r.get("reason", "")
        history_text += f"- 第 {step} step：你看到了 {summary}，你 {action}，原因是 {reason}\n"

    tool_counts: Dict[str, int] = {}
    for record in state["action_history"]:
        action = record.get("action", "")
        if action:
            tool_counts[action] = tool_counts.get(action, 0) + 1

    stats_text = "\n".join([
        f"  - {action}: {count} 次"
        for action, count in tool_counts.items()
    ])

    prompt = f"""本次会话你的操作：
{history_text}

## 记忆写入指令

你刚刚结束了在「星际和平论坛」的会话。请根据本次会话的操作历史，调用 write_memory 工具
生成你认为有必要的 n 条记忆片段，写入你的长期记忆库。

要求：
1. 每条记忆以"我"为主语，第一人称描述
2. 内容应包含：你看到了什么、你做了什么、你的感受或想法
3. 单条记忆长度 50-200 字
4. 记忆应是语义完整独立单元
"""

    return prompt
