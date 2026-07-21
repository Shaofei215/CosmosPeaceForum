"""Management 核心配置加载与规范化行为测试。"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.management.backend.core.config import Settings, finalize_runtime_secrets


_MANAGEMENT_SETTING_ENV_NAMES: tuple[str, ...] = (
    "MANAGEMENT_JWT_SECRET_KEY",
    "MANAGEMENT_JWT_ALGORITHM",
    "MANAGEMENT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "MANAGEMENT_REFRESH_TOKEN_EXPIRE_HOURS",
    "MANAGEMENT_REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS",
    "MANAGEMENT_ADMIN_INITIAL_USERNAME",
    "MANAGEMENT_ADMIN_INITIAL_PASSWORD",
    "MANAGEMENT_SERVER_HOST",
    "MANAGEMENT_SERVER_PORT",
    "MANAGEMENT_DB_PATH",
    "MANAGEMENT_DATABASE_URL",
    "SOCIAL_PLATFORM_API_BASE_URL",
    "SOCIAL_PLATFORM_FRONTEND_URL",
    "ADMIN_KEY",
    "AI_USER_PASSWORD",
    "LOG_LEVEL",
    "LOG_DIR",
    "LOG_RETENTION_DAYS",
    "LOG_SEGMENT_MAX_MB",
    "LOG_MAX_TOTAL_MB",
    "PLATFORM_DISPLAY_NAME",
    "SCHEDULER_INTERNAL_HOST",
    "SCHEDULER_INTERNAL_PORT",
    "SCHEDULER_INTERNAL_BASE_URL",
)


@pytest.fixture(autouse=True)
def isolate_management_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """移除宿主进程配置，让每个用例显式声明自身的 Settings 输入。

    Args:
        monkeypatch: pytest 提供的进程环境隔离工具，测试结束后自动恢复原始值。
    """

    for variable_name in _MANAGEMENT_SETTING_ENV_NAMES:
        monkeypatch.delenv(variable_name, raising=False)


def test_settings_default_management_host_is_loopback() -> None:
    """未配置监听地址时，管理后端应默认仅允许本机访问。"""
    settings = Settings(_env_file=None)

    assert settings.server_host == "127.0.0.1"


def test_settings_load_dotenv_and_prefer_process_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """系统环境变量应覆盖 .env，且 .env 交由标准 dotenv 语法解析。"""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "BASE_LOG_LEVEL=DEBUG",
                "export LOG_LEVEL=${BASE_LOG_LEVEL}",
                "MANAGEMENT_SERVER_PORT=8100",
                "SOCIAL_PLATFORM_API_BASE_URL='http://platform.test/api/v1/'",
                "UNRELATED_SHARED_SETTING=ignored",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MANAGEMENT_SERVER_PORT", "8200")

    settings = Settings(_env_file=env_file)

    assert settings.server_port == 8200
    assert settings.log_level == "DEBUG"
    assert settings.social_platform_api_base_url == "http://platform.test/api/v1"


def test_settings_reject_invalid_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    """整数配置格式错误时应显式报告校验错误，而不是静默使用默认值。"""
    monkeypatch.setenv("MANAGEMENT_SERVER_PORT", "not-an-integer")

    with pytest.raises(ValidationError, match="MANAGEMENT_SERVER_PORT"):
        Settings(_env_file=None)


def test_settings_prefer_database_path_and_build_database_url() -> None:
    """同时提供数据库路径和 URL 时，应保持既有的路径优先规则。"""
    settings = Settings(
        _env_file=None,
        db_path="custom/management.db",
        database_url="sqlite:///ignored.db",
    )

    assert settings.get_db_path() == "custom/management.db"
    assert settings.get_database_url() == "sqlite:///custom/management.db"


def test_settings_derive_scheduler_url_from_host_and_port() -> None:
    """未显式配置内部 URL 时，应根据 Scheduler host 与 port 动态构造。"""
    settings = Settings(
        _env_file=None,
        scheduler_internal_host="scheduler.internal",
        scheduler_internal_port=9102,
    )

    assert settings.scheduler_internal_base_url == "http://scheduler.internal:9102"


def test_settings_load_initial_admin_environment_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """管理员初始账号只从当前 INITIAL 环境变量名加载。"""
    monkeypatch.setenv("MANAGEMENT_ADMIN_INITIAL_USERNAME", "initial-admin")
    monkeypatch.setenv("MANAGEMENT_ADMIN_INITIAL_PASSWORD", "initial-password")

    settings = Settings(_env_file=None)

    assert settings.admin_username == "initial-admin"
    assert settings.admin_password == "initial-password"


def test_settings_ignore_removed_legacy_environment_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已移除的管理员变量与小时级 access token 配置不应再影响结果。"""
    monkeypatch.setenv("MANAGEMENT_ADMIN_USERNAME", "legacy-admin")
    monkeypatch.setenv("MANAGEMENT_ADMIN_PASSWORD", "legacy-password")
    monkeypatch.setenv("MANAGEMENT_ACCESS_TOKEN_EXPIRE_HOURS", "999")

    settings = Settings(_env_file=None)

    assert settings.admin_username == "management_admin"
    assert settings.admin_password == "ChangeMe123!"
    assert settings.jwt_access_token_expire_minutes == 10


def test_finalize_runtime_secrets_generates_and_reuses_persistent_values(
    tmp_path: Path,
) -> None:
    """JWT 与 AI 密码应自动生成并跨配置实例复用，初始管理员密码则保持一次性。"""

    secret_file = tmp_path / "generated_secrets.json"
    first = finalize_runtime_secrets(Settings(_env_file=None), secret_file)
    second = finalize_runtime_secrets(Settings(_env_file=None), secret_file)

    assert first.jwt_secret_key != "change-this-local-management-jwt-secret"
    assert first.ai_user_password != "ChangeMe123!"
    assert len(first.ai_user_password) == 32
    assert first.jwt_secret_key == second.jwt_secret_key
    assert first.ai_user_password == second.ai_user_password
    assert len(first.admin_password) == 32
    assert first.admin_password != second.admin_password
    assert first.admin_password_was_generated is True
    assert secret_file.stat().st_mode & 0o777 == 0o600


def test_finalize_runtime_secrets_preserves_explicit_values(tmp_path: Path) -> None:
    """显式提供的安全配置应原样保留，且不创建运行期密钥文件。"""

    secret_file = tmp_path / "generated_secrets.json"
    settings = Settings(
        _env_file=None,
        jwt_secret_key="explicit-jwt-secret",
        admin_password="explicit-admin-password",
        ai_user_password="explicit-ai-password",
    )

    finalized = finalize_runtime_secrets(settings, secret_file)

    assert finalized.jwt_secret_key == "explicit-jwt-secret"
    assert finalized.admin_password == "explicit-admin-password"
    assert finalized.ai_user_password == "explicit-ai-password"
    assert finalized.admin_password_was_generated is False
    assert not secret_file.exists()
