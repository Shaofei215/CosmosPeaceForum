# Prompt 模板模块
# 定义 LangGraph 会话中使用的各种 Prompt 模板
# 注意：工具描述由 LangGraph/LangChain 自动注入，无需在 prompt 中重复
from typing import Dict, Any


def build_system_prompt(
    username: str,
    name: str,
    personality_prompt: str,
    personal_signature: str
) -> str:
    """
    构建系统提示词

    系统提示词定义了 AI Agent 的角色设定和行为准则。
    注意：工具描述由 LangGraph 自动从 @tool 装饰器注入。

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
2. 真实性：像真人一样浏览、点赞、评论，而不是机械执行任务
3. 选择性：不必阅读所有内容，选择你最感兴趣的

## 工作记忆
你会收到一个 action_history 列表，记录了你在本次会话中已经执行的操作。
这是你的"记忆"，通过它你知道：
- 已经执行到第几步
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
        history_text = "【你的工作记忆】\n你已经在本次会话中执行了以下操作：\n"
        for record in state["action_history"]:
            history_text += f"  步骤 {record['step']}: 你调用了 {record['tool_name']}\n"
            history_text += f"    原因：{record['reason']}\n"
        history_text += "\n基于以上记忆，继续做出你的下一步决策。\n"
    else:
        # 首次决策：从环境信息获取粉丝数、关注数
        env = state.get("environment", {})
        profile = env.get("profile", {})
        followers = profile.get("followers_count", 0)
        following = profile.get("following_count", 0)
        history_text = f"""【你的工作记忆】
这是本次会话的开始，你的信息：
- 粉丝数: {followers}
- 关注数: {following}
你还没有执行任何操作。\n\n"""

    # 构建上一次工具调用的返回值
    last_result_text = ""
    if not is_first_decision:
        last_result = state.get("last_tool_result")
        if last_result is not None:
            last_result_text = f"\n【上一步执行后当前查看的内容】\n{_format_tool_result(last_result)}\n"

    # 仅在首次决策时显示初始环境信息（粉丝数、关注数已放在工作记忆中）
    initial_environment_text = ""
    if is_first_decision:
        env = state.get("environment", {})
        feed = env.get("feed", [])

        if feed:
            initial_environment_text = """【首页帖子】
"""
            if feed:
                for i, post in enumerate(feed, 1):
                    content_preview = post.get("content", "")[:60]
                    author = post.get("author_username", "未知")
                    post_id = post.get("id", "?")
                    initial_environment_text += f"{i}. 帖子ID:{post_id} @{author}: {content_preview}...\n"
            else:
                initial_environment_text += "暂无帖子\n"

    prompt = f"""## 当前状态
- 📍 位置：{current_location}
- 本次会话已执行: {current_step} 步，剩余: {remaining_steps} 步
{last_result_text}
{initial_environment_text}
{history_text}

## 决策要求
1. 根据你的角色性格做出符合人设的决策
2. 结合当前位置和工作记忆做出合理选择
3. 每次决策最多选择一个工具
4. 记住你之前的操作，避免重复操作
5. 思考你的决策理由，这将记录到工作记忆中

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
        if "data" in result and isinstance(result["data"], list):
            items = result["data"]
            if not items:
                return "空列表"
            formatted_items = []
            for item in items[:5]:
                if isinstance(item, dict):
                    content = item.get("content", "")[:50]
                    author = item.get("author_username", "未知")
                    formatted_items.append(f"@{author}: {content}...")
                else:
                    formatted_items.append(str(item)[:50])
            return "\n".join(formatted_items)
        return str(result)[:500]
    elif isinstance(result, list):
        if not result:
            return "空列表"
        return "\n".join([str(item)[:100] for item in result[:5]])
    else:
        return str(result)[:500]


def build_summarize_prompt(state: Dict[str, Any]) -> str:
    """
    构建总结 Prompt

    在登出后，根据 action_history（工作记忆）生成会话总结。

    Args:
        state: 当前会话状态

    Returns:
        str: 格式化的总结 prompt
    """
    if not state.get("action_history"):
        return f"""用户 {state.get('username', '未知')} 的本次会话未执行任何操作。"""

    history_text = ""
    for r in state["action_history"]:
        history_text += f"- 步骤 {r['step']}: {r['tool_name']}\n"
        history_text += f"  原因: {r['reason']}\n"

    tool_counts: Dict[str, int] = {}
    for record in state["action_history"]:
        tool_name = record["tool_name"]
        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    stats_text = "\n".join([
        f"  - {tool}: {count} 次"
        for tool, count in tool_counts.items()
    ])

    prompt = f"""我是一个社交平台用户，名叫 {state.get('username', '未知')}。

我的角色设定：{state.get('personality_prompt', '')[:100]}...

本次会话我的操作：
{history_text}

请以"我"第一人称生成一段总结，描述我在这次会话中的活动和感受。
100-200字。"""

    return prompt
