"""
Management Backend - 记忆管理路由
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

import jieba
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from agents.management.backend.core.database import get_db
from agents.management.backend.api.deps import get_current_admin
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.models.agent_config import AgentConfig
from agents.management.backend.services.log_service import create_log
from agents.management.backend.services.chunk_model_service import get_active_chunk_model_config

logger = logging.getLogger(__name__)

router = APIRouter()

MEMORY_SERVICE = None
MEMORY_DB = None


def _get_memory_service():
    """延迟获取记忆服务实例"""
    global MEMORY_SERVICE, MEMORY_DB
    if MEMORY_SERVICE is None:
        from agents.agents_scheduler.memory.service import get_memory_service
        from agents.agents_scheduler.memory.database import MemoryDB
        from agents.agents_scheduler.memory.config import get_memory_config
        MEMORY_SERVICE = get_memory_service()
        MEMORY_DB = MemoryDB(get_memory_config())
    return MEMORY_SERVICE, MEMORY_DB


def _auto_chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """
    自动分块文本（基于 jieba 中文分词）

    中文按词语（非单字）计为 token，英文按单词计，标点符号各计 1 token。
    每个分块最大 chunk_size tokens，相邻分块重叠 overlap tokens。
    分块边界保证在完整词语处，不会切断词语。

    Args:
        text: 原始文本
        chunk_size: 每块大小（tokens），默认 512
        overlap: 重叠大小（tokens），默认 50

    Returns:
        list[str]: 分块后的文本列表
    """
    # 使用 jieba 精确模式分词，保证词语完整性
    words = list(jieba.cut(text))

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunks.append(''.join(chunk_words))

        if end >= len(words):
            break

        start = end - overlap
        if start < 0:
            start = 0

    return chunks


@tool
def chunk_memories(memories: list[dict]) -> list[dict]:
    """
    将文本拆分为多个记忆片段

    规则：
    - 每条记忆以"我"为主语，第一人称描述
    - 每条记忆上限 512 tokens
    - 每个分块是独立的语义单元，包含完整的故事上下文和人物关系叙事

    Args:
        memories: 记忆列表，每个元素是 {"content": "记忆内容", "memory_coefficient": 0.85}

    Returns:
        list[dict]: 分块后的记忆列表
    """
    return memories


async def _llm_smart_chunk(
    text: str,
    owner_id: int,
    personality_prompt: str,
    semantic_timestamp: float,
    memory_coefficient: float,
    db: Session,
) -> list[dict]:
    """
    使用 LangChain Tool 调用进行智能分块

    Args:
        text: 原始文本
        owner_id: 记忆所有者 ID
        personality_prompt: 角色个性提示词
        semantic_timestamp: 语义时间戳
        memory_coefficient: 默认记忆系数
        db: 数据库会话

    Returns:
        list[dict]: 分块列表 [{"content": "...", "memory_coefficient": 0.85}, ...]
    """
    chunk_model_config = get_active_chunk_model_config(db)
    if not chunk_model_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未配置或未启用分块模型，请先在模型配置页的分块模型配置中添加并启用"
        )

    system_prompt = """你是一个记忆分块助手。请根据人物信息，将提供的文本拆分为多个语义完整的、符合角色设定的第一人称记忆片段。

【分块规则】
1. 每条记忆必须以"我"为主语，使用第一人称叙述，包含符合角色视角的叙事、表达、看法与情感
2. 每条记忆上限 512 tokens
3. 每个分块应是一个独立的语义单元，包含完整的上下文和人物关系叙事

请调用 chunk_memories 工具，一次性传入所有分块后的记忆列表。"""

    user_prompt = f"""【角色设定】
{personality_prompt}

【待分块文本】
{text}

请按照规则进行分块，并调用 chunk_memories 工具传入结果。"""

    try:
        llm_kwargs = {
            "model": chunk_model_config.model_name,
            "temperature": chunk_model_config.temperature,
            "max_tokens": chunk_model_config.max_token,
            "api_key": chunk_model_config.api_key,
        }
        base_url = chunk_model_config.base_url.rstrip('/')
        if base_url:
            llm_kwargs["base_url"] = base_url

        llm = ChatOpenAI(**llm_kwargs)
        llm_with_tools = llm.bind_tools([chunk_memories])

        response = llm_with_tools.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        if not response.tool_calls:
            logger.error("LLM 未调用工具，返回内容: %s", response.content)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM 未返回有效的工具调用结果"
            )

        tool_call = response.tool_calls[0]
        memories = tool_call["args"].get("memories", [])

        if not memories:
            logger.error("LLM 工具调用返回空记忆列表")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM 未返回有效的分块结果"
            )

        return memories

    except HTTPException:
        raise
    except Exception as e:
        logger.error("LLM 分块错误: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM 分块失败: {str(e)}"
        )


@router.get("/", response_model=dict)
def list_memories(
    skip: int = 0,
    limit: int = 100,
    owner_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取记忆列表"""
    _, memory_db = _get_memory_service()

    if owner_id:
        all_memories = memory_db._get_user_memories_sync(owner_id)
    else:
        all_memories = memory_db._get_all_memories_sync()

    # 获取 agent 用户名映射
    agent_stmt = select(AgentConfig)
    agents = db.exec(agent_stmt).all()
    agent_map = {a.app_platform_user_id: a.name for a in agents if a.app_platform_user_id}

    total = len(all_memories)
    sliced = all_memories[skip:skip + limit]

    items = []
    for chunk in sliced:
        items.append({
            "id": chunk.id,
            "owner_id": chunk.owner_id,
            "owner_username": agent_map.get(chunk.owner_id, f"User-{chunk.owner_id}"),
            "content": chunk.content,
            "semantic_timestamp": chunk.semantic_timestamp,
            "system_timestamp": chunk.timestamp,
            "memory_coefficient": chunk.memory_coefficient,
        })

    return {"items": items, "total": total}


