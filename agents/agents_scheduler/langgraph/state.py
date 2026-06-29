# 状态类型定义模块
# 定义 LangGraph 会话状态的数据结构，包括状态类型、退出原因、操作记录等
from typing import TypedDict, List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


class ExitReason(str, Enum):
    """
    会话退出原因枚举

    描述导致登录会话终止的原因，用于追踪和分析 AI Agent 的行为模式。
    """
    USER_CHOICE = "user_choice"           # LLM 主动选择登出
    MAX_STEPS_REACHED = "max_steps"      # 达到最大步数限制
    ERROR = "error"                      # 执行错误导致退出


class ActionRecord(TypedDict):
    """
    单条操作记录

    工作记忆的核心组成部分。记录 LLM 执行的每个操作。

    设计要点：
    - step: 步骤编号，让 LLM 知道执行到第几步
    - summary: 对当前视野的第一人称总结，让 LLM 知道自己"看到了什么"
    - action: 自然语言格式的动作描述，如 "点赞了 @用户 的帖子"
    - reason: LLM 调用该工具的具体原因

    注意：工具返回值不存储在这里，而是在 SessionState.last_tool_result 中，
    在下一次决策时作为上下文显示给 LLM。

    Attributes:
        step: 步骤编号，从 1 开始递增
        timestamp: 操作执行时的 ISO 格式时间戳
        summary: 对当前视野的第一人称总结
        action: 自然语言格式的动作描述
        reason: LLM 调用该工具的具体原因
    """
    step: int                              # 步骤编号
    timestamp: str                          # ISO 格式时间戳
    summary: str                            # 对当前视野的第一人称总结
    action: str                             # 自然语言格式的动作描述
    reason: str                             # 调用原因


class SessionState(TypedDict):
    """
    LangGraph 会话状态

    这是贯穿整个图结构的核心状态对象，在每个节点之间传递。
    包含了身份信息、会话控制、工作记忆、当前位置等。

    设计要点：
    - 身份信息在初始化时设置，之后不可更改
    - action_history 是工作记忆，让 LLM 知道自己做了什么决策
    - last_tool_result 是上一次工具调用的完整返回值，给下一次决策看
    - current_location 追踪 LLM 当前所在的"页面"
    - pending_tool 在 LLM 决策后设置，在工具执行后清空
    - summary 在会话结束时由总结节点生成

    工作记忆机制：
    - action_history: 记录每次决策的动机（reason），登出后用于总结
    - last_tool_result: 工具调用的完整返回值，下一次决策时作为上下文

    Attributes:
        user_id: 用户 ID，对应平台中的唯一标识符
        username: 用户名，用于显示和识别
        agent_id: AI 配置 ID，对应 ai_users_config.json 中的 id
        personality_prompt: 角色性格描述，用于构建 LLM 的系统提示词
        personal_signature: 个性签名，用户的简短自我介绍
        session_prompt_injection: 本次登录会话的一次性提示词注入

        step_count: 当前已执行的步数，用于控制最大步数限制
        max_steps: 最大步数限制，防止无限循环
        exit_reason: 退出原因，None 表示会话仍在进行中

        action_history: 操作历史列表，作为工作记忆记录所有执行过的操作（不含返回值）
        current_location: LLM 当前所在的"页面"，如"主页"、"帖子详情页"等

        last_tool_result: 上一次工具调用的完整返回值，给下一次决策看

        pending_tool: 待执行的工具调用，由 LLM 决策节点设置
        last_error: 最近一次错误信息，用于错误处理和恢复

        summary: 会话总结，登出后由总结节点生成，准备写入 RAG 记忆库
    """
    # === 身份信息（初始化时设置，过程中不可更改）===
    user_id: int                            # 用户 ID
    username: str                            # 用户名（登录用）
    name: str                               # 昵称（显示用）
    agent_id: int                       # AI 配置 ID
    personality_prompt: str                  # 角色性格描述
    personal_signature: str                   # 个性签名
    session_prompt_injection: str             # 本次会话的一次性提示词注入

    # === 会话控制 ===
    step_count: int                          # 当前步数
    max_steps: int                           # 最大步数限制
    exit_reason: Optional[ExitReason]        # 退出原因

    # === 工作记忆（核心）===
    # 记录 LLM 的决策动机，登出后用于总结
    action_history: List[ActionRecord]

    # === 当前位置 ===
    # 追踪 LLM 当前所在的"页面"，是做出下一步决策的关键上下文
    current_location: str

    # === 上一次工具返回值（给下一次决策看）===
    # 工具调用的完整返回值，在下一次决策时作为上下文显示
    last_tool_result: Optional[Union[Dict[str, Any], List, str, int, bool]]

    # === LLM 决策上下文 ===
    pending_tool: Optional[Dict[str, Any]]    # 待执行的单个工具调用（兼容旧逻辑）
    pending_tools: Optional[List[Dict[str, Any]]]  # 待执行的批量工具调用
    last_error: Optional[str]                 # 最近一次错误信息

    # === 输出 ===
    summary: Optional[str]                   # 会话总结

    # === 记忆系统 ===
    recalled_memories: Optional[str]          # 召回的记忆注入文本


class SessionSummary(TypedDict):
    """
    会话总结

    在会话结束时生成，用于：
    1. 提供给 RAG 记忆库进行存储
    2. 用于后续会话的上下文参考
    3. 用于行为分析和统计

    Attributes:
        session_id: 会话唯一标识符
        user_id: 用户 ID
        username: 用户名
        agent_id: AI 配置 ID
        start_time: 会话开始时间
        end_time: 会话结束时间
        duration_seconds: 会话持续时长（秒）
        step_count: 执行的总步数
        exit_reason: 退出原因
        actions: 操作记录列表
        narrative: LLM 生成的叙事性总结
    """
    session_id: str                          # 会话唯一标识符
    user_id: int                             # 用户 ID
    username: str                            # 用户名
    agent_id: int                        # AI 配置 ID
    start_time: str                          # 会话开始时间（ISO 格式）
    end_time: str                            # 会话结束时间（ISO 格式）
    duration_seconds: float                  # 会话持续时长（秒）
    step_count: int                          # 执行的总步数
    exit_reason: str                         # 退出原因
    actions: List[Dict[str, Any]]            # 操作记录列表
    narrative: str                            # LLM 生成的叙事性总结
