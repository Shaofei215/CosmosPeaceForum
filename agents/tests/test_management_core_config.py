"""Management 核心配置加载与规范化行为测试。"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.management.backend.core.config import Settings


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