@router.post("/upload", response_model=dict)
async def upload_memory(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """
    上传记忆（单角色，支持自动分块与 LLM 智能分块）

    请求体:
    {
        "owner_id": 1,
        "content": "长文本...",
        "semantic_time": "2023-01-15T10:30:00",
        "memory_coefficient": 0.85,        // 仅自动分块模式需要
        "chunk_mode": "auto" | "llm",
        "personality_prompt": "..."         // 仅 LLM 分块模式需要
    }
    """
    owner_id = request.get("owner_id")
    content = request.get("content", "").strip()
    semantic_time = request.get("semantic_time", "")
    chunk_mode = request.get("chunk_mode", "auto")

    if not owner_id:
        raise HTTPException(status_code=400, detail="owner_id 不能为空")
    if not content:
        raise HTTPException(status_code=400, detail="记忆内容不能为空")

    # 解析语义时间
    try:
        if semantic_time:
            dt = datetime.fromisoformat(semantic_time)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            semantic_timestamp = dt.timestamp()
        else:
            semantic_timestamp = 0
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的时间格式，请使用 ISO 格式 (e.g. 2023-01-15T10:30:00)")

    # 自动分块模式：必须提供 memory_coefficient 和 semantic_time
    if chunk_mode == "auto":
        memory_coefficient = request.get("memory_coefficient")
        if memory_coefficient is None:
            raise HTTPException(status_code=400, detail="自动分块模式必须提供 memory_coefficient")
        if not semantic_time:
            raise HTTPException(status_code=400, detail="自动分块模式必须提供 semantic_time（记忆产生时间）")

        chunks = _auto_chunk_text(content)
        chunk_data_list = [{"content": c, "memory_coefficient": float(memory_coefficient)} for c in chunks]

    # LLM 智能分块模式：必须提供 personality_prompt
    elif chunk_mode == "llm":
        personality_prompt = request.get("personality_prompt", "").strip()
        if not personality_prompt:
            raise HTTPException(status_code=400, detail="LLM 分块模式必须提供 personality_prompt")
        memory_coefficient = request.get("memory_coefficient", 0.85)

        chunk_data_list = await _llm_smart_chunk(
            text=content,
            owner_id=owner_id,
            personality_prompt=personality_prompt,
            semantic_timestamp=semantic_timestamp,
            memory_coefficient=memory_coefficient,
            db=db,
        )
    else:
        raise HTTPException(status_code=400, detail="chunk_mode 必须为 auto 或 llm")

    # 写入记忆
    service, _ = _get_memory_service()
    memory_ids = []

    for cd in chunk_data_list:
        chunk_content = cd.get("content", "").strip()
        chunk_coef = cd.get("memory_coefficient", 0.85)
        if not chunk_content:
            continue

        memory_id = await service.write_memory(
            content=chunk_content,
            owner_id=owner_id,
            memory_coefficient=float(chunk_coef),
            semantic_timestamp=semantic_timestamp,
        )
        memory_ids.append(memory_id)

    create_log(db, current_admin.id, "upload_memory", "memory", owner_id)

    return {
        "message": f"成功上传 {len(memory_ids)} 条记忆分块",
        "memory_ids": memory_ids,
    }


@router.delete("/{memory_id}", response_model=dict)
def delete_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """删除单条记忆"""
    service, _ = _get_memory_service()

    asyncio.run(service.delete_memory(memory_id))

    create_log(db, current_admin.id, "delete_memory", "memory", None)
    return {"message": "记忆已删除"}


@router.delete("/user/{owner_id}", response_model=dict)
def clear_user_memories(
    owner_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """清除指定用户的所有记忆"""
    service, _ = _get_memory_service()

    count = asyncio.run(service.clear_user_memories(owner_id))

    create_log(db, current_admin.id, "clear_user_memories", "memory", owner_id)
    return {"message": f"已清除 {count} 条记忆"}
