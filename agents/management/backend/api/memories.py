"""
Management Backend - 记忆管理路由
"""

import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Optional

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


def _coerce_memories_payload(payload: Any) -> list[dict]:
    """从工具参数或 JSON 响应中提取 memories 列表。"""
    if isinstance(payload, dict):
        memories = payload.get("memories", [])
    elif isinstance(payload, list):
        memories = payload
    else:
        return []

    return [item for item in memories if isinstance(item, dict)]


def _load_json_payload(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str):
        return None

    text = raw.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_chunked_memories(response: Any) -> list[dict]:
    """
    兼容不同 LangChain/OpenAI-compatible 返回形态。

    仅接受 LangChain 标准 tool_calls 或 additional_kwargs 里的 OpenAI
    原始 tool_calls。普通文本/JSON 响应不视为有效分块结果。
    """
    tool_calls = getattr(response, "tool_calls", None) or []

    additional_kwargs = getattr(response, "additional_kwargs", None) or {}
    if not tool_calls and isinstance(additional_kwargs, dict):
        tool_calls = additional_kwargs.get("tool_calls", []) or []

    for call in tool_calls:
        args = None
        if isinstance(call, dict):
            args = call.get("args")
            if args is None:
                function = call.get("function") or {}
                args = _load_json_payload(function.get("arguments"))
        else:
            args = getattr(call, "args", None)
            if args is None:
                function = getattr(call, "function", None)
                args = _load_json_payload(getattr(function, "arguments", None))

        memories = _coerce_memories_payload(args)
        if memories:
            return memories

    return []


async def _llm_smart_chunk(
    text: str,
    owner_id: int,
    personality_prompt: str,
    semantic_timestamp: float,
    db: Session,
    enable_rag_on_chunking: bool = True,
) -> list[dict]:
    """
    使用 LangChain Tool 调用进行智能分块

    Args:
        text: 原始文本
        owner_id: 记忆所有者 ID
        personality_prompt: 角色个性提示词
        semantic_timestamp: 语义时间戳
        db: 数据库会话
        enable_rag_on_chunking: 是否在分块时启用 RAG 召回记忆

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
1. 每条记忆以"我"为主语，第一人称描述
2. 内容应包含：你看到了什么、你做了什么、你的感受或想法
3. 单条记忆长度 512 tokens 内
4. **核心规则：每条记忆可以聚焦事件的不同阶段/方面，但必须简要交代整个事件的起因和结果作为上下文，确保每条记忆独立可读。**
   - 举例：文档描述了一次完整旅行（出发→游玩A→游玩B→返回）
     - 分块1：详细描写游玩A的体验，但开头简述"我去了某地旅行，在游玩A时……，这次旅行让我难忘"
     - 分块2：详细描写游玩B的体验，但开头简述"我去了某地旅行，在游玩B时……，这次旅行让我难忘"
   - **绝不允许**：分块只写"我到了某地"（只有起因无结果）或"我回家了"（只有结果无起因）
5. 每条记忆中的人物与关系应指代明确
6. 为每条记忆设置差异化的记忆系数（memory_coefficient），范围 0.0-1.0：
   - 0.9-1.0：极其重要的经历，如重大情感波动、关键人际关系建立、改变认知的发现、重要事务
   - 0.7-0.9：重要经历，如深度互动的内容、引发强烈共鸣的信息、有意义的行为
   - 0.5-0.7：一般记忆，一般经历
   - 0.3-0.5：边缘记忆，不感兴趣的内容
   - 0.0-0.3：几乎不重要的信息，不建议写入
   - 请根据记忆的重要性、情感强度、人际关系关联度等因素综合评估，合理分配系数

请调用 chunk_memories 工具，一次性传入所有分块后的记忆列表。"""

    static_memories_context = ""
    if enable_rag_on_chunking:
        try:
            service, _ = _get_memory_service()
            recalled = await service.recall_memories_with_time_filter(
                owner_id=owner_id,
                context=text[:500],
                max_semantic_timestamp=semantic_timestamp,
                limit=10,
            )
            if recalled:
                static_lines = []
                for chunk, _ in recalled:
                    static_lines.append(f"- [{chunk.memory_coefficient:.2f}] {chunk.content}")
                static_memories_context = "\n\n【已有的相关记忆】\n" + "\n".join(static_lines) + "\n\n请参考以上已有记忆进行分块，系数越高表示该记忆越重要，避免生成重复内容。"
        except Exception as e:
            logger.warning("召回记忆失败，继续不带 RAG 的分块: %s", e)

    user_prompt = f"""【角色设定】
{personality_prompt}

【待分块文本】
{text}{static_memories_context}
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

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = await asyncio.to_thread(llm_with_tools.invoke, messages)

        memories = _extract_chunked_memories(response)

        if not memories:
            logger.error(
                "LLM 未返回有效分块。response_type=%s content=%s additional_kwargs=%s",
                type(response).__name__,
                getattr(response, "content", ""),
                getattr(response, "additional_kwargs", {}),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM 未返回有效的工具调用分块结果"
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
            "memory_type": chunk.memory_type,
        })

    return {"items": items, "total": total}


@router.get("/owners", response_model=dict)
def list_memory_owners(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取记忆库中的 owner 汇总，直接以 memory DB 为数据源。"""
    _, memory_db = _get_memory_service()
    all_memories = memory_db._get_all_memories_sync()

    agent_stmt = select(AgentConfig)
    agents = db.exec(agent_stmt).all()
    agent_map = {a.app_platform_user_id: a for a in agents if a.app_platform_user_id}

    grouped = {}
    for chunk in all_memories:
        stat = grouped.setdefault(chunk.owner_id, {
            "owner_id": chunk.owner_id,
            "owner_username": f"User-{chunk.owner_id}",
            "agent_id": None,
            "agent_name": None,
            "memory_count": 0,
            "latest_system_timestamp": 0,
            "latest_semantic_timestamp": 0,
            "has_agent_config": False,
        })
        agent = agent_map.get(chunk.owner_id)
        if agent:
            stat["owner_username"] = agent.name or agent.username or f"User-{chunk.owner_id}"
            stat["agent_id"] = agent.id
            stat["agent_name"] = agent.name
            stat["has_agent_config"] = True
        stat["memory_count"] += 1
        stat["latest_system_timestamp"] = max(stat["latest_system_timestamp"], chunk.timestamp)
        stat["latest_semantic_timestamp"] = max(stat["latest_semantic_timestamp"], chunk.semantic_timestamp)

    items = sorted(
        grouped.values(),
        key=lambda item: item["latest_system_timestamp"],
        reverse=True,
    )
    return {"items": items, "total": len(items)}


