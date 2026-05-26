"""
LangGraph 会话配置模块

业务配置通过 management 数据库抽象层加载（system_configs 表），
LLM 模型配置从 model_configs 表加载（取第一个 is_active=1 的记录）。
"""

from dataclasses import dataclass

from agents.management.backend.db_client import get_db_client


@dataclass
class SessionConfig:
    """
    会话配置类

    LLM 相关配置从 model_configs 表加载（全局共用一个活跃模型），
    其他业务配置从 system_configs 表加载。
    """
    max_steps: int = 20
    max_consecutive_errors: int = 3
    tool_timeout: int = 30
    temperature: float = 1.2
    model_name: str = ""
    enable_checkpointer: bool = True
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model_name: str = ""
    anthropic_api_key: str = ""
    anthropic_model_name: str = ""
    web_search_enabled: bool = False
    tavily_api_key: str = ""

    @classmethod
    def from_db(cls) -> "SessionConfig":
        """
        从数据库加载配置

        LLM 配置从 model_configs 表读取（取第一个 is_active=1 的模型），
        其他业务配置从 system_configs 表读取。
        """
        db = get_db_client()

        def _get(key: str, default: str) -> str:
            val = db.get_system_config(key)
            return val if val else default

        model_config = db.get_active_model_configs()
        if not model_config:
            raise RuntimeError(
                "未找到启用的模型配置，请在模型配置页添加并启用一个模型"
            )

        active_model = model_config[0]
        api_key = active_model["api_key"]
        provider = active_model["provider"]
        model_name = active_model["model_name"]
        openai_api_key = api_key if provider == "openai" else ""
        openai_base_url = active_model["base_url"] if provider == "openai" else ""
        openai_model_name = model_name if provider == "openai" else ""
        anthropic_api_key = api_key if provider == "anthropic" else ""
        anthropic_model_name = model_name if provider == "anthropic" else ""
        temperature = float(active_model["temperature"])

        return cls(
            max_steps=int(_get("LANGGRAPH_MAX_STEPS", "20")),
            max_consecutive_errors=int(_get("LANGGRAPH_MAX_CONSECUTIVE_ERRORS", "3")),
            tool_timeout=int(_get("LANGGRAPH_TOOL_TIMEOUT", "30")),
            temperature=temperature,
            model_name=model_name,
            enable_checkpointer=_get("LANGGRAPH_CHECKPOINTER_ENABLED", "true").lower() in ("true", "1", "yes"),
            llm_provider=provider,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_model_name=openai_model_name,
            anthropic_api_key=anthropic_api_key,
            anthropic_model_name=anthropic_model_name,
            web_search_enabled=_get("WEB_SEARCH_ENABLED", "false").lower() in ("true", "1", "yes"),
            tavily_api_key=_get("TAVILY_API_KEY", ""),
        )

    def __post_init__(self):
        """配置验证"""
        if self.max_steps <= 0:
            raise ValueError("max_steps 必须大于 0")
        if self.max_consecutive_errors <= 0:
            raise ValueError("max_consecutive_errors 必须大于 0")
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
    ai_config_id: int
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
