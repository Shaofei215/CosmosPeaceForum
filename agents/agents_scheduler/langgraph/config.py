"""
LangGraph 会话配置模块

业务配置通过 management 数据库抽象层加载（system_configs 表），
LLM 模型配置从 model_configs 表加载，Agent 会话按角色绑定的模型读取。
"""

from dataclasses import dataclass
from typing import Any

from agents.management.backend.db_client import get_db_client


def _model_value(model_config: dict[str, Any], key: str, default: str = "") -> str:
    """
    安全读取模型配置中的字符串字段。

    Args:
        model_config: 从 management 数据库读取的模型配置字典。
        key: 需要读取的字段名。
        default: 字段缺失或为空时返回的默认值。

    Returns:
        str: 去除首尾空白后的字段值。
    """
    value = model_config.get(key, default)
    if value is None:
        return default
    return str(value).strip()


@dataclass
class SessionConfig:
    """
    会话配置类

    LLM 相关配置从 model_configs 表加载，
    其他业务配置从 system_configs 表加载。
    """
    model_config_id: int | None = None
    max_steps: int = 20
    tool_timeout: int = 30
    temperature: float = 1.2
    model_name: str = ""
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model_name: str = ""
    anthropic_api_key: str = ""
    anthropic_model_name: str = ""
    web_search_enabled: bool = False
    tavily_api_key: str = ""
    tavily_topic: str = ""
    tavily_max_results: int | None = None
    tavily_search_depth: str = ""
    tavily_include_domains: str = ""
    tavily_exclude_domains: str = ""

    @classmethod
    def from_db(cls, model_config_id: int | None = None) -> "SessionConfig":
        """
        从数据库加载配置

        LLM 配置从 model_configs 表读取。传入 model_config_id 时必须存在且启用；
        未传入时保留旧的全局读取能力，取第一个启用模型。
        其他业务配置从 system_configs 表读取。
        """
        db = get_db_client()

        def _get(key: str, default: str) -> str:
            val = db.get_system_config(key)
            return val if val else default

        if model_config_id is not None:
            active_model = db.get_model_config(model_config_id)
            if not active_model:
                raise RuntimeError(f"模型配置不存在: id={model_config_id}")
            if not active_model.get("is_active"):
                raise RuntimeError(f"模型配置未启用: id={model_config_id}")
        else:
            model_config = db.get_active_model_configs()
            if not model_config:
                raise RuntimeError(
                    "未找到启用的模型配置，请在模型配置页添加并启用一个模型"
                )
            active_model = model_config[0]

        api_key = _model_value(active_model, "api_key")
        provider = _model_value(active_model, "provider", "openai").lower()
        is_anthropic_provider = provider == "anthropic"
        model_name = _model_value(active_model, "model_name")
        openai_api_key = "" if is_anthropic_provider else api_key
        openai_base_url = (
            "" if is_anthropic_provider else _model_value(active_model, "base_url")
        )
        openai_model_name = "" if is_anthropic_provider else model_name
        anthropic_api_key = api_key if is_anthropic_provider else ""
        anthropic_model_name = model_name if is_anthropic_provider else ""
        temperature = float(active_model.get("temperature") or 1.2)
        raw_tavily_max_results = _get("TAVILY_MAX_RESULTS", "").strip()

        return cls(
            model_config_id=int(model_config_id or active_model.get("id")),
            max_steps=int(_get("LANGGRAPH_MAX_STEPS", "20")),
            tool_timeout=int(_get("LANGGRAPH_TOOL_TIMEOUT", "30")),
            temperature=temperature,
            model_name=model_name,
            llm_provider=provider,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_model_name=openai_model_name,
            anthropic_api_key=anthropic_api_key,
            anthropic_model_name=anthropic_model_name,
            web_search_enabled=_get(
                "WEB_SEARCH_ENABLED",
                "false",
            ).lower() in ("true", "1", "yes"),
            tavily_api_key=_get("TAVILY_API_KEY", ""),
            tavily_topic=_get("TAVILY_TOPIC", "").strip().lower(),
            tavily_max_results=(
                int(raw_tavily_max_results) if raw_tavily_max_results else None
            ),
            tavily_search_depth=_get("TAVILY_SEARCH_DEPTH", "").strip().lower(),
            tavily_include_domains=_get("TAVILY_INCLUDE_DOMAINS", ""),
            tavily_exclude_domains=_get("TAVILY_EXCLUDE_DOMAINS", ""),
        )

    def __post_init__(self):
        """配置验证"""
        if self.max_steps <= 0:
            raise ValueError("max_steps 必须大于 0")
        if self.tool_timeout <= 0:
            raise ValueError("tool_timeout 必须大于 0")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature 必须在 0.0 到 2.0 之间")


@dataclass
class AgentConfig:
    """Agent 配置类"""
    user_id: int
    username: str
    name: str
    agent_id: int
    personality_prompt: str
    personal_signature: str
    token: str
    session_prompt_injection: str = ""


def get_default_config() -> SessionConfig:
    """获取默认配置"""
    return SessionConfig.from_db()


_session_config: SessionConfig | None = None


def get_session_config() -> SessionConfig:
    """获取会话配置单例"""
    global _session_config
    if _session_config is None:
        _session_config = SessionConfig.from_db()
    return _session_config


def reload_session_config():
    """重载会话配置（热更新）"""
    global _session_config
    _session_config = SessionConfig.from_db()
    return _session_config
