# 记忆工具函数
# 包含与记忆操作相关的工具
# 注意：write_memory 工具应该仅在总结节点中绑定给 LLM，而不是随其他工具一起绑定

from typing import Optional, Dict, Any, List

from langchain_core.tools import tool

from agents.agents_scheduler.scheduler.context import get_current_user_id
from agents.agents_scheduler.memory.service import get_memory_service
from agents.agents_scheduler.memory.config import get_memory_config
from agents.agents_scheduler.langgraph.tools.types import ToolResult


@tool
def write_memory(
    memories: list,
    reason: str = "用户想要将重要经历写入长期记忆",
    summary: str = ""
) -> ToolResult:
    """
    将记忆写入长期记忆库

    【重要！】注意！如果提示词中未提及调用此工具，此工具严禁被调用！

    进入总结节点后，提示词提示LLM 调用此工具将本次会话的重要经历写入记忆库。
    LLM 将总结内容分成 n 个语义完整的记忆片段，一次性传入。

    注意：
    - 每条记忆应以"我"为主语，第一人称描述
    - 每次调用可写入多条记忆，每条记忆分块上限300字，每个分块都必须有完整的上下文叙事与人际关系叙事。
    - memories 是一个列表，每个元素是一个字典，包含 content 和 memory_coefficient

    Args:
        memories: 记忆列表，每个元素是 {"content": "记忆内容", "memory_coefficient": 0.85}
        reason: 调用原因
        summary: 对当前视野的第一人称总结

    Returns:
        ToolResult: 包含操作结果和记忆ID列表
    """
    owner_id = get_current_user_id()
    config = get_memory_config()

    if not config.memory_enabled:
        return ToolResult(
            action="记忆系统未启用，无法写入",
            data={"memory_ids": []}
        )

    try:
        service = get_memory_service()
        import asyncio
        
        memory_ids = []
        for mem in memories:
            content = mem.get("content", "")
            coefficient = mem.get("memory_coefficient", 0.85)
            
            if not content:
                continue
                
            memory_id = asyncio.run(service.write_memory(
                content=content,
                owner_id=owner_id,
                memory_coefficient=coefficient
            ))
            memory_ids.append(memory_id)
        
        return ToolResult(
            action=f"将{len(memory_ids)}条记忆写入长期记忆库",
            data={"memory_ids": memory_ids}
        )
    except Exception as e:
        return ToolResult(
            action=f"记忆写入失败: {str(e)}",
            data={"memory_ids": []}
        )
