from sqlmodel import Session, SQLModel, create_engine, select

from agents.management.backend.models.system_config import SystemConfig
from agents.management.backend.services.system_service import (
    DEFAULT_SYSTEM_CONFIGS,
    ENV_MANAGED_CONFIG_KEYS,
    REMOVED_SYSTEM_CONFIG_KEYS,
    get_config_value,
    init_default_configs,
    list_system_configs,
    update_system_config,
)


def test_default_system_configs_do_not_include_env_managed_keys():
    default_keys = {key for key, _, _ in DEFAULT_SYSTEM_CONFIGS}

    assert default_keys.isdisjoint(ENV_MANAGED_CONFIG_KEYS)


def test_default_system_configs_do_not_include_removed_keys() -> None:
    """已移除的历史配置不应重新写入新数据库。"""
    default_keys = {key for key, _, _ in DEFAULT_SYSTEM_CONFIGS}

    assert default_keys.isdisjoint(REMOVED_SYSTEM_CONFIG_KEYS)


def test_default_system_configs_include_web_search_keys():
    default_keys = {key for key, _, _ in DEFAULT_SYSTEM_CONFIGS}

    assert "WEB_SEARCH_ENABLED" in default_keys
    assert "TAVILY_API_KEY" in default_keys


def test_default_system_configs_include_scheduler_time_scale():
    default_keys = {key for key, _, _ in DEFAULT_SYSTEM_CONFIGS}

    assert "SCHEDULER_TIME_SCALE" in default_keys


def test_default_system_configs_include_current_memory_defaults():
    """新数据库写入的记忆默认值应等于旧数据迁移后的最终配置。"""

    defaults = {key: value for key, value, _ in DEFAULT_SYSTEM_CONFIGS}

    assert defaults["MEMORY_RECALL_VECTOR_RESULTS"] == "20"
    assert defaults["MEMORY_RECALL_BM25_RESULTS"] == "20"
    assert defaults["MEMORY_RECALL_MAX_CANDIDATES"] == "200"
    assert defaults["MEMORY_IMPORTANCE_WEIGHT"] == "0.3"
    assert defaults["MEMORY_THRESHOLD"] == "0.1"
    assert defaults["MEMORY_BOOST_FACTOR"] == "0.1"
    assert defaults["MEMORY_BOOST_COOLDOWN_SECONDS"] == "86400"


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


def test_init_default_configs_purges_removed_values_from_sqlite() -> None:
    """初始化配置时应清理旧库中的已移除配置。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        removed_keys = {
            "LANGGRAPH_CHECKPOINTER_ENABLED",
            "LANGGRAPH_MAX_CONSECUTIVE_ERRORS",
        }
        for key in removed_keys:
            db.add(
                SystemConfig(
                    key=key,
                    value="true",
                    description="legacy",
                )
            )
        db.commit()

        init_default_configs(db)

        for key in removed_keys:
            removed_config = db.exec(
                select(SystemConfig).where(SystemConfig.key == key)
            ).first()
            assert removed_config is None


def test_get_config_value_reads_env_managed_values_from_core_config(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    class FakeConfig:
        admin_key = "env-admin-key"
        ai_user_password = "env-ai-password"
        social_platform_api_base_url = "http://social-platform/api/v1"
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
        assert get_config_value(db, "SOCIAL_PLATFORM_API_BASE_URL") == "http://social-platform/api/v1"
        assert get_config_value(db, "LOG_LEVEL") == "DEBUG"


def test_update_system_config_rejects_invalid_scheduler_time_scale():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(
            SystemConfig(
                key="SCHEDULER_TIME_SCALE",
                value="1.0",
                description="Scheduler 时间倍率",
            )
        )
        db.commit()

        for value in ("0", "-1", "invalid"):
            try:
                update_system_config(db, "SCHEDULER_TIME_SCALE", value)
            except ValueError:
                pass
            else:
                raise AssertionError(f"非法时间倍率未被拒绝: {value}")


def test_update_system_config_rejects_invalid_memory_values():
    """记忆候选数、衰减间隔和系数应在写入配置前校验。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    invalid_values = {
        "MEMORY_RECALL_VECTOR_RESULTS": "0",
        "MEMORY_RECALL_MAX_CANDIDATES": "0",
        "MEMORY_DECAY_INTERVAL_SECONDS": "-1",
        "MEMORY_IMPORTANCE_WEIGHT": "1.1",
        "MEMORY_THRESHOLD": "1.1",
        "MEMORY_BOOST_COOLDOWN_SECONDS": "-1",
        "MEMORY_DECAY_RATE": "0",
        "MEMORY_ENABLED": "maybe",
    }
    with Session(engine) as db:
        for key, value in invalid_values.items():
            db.add(SystemConfig(key=key, value="1", description=key))
        db.commit()

        for key, value in invalid_values.items():
            try:
                update_system_config(db, key, value)
            except ValueError:
                pass
            else:
                raise AssertionError(f"非法记忆配置未被拒绝: {key}={value}")


def test_list_system_configs_uses_default_order_and_descriptions():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(SystemConfig(key="TAVILY_API_KEY", value="", description="old tavily description"))
        db.add(SystemConfig(key="WEB_SEARCH_ENABLED", value="false", description="old switch description"))
        db.commit()

        configs = list_system_configs(db)

        assert [config.key for config in configs] == ["WEB_SEARCH_ENABLED", "TAVILY_API_KEY"]
        assert configs[0].description == "启用联网搜索工具"
        assert configs[1].description == "Tavily API Key"
