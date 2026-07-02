"""Agent 操作来源 Alembic 迁移测试。"""

from importlib import import_module

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migration_backfills_legacy_agent_rows_and_drops_user_coupling() -> None:
    """SQLite 与生产迁移共享的 SQL 应回填来源并删除公开用户旧字段。"""

    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("is_ai_agent", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ai_config_id", sa.Integer, nullable=True),
    )
    sa.Index("ix_users_is_ai_agent", users.c.is_ai_agent)
    sa.Index("ix_users_ai_config_id", users.c.ai_config_id)
    posts = sa.Table(
        "posts",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("author_id", sa.Integer, nullable=False),
    )
    notifications = sa.Table(
        "notifications",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sender_id", sa.Integer, nullable=True),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            users.insert(),
            [
                {"id": 1, "is_ai_agent": False, "ai_config_id": None},
                {"id": 2, "is_ai_agent": True, "ai_config_id": 99},
            ],
        )
        connection.execute(posts.insert(), [{"id": 10, "author_id": 1}, {"id": 11, "author_id": 2}])
        connection.execute(
            notifications.insert(),
            [
                {"id": 20, "sender_id": None},
                {"id": 21, "sender_id": 1},
                {"id": 22, "sender_id": 2},
            ],
        )

        migration = import_module(
            "social_platform.alembic.versions.0021_agent_operation_source"
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()

        post_rows = connection.execute(
            sa.text("SELECT id, created_by_agent FROM posts ORDER BY id")
        ).all()
        notification_rows = connection.execute(
            sa.text("SELECT id, created_by_agent FROM notifications ORDER BY id")
        ).all()
        user_columns = {
            column["name"] for column in sa.inspect(connection).get_columns("users")
        }

    assert post_rows == [(10, 0), (11, 1)]
    assert notification_rows == [(20, 0), (21, 0), (22, 1)]
    assert "is_ai_agent" not in user_columns
    assert "ai_config_id" not in user_columns
