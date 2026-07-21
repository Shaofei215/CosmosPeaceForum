"""公开平台运行期密钥生成与初始管理员密码行为测试。"""

from pathlib import Path

from social_platform.app.core.config import Settings, finalize_runtime_secrets


def _build_settings(jwt_secret: str, admin_password: str) -> Settings:
    """构造仅包含密钥测试所需字段的配置对象。

    Args:
        jwt_secret: 待解析的 JWT secret。
        admin_password: 待解析的平台初始管理员密码。

    Returns:
        Settings: 跳过无关必填部署配置校验的测试配置。
    """

    return Settings.model_construct(
        JWT_SECRET_KEY=jwt_secret,
        PLATFORM_ADMIN_INITIAL_PASSWORD=admin_password,
    )


def test_finalize_runtime_secrets_generates_and_reuses_jwt_secret(tmp_path: Path) -> None:
    """示例 JWT secret 应持久化复用，而自动生成的管理员密码应保持一次性。"""

    secret_file = tmp_path / "generated_secrets.json"
    first = finalize_runtime_secrets(
        _build_settings("change-this-to-a-long-random-secret", "ChangeMe123!"),
        secret_file,
    )
    second = finalize_runtime_secrets(
        _build_settings("", ""),
        secret_file,
    )

    assert first.JWT_SECRET_KEY != "change-this-to-a-long-random-secret"
    assert first.JWT_SECRET_KEY == second.JWT_SECRET_KEY
    assert len(first.PLATFORM_ADMIN_INITIAL_PASSWORD) == 32
    assert first.PLATFORM_ADMIN_INITIAL_PASSWORD != second.PLATFORM_ADMIN_INITIAL_PASSWORD
    assert first.platform_admin_password_was_generated is True
    assert secret_file.stat().st_mode & 0o777 == 0o600


def test_finalize_runtime_secrets_preserves_explicit_values(tmp_path: Path) -> None:
    """显式 JWT secret 与初始管理员密码应原样保留且不触碰运行期文件。"""

    secret_file = tmp_path / "generated_secrets.json"
    settings = _build_settings("explicit-jwt-secret", "explicit-admin-password")

    finalized = finalize_runtime_secrets(settings, secret_file)

    assert finalized.JWT_SECRET_KEY == "explicit-jwt-secret"
    assert finalized.PLATFORM_ADMIN_INITIAL_PASSWORD == "explicit-admin-password"
    assert finalized.platform_admin_password_was_generated is False
    assert not secret_file.exists()
