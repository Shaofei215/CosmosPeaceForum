# 会话配置模块
# 定义 LangGraph 会话的各种配置参数，包括步数限制、超时设置等
# 支持从环境变量加载配置，优先使用环境变量值
import os
from typing import Optional
from dataclasses import dataclass


# ============================================================
# .env 文件加载
# ============================================================

def _load_env_file(env_file_path: str) -> dict:
    """
    从 .env 文件加载环境配置

    Args:
        env_file_path: .env 文件路径

    Returns:
        dict: 配置字典
    """
    config = {}
    if not os.path.exists(env_file_path):
        return config

    with open(env_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config


def _get_env_config() -> dict:
    """
    获取环境配置

    优先从环境变量获取，如果没有则从 .env 文件读取。

    Returns:
        dict: 配置字典
    """
    scheduler_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_file = os.path.join(scheduler_dir, '.env')
    return _load_env_file(env_file)


# 加载 .env 文件配置
_env_config = _get_env_config()


# ============================================================
# 环境变量辅助函数
# ============================================================

def _get_env_int(key: str, default: int) -> int:
    """
    从环境变量获取整数配置（优先环境变量，其次 .env 文件，最后默认值）

    Args:
        key: 环境变量名称
        default: 默认值

    Returns:
        int: 配置值，如果环境变量无效则使用默认值
    """
    # 优先从环境变量获取
    value = os.environ.get(key)
    if value:
        try:
            return int(value)
        except ValueError:
            pass

    # 其次从 .env 文件获取
    env_value = _env_config.get(key)
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            return default

    return default


def _get_env_float(key: str, default: float) -> float:
    """
    从环境变量获取浮点数配置（优先环境变量，其次 .env 文件，最后默认值）

    Args:
        key: 环境变量名称
        default: 默认值

    Returns:
        float: 配置值，如果环境变量无效则使用默认值
    """
    value = os.environ.get(key)
    if value:
        try:
            return float(value)
        except ValueError:
            pass

    env_value = _env_config.get(key)
    if env_value:
        try:
            return float(env_value)
        except ValueError:
            return default

    return default


def _get_env_bool(key: str, default: bool) -> bool:
    """
    从环境变量获取布尔配置（优先环境变量，其次 .env 文件，最后默认值）

    Args:
        key: 环境变量名称
        default: 默认值

    Returns:
        bool: 配置值，支持 "true"/"1"/"yes" (不区分大小写) 为 True
    """
    value = os.environ.get(key)
    if value:
        return value.lower() in ("true", "1", "yes")

    env_value = _env_config.get(key)
    if env_value:
        return env_value.lower() in ("true", "1", "yes")

    return default


def _get_env_str(key: str, default: str) -> str:
    """
    从环境变量获取字符串配置（优先环境变量，其次 .env 文件，最后默认值）

    Args:
        key: 环境变量名称
        default: 默认值

    Returns:
        str: 配置值
    """
    value = os.environ.get(key)
    if value:
        return value.strip()

    env_value = _env_config.get(key)
    if env_value:
        return env_value.strip()

    return default


# ============================================================
# 配置类定义
# ============================================================

@dataclass
class SessionConfig:
    """
    会话配置类

    包含控制 LangGraph 会话行为的所有配置参数。
    使用 dataclass 便于序列化存储和配置管理。

    配置加载顺序（优先级从高到低）：
    1. 环境变量
    2. .env 文件
    3. 程序默认值

    Attributes:
        max_steps: 最大步数限制，防止 LLM 无限决策
        max_consecutive_errors: 最大连续错误次数，超过后强制退出
        tool_timeout: 单次工具调用超时时间（秒）
        temperature: LLM 温度参数，控制输出的随机性
        model_name: LLM 模型名称
        enable_environment_cache: 是否启用环境感知缓存
        environment_cache_ttl: 环境感知缓存有效期（秒）
        enable_checkpointer: 是否启用检查点，支持中断恢复
        llm_provider: LLM 提供者 (openai / anthropic)
        openai_api_key: OpenAI API 密钥
        openai_base_url: OpenAI API 基础 URL
        openai_model_name: OpenAI 模型名称
        anthropic_api_key: Anthropic API 密钥
        anthropic_model_name: Anthropic 模型名称
    """
    # 步数控制
    max_steps: int = 10                              # 最大步数限制
    max_consecutive_errors: int = 3                  # 最大连续错误次数

    # 超时配置
    tool_timeout: int = 30                            # 工具调用超时（秒）

    # LLM 配置
    temperature: float = 0.7                          # LLM 温度参数
    model_name: str = "gpt-4o-mini"                   # LLM 模型名称

    # 缓存配置
    enable_environment_cache: bool = True              # 启用环境感知缓存
    environment_cache_ttl: int = 60                   # 缓存有效期（秒）

    # 检查点配置
    enable_checkpointer: bool = True                   # 启用检查点

    # LLM 提供者配置
    llm_provider: str = "openai"                      # LLM 提供者

    # OpenAI 配置
    openai_api_key: str = ""                          # OpenAI API 密钥
    openai_base_url: str = ""                          # OpenAI API 基础 URL

    # Anthropic 配置
    anthropic_api_key: str = ""                        # Anthropic API 密钥
    anthropic_model_name: str = "claude-sonnet-4-20250514"  # Anthropic 模型名称

    def __post_init__(self):
        """
        配置验证

        在初始化后验证配置参数的合法性。
        """
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
    """
    Agent 配置类

    包含单个 AI Agent 的身份和角色配置。
    这些信息在创建会话执行器时传入。

    Attributes:
        user_id: 用户 ID
        username: 用户名
        ai_config_id: AI 配置 ID
        personality_prompt: 角色性格描述
        personal_signature: 个性签名
        token: 访问令牌
    """
    user_id: int                                     # 用户 ID
    username: str                                     # 用户名
    ai_config_id: int                                 # AI 配置 ID
    personality_prompt: str                           # 角色性格描述
    personal_signature: str                           # 个性签名
    token: str                                        # 访问令牌


def get_default_config() -> SessionConfig:
    """
    获取默认配置

    优先从环境变量加载配置，环境变量不存在时使用默认值。

    Returns:
        SessionConfig: 配置实例
    """
    return SessionConfig(
        # 步数控制
        max_steps=_get_env_int("LANGGRAPH_MAX_STEPS", 10),
        max_consecutive_errors=_get_env_int("LANGGRAPH_MAX_CONSECUTIVE_ERRORS", 3),

        # 超时配置
        tool_timeout=_get_env_int("LANGGRAPH_TOOL_TIMEOUT", 30),

        # LLM 配置
        temperature=_get_env_float("LLM_TEMPERATURE", 0.7),
        model_name=_get_env_str("OPENAI_MODEL_NAME", "gpt-4o-mini"),

        # 缓存配置
        enable_environment_cache=_get_env_bool("LANGGRAPH_ENVIRONMENT_CACHE_ENABLED", True),
        environment_cache_ttl=_get_env_int("LANGGRAPH_ENVIRONMENT_CACHE_TTL", 60),

        # 检查点配置
        enable_checkpointer=_get_env_bool("LANGGRAPH_CHECKPOINTER_ENABLED", True),

        # LLM 提供者
        llm_provider=_get_env_str("LLM_PROVIDER", "openai"),

        # OpenAI 配置
        openai_api_key=_get_env_str("OPENAI_API_KEY", ""),
        openai_base_url=_get_env_str("OPENAI_BASE_URL", ""),

        # Anthropic 配置
        anthropic_api_key=_get_env_str("ANTHROPIC_API_KEY", ""),
        anthropic_model_name=_get_env_str("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-20250514"),
    )


def load_config_from_env() -> SessionConfig:
    """
    从环境变量加载配置（显式加载）

    与 get_default_config 功能相同，但语义更明确。
    适用于需要显式控制配置加载的场景。

    Returns:
        SessionConfig: 配置实例
    """
    return get_default_config()
