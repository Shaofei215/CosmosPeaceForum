from sqlmodel import Session, SQLModel, create_engine, select

from agents.management.backend.models.system_config import SystemConfig
from agents.management.backend.services.system_service import (
    DEFAULT_SYSTEM_CONFIGS,
    ENV_MANAGED_CONFIG_KEYS,
    get_config_value,
    init_default_configs,
)


def test_default_system_configs_do_not_include_env_managed_keys():
    default_keys = {key for key, _, _ in DEFAULT_SYSTEM_CONFIGS}

    assert default_keys.isdisjoint(ENV_MANAGED_CONFIG_KEYS)


def test_init_default_configs_purges_env_managed_values_from_sqlite():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(SystemConfig(key="ADMIN_KEY", value="old-secret", description="legacy"))
        db.add(SystemConfig(key="AI_USER_PASSWORD", value="old-password", description="legacy"))
        db.commit()

        init_default_configs(db)

        admin_key = db.exec(select(SystemConfig).where(SystemConfig.key == "ADMIN_KEY")).first()
        ai_password = db.exec(
            select(SystemConfig).where(SystemConfig.key == "AI_USER_PASSWORD")
        ).first()
        assert admin_key is None
        assert ai_password is None


def test_get_config_value_reads_env_managed_values_from_core_config(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    class FakeConfig:
        admin_key = "env-admin-key"
        ai_user_password = "env-ai-password"
        app_platform_api_base_url = "http://platform/api/v1"
        log_level = "DEBUG"

    monkeypatch.setattr(
        "agents.management.backend.services.system_service.get_config",
        lambda: FakeConfig(),
    )

    with Session(engine) as db:
        db.add(SystemConfig(key="ADMIN_KEY", value="sqlite-secret", description="legacy"))
        db.commit()

        assert get_config_value(db, "ADMIN_KEY") == "env-admin-key"
        assert get_config_value(db, "AI_USER_PASSWORD") == "env-ai-password"
        assert get_config_value(db, "API_BASE_URL") == "http://platform/api/v1"
        assert get_config_value(db, "LOG_LEVEL") == "DEBUG"