@router.post("/upload", response_model=dict)
async def upload_memory(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """
    上传记忆（单角色，支持自动分块、LLM 智能分块与不分块）

    请求体:
    {
        "owner_id": 1,
        "content": "长文本...",
        "semantic_time": "2023-01-15T10:30:00",     // 动态记忆必填，静态记忆可选
        "memory_coefficient": 0.85,                // 自动分块/不分块模式需要，LLM分块不需要（由LLM自动分配）
        "chunk_mode": "auto" | "llm" | "none",     // none 表示不分块直接存入
        "memory_type": "normal" | "static",        // 静态记忆不参与衰减与唤醒
        "personality_prompt": "...",               // 仅 LLM 分块模式需要
        "enable_rag_on_chunking": true             // 仅 LLM 分块模式，是否在分块时召回静态记忆（默认 true）
    }
    """
    owner_id = request.get("owner_id")
    content = request.get("content", "").strip()
    semantic_time = request.get("semantic_time", "")
    chunk_mode = request.get("chunk_mode", "auto")
    memory_type = request.get("memory_type", "normal")
    enable_rag_on_chunking = request.get("enable_rag_on_chunking", True)

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

    # 不分块模式：直接存入
    if chunk_mode == "none":
        memory_coefficient = request.get("memory_coefficient")
        if memory_coefficient is None:
            raise HTTPException(status_code=400, detail="不分块模式必须提供 memory_coefficient")

        # 静态记忆的时间戳可选，普通记忆必须提供
        if memory_type == "normal" and not semantic_time:
            raise HTTPException(status_code=400, detail="普通记忆必须提供 semantic_time（记忆产生时间）")

        chunk_data_list = [{"content": content, "memory_coefficient": float(memory_coefficient)}]

    # 自动分块模式：必须提供 memory_coefficient 和 semantic_time（普通记忆）
    elif chunk_mode == "auto":
        memory_coefficient = request.get("memory_coefficient")
        if memory_coefficient is None:
            raise HTTPException(status_code=400, detail="自动分块模式必须提供 memory_coefficient")
        if memory_type == "normal" and not semantic_time:
            raise HTTPException(status_code=400, detail="普通记忆必须提供 semantic_time（记忆产生时间）")

        chunks = _auto_chunk_text(content)
        chunk_data_list = [{"content": c, "memory_coefficient": float(memory_coefficient)} for c in chunks]

    # LLM 智能分块模式：必须提供 personality_prompt，记忆系数由 LLM 自动分配
    elif chunk_mode == "llm":
        personality_prompt = request.get("personality_prompt", "").strip()
        if not personality_prompt:
            raise HTTPException(status_code=400, detail="LLM 分块模式必须提供 personality_prompt")

        chunk_data_list = await _llm_smart_chunk(
            text=content,
            owner_id=owner_id,
            personality_prompt=personality_prompt,
            semantic_timestamp=semantic_timestamp,
            db=db,
            enable_rag_on_chunking=enable_rag_on_chunking,
        )
    else:
        raise HTTPException(status_code=400, detail="chunk_mode 必须为 auto、llm 或 none")

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
            memory_type=memory_type,
        )
        memory_ids.append(memory_id)

    create_log(db, current_admin.id, "upload_memory", "memory", owner_id)

    chunk_mode_text = {"auto": "自动分块", "llm": "LLM 智能分块", "none": "不分块"}.get(chunk_mode, chunk_mode)
    memory_type_text = {"normal": "普通记忆", "static": "静态记忆"}.get(memory_type, memory_type)

    return {
        "message": f"成功上传 {len(memory_ids)} 条记忆（{chunk_mode_text}，{memory_type_text}）",
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
