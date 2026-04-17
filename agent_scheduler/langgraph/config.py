"""
LangGraph 会话配置模块

从 management 数据库读取系统配置（优先级最高）
如果数据库未配置，则 fallback 到 .env 文件
"""

import os
from dataclasses import dataclass

from agent_scheduler.management.backend.db_client import get_db_client


def _load_env_file() -> None:
    """从 .env 文件加载环境变量"""
    config_dir = os.path.dirname(os.path.abspath(__file__))
    scheduler_dir = os.path.dirname(config_dir)
    env_file = os.path.join(scheduler_dir, '.env')
    if not os.path.exists(env_file):
        return

    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    if key not in os.environ:
                        os.environ[key] = value.strip()
    except Exception:
        return


@dataclass
class SessionConfig:
    """
    会话配置类

    配置加载顺序（优先级从高到低）：
    1. 数据库 system_configs 表（主存储）
    2. 环境变量
    3. .env 文件
    4. 程序默认值
    """
    max_steps: int = 20
    max_consecutive_errors: int = 3
    tool_timeout: int = 30
    temperature: float = 1.2
    model_name: str = ""
    enable_environment_cache: bool = True
    environment_cache_ttl: int = 180
    enable_checkpointer: bool = True
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model_name: str = ""
    anthropic_api_key: str = ""
    anthropic_model_name: str = ""

    @classmethod
    def from_db_or_env(cls) -> "SessionConfig":
        """从数据库或环境变量加载配置"""
        _load_env_file()
        db = get_db_client()

        def _get(key: str, default: str) -> str:
            val = db.get_system_config(key)
            return val if val else os.environ.get(key, default)

        provider = _get("LLM_PROVIDER", "openai")

        return cls(
            max_steps=int(_get("LANGGRAPH_MAX_STEPS", "20")),
            max_consecutive_errors=int(_get("LANGGRAPH_MAX_CONSECUTIVE_ERRORS", "3")),
            tool_timeout=int(_get("LANGGRAPH_TOOL_TIMEOUT", "30")),
            temperature=float(_get("LLM_TEMPERATURE", "1.2")),
            model_name=_get("OPENAI_MODEL_NAME", "") if provider == "openai" else _get("ANTHROPIC_MODEL_NAME", ""),
            enable_environment_cache=_get("LANGGRAPH_ENVIRONMENT_CACHE_ENABLED", "true").lower() in ("true", "1", "yes"),
            environment_cache_ttl=int(_get("LANGGRAPH_ENVIRONMENT_CACHE_TTL", "180")),
            enable_checkpointer=_get("LANGGRAPH_CHECKPOINTER_ENABLED", "true").lower() in ("true", "1", "yes"),
            llm_provider=provider,
            openai_api_key=_get("OPENAI_API_KEY", ""),
            openai_base_url=_get("OPENAI_BASE_URL", ""),
            openai_model_name=_get("OPENAI_MODEL_NAME", ""),
            anthropic_api_key=_get("ANTHROPIC_API_KEY", ""),
            anthropic_model_name=_get("ANTHROPIC_MODEL_NAME", ""),
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
        if self.environment_cache_ttl <= 0:
            raise ValueError("environment_cache_ttl 必须大于 0")


@dataclass
class AgentConfig:
    """Agent 配置类"""
    user_id: int
    username: str
    ai_config_id: int
    personality_prompt: str
    personal_signature: str
    token: str


def get_default_config() -> SessionConfig:
    """获取默认配置"""
    return SessionConfig.from_db_or_env()


def load_config_from_env() -> SessionConfig:
    """从环境变量/数据库加载配置"""
    return SessionConfig.from_db_or_env()


_session_config: SessionConfig | None = None


def get_session_config() -> SessionConfig:
    """获取会话配置单例"""
    global _session_config
    if _session_config is None:
        _session_config = SessionConfig.from_db_or_env()
    return _session_config


def reload_session_config():
    """重载会话配置（热更新）"""
    global _session_config
    _session_config = SessionConfig.from_db_or_env()
    return _session_config


def get_model_config_from_db(model_config_id: int) -> SessionConfig:
    """
    从数据库加载指定模型配置
    
    通过 management 数据库抽象层读取模型配置，
    并解密 API Key 后转换为 SessionConfig。
    
    Args:
        model_config_id: 模型配置 ID（对应 model_configs 表的主键）
        
    Returns:
        SessionConfig: 会话配置对象
        
    Raises:
        ValueError: 模型配置不存在
    """
    from agent_scheduler.management.backend.core.encryption import decrypt_value
    
    db = get_db_client()
    model_data = db.get_model_config(model_config_id)
    
    if not model_data:
        raise ValueError(f"模型配置不存在: id={model_config_id}")
    
    api_key = decrypt_value(model_data["api_key_encrypted"])
    
    return SessionConfig(
        llm_provider=model_data["provider"],
        openai_api_key=api_key if model_data["provider"] == "openai" else "",
        openai_base_url=model_data["base_url"] if model_data["provider"] == "openai" else "",
        openai_model_name=model_data["model_name"] if model_data["provider"] == "openai" else "",
        anthropic_api_key=api_key if model_data["provider"] == "anthropic" else "",
        anthropic_model_name=model_data["model_name"] if model_data["provider"] == "anthropic" else "",
        temperature=float(model_data["temperature"]),
        model_name=model_data["model_name"],
    )
