"""公开平台 Alembic 结构集成测试。

本模块从空 SQLite 文件执行与 Docker 入口相同的 ``upgrade head`` 流程，确认迁移链
生成的表与当前 SQLAlchemy metadata 一致，并验证基线可以完整回退。
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
import sqlalchemy as sa

from social_platform.app import models as app_models  # noqa: F401
from social_platform.app.admin import models as admin_models  # noqa: F401
from social_platform.app.db.session import Base
from social_platform.app.domains import registry as domain_models  # noqa: F401


SOCIAL_PLATFORM_ROOT = Path(app_models.__file__).resolve().parents[2]


def _create_alembic_config(database_url: str) -> Config:
    """创建指向测试数据库和公开平台迁移目录的 Alembic 配置。

    Args:
        database_url: 测试数据库的 SQLAlchemy URL。

    Returns:
        Config: 可传给 Alembic 命令 API 的隔离配置。
    """

    config = Config(str(SOCIAL_PLATFORM_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SOCIAL_PLATFORM_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_upgrade_head_matches_current_metadata_and_downgrades(tmp_path: Path) -> None:
    """空数据库升级到 head 后应匹配模型，并能完整回退到 base。

    Args:
        tmp_path: Pytest 提供的隔离临时目录。
    """

    database_path = tmp_path / "social_platform.sqlite3"
    database_url = f"sqlite:///{database_path}"
    config = _create_alembic_config(database_url)

    command.upgrade(config, "head")

    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)
    expected_tables = set(Base.metadata.tables) | {"alembic_version"}
    assert set(inspector.get_table_names()) == expected_tables
    with engine.connect() as connection:
        revision = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    assert revision == "0001_initial_schema"
    engine.dispose()

    command.check(config)
    command.downgrade(config, "base")

    downgraded_engine = sa.create_engine(database_url)
    assert set(sa.inspect(downgraded_engine).get_table_names()) == {"alembic_version"}
    downgraded_engine.dispose()
