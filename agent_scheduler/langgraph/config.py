# 会话配置模块
# 定义 LangGraph 会话的各种配置参数，包括步数限制、超时设置等
import os
from dataclasses import dataclass


def _load_env_file() -> None:
    """
    从 .env 文件加载环境配置到 os.environ

    查找顺序：
    1. 当前目录下的 .env
    2. agent_scheduler 目录下的 .env
    """
    if os.path.exists('.env'):
        env_file = '.env'
    else:
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
                    value = value.strip()
                    if key not in os.environ:
                        os.environ[key] = value
    except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
        print(f"[配置加载][warning]无法加载环境文件 {env_file}: {e}")
        return


@dataclass
class SessionConfig:
    """
    会话配置类

    包含控制 LangGraph 会话行为的所有配置参数。

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
        anthropic_api_key: Anthropic API 密钥
        anthropic_model_name: Anthropic 模型名称
    """
    max_steps: int = 20
    max_consecutive_errors: int = 3
    tool_timeout: int = 30
    temperature: float = 1.2
    model_name: str = ""
    enable_environment_cache: bool = True
    environment_cache_ttl: int = 60
    enable_checkpointer: bool = True
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = ""
    anthropic_api_key: str = ""
    anthropic_model_name: str = ""

    @classmethod
    def from_env(cls) -> "SessionConfig":
        """
        从环境变量创建配置实例

        优先从环境变量获取配置值，环境变量不存在时使用默认值。
        支持的环境变量请参见各属性的默认值。

        Returns:
            SessionConfig: 配置实例
        """
        _load_env_file()
        return cls(
            max_steps=int(os.environ.get("LANGGRAPH_MAX_STEPS", "20")),
            max_consecutive_errors=int(os.environ.get("LANGGRAPH_MAX_CONSECUTIVE_ERRORS", "3")),
            tool_timeout=int(os.environ.get("LANGGRAPH_TOOL_TIMEOUT", "30")),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "1.2")),
            model_name=os.environ.get("OPENAI_MODEL_NAME", ""),
            enable_environment_cache=os.environ.get("LANGGRAPH_ENVIRONMENT_CACHE_ENABLED", "true").lower() in ("true", "1", "yes"),
            environment_cache_ttl=int(os.environ.get("LANGGRAPH_ENVIRONMENT_CACHE_TTL", "60")),
            enable_checkpointer=os.environ.get("LANGGRAPH_CHECKPOINTER_ENABLED", "true").lower() in ("true", "1", "yes"),
            llm_provider=os.environ.get("LLM_PROVIDER", "openai"),
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_base_url=os.environ.get("OPENAI_BASE_URL", ""),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            anthropic_model_name=os.environ.get("ANTHROPIC_MODEL_NAME", ""),
        )

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
    user_id: int
    username: str
    ai_config_id: int
    personality_prompt: str
    personal_signature: str
    token: str


def get_default_config() -> SessionConfig:
    """
    获取默认配置

    优先从环境变量加载配置，环境变量不存在时使用默认值。

    Returns:
        SessionConfig: 配置实例
    """
    return SessionConfig.from_env()


def load_config_from_env() -> SessionConfig:
    """
    从环境变量加载配置（显式加载）

    与 get_default_config 功能相同，但语义更明确。
    适用于需要显式控制配置加载的场景。

    Returns:
        SessionConfig: 配置实例
    """
    return SessionConfig.from_env()
