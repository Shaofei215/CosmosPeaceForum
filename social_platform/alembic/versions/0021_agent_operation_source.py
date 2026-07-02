"""统一持久社交关系的 Agent 操作来源并解除公开账号与 Management 的耦合。

Revision ID: 0021_agent_operation_source
Revises: 0020_content_length_limits
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_agent_operation_source"
down_revision = "0020_content_length_limits"
branch_labels = None
depends_on = None

SOURCE_TABLE_ACTORS = {
    "posts": "author_id",
    "comments": "owner_id",
    "likes": "user_id",
    "comment_likes": "user_id",
    "follows": "follower_id",
    "poll_votes": "user_id",
    "content_reports": "reporter_id",
}


def _table_names() -> set[str]:
    """返回当前连接可见的表名。"""

    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    """返回指定表的字段名集合。"""

    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    """返回指定表的索引名集合。"""

    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    """增加来源字段、回填历史 Agent 操作，并删除公开用户的旧类型字段。"""

    table_names = _table_names()
    source_tables = [*SOURCE_TABLE_ACTORS, "notifications"]
    for table_name in source_tables:
        if table_name not in table_names or "created_by_agent" in _column_names(table_name):
            continue
        op.add_column(
            table_name,
            sa.Column(
                "created_by_agent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    user_columns = _column_names("users") if "users" in table_names else set()
    if "is_ai_agent" in user_columns:
        for table_name, actor_column in SOURCE_TABLE_ACTORS.items():
            if table_name not in table_names:
                continue
            op.execute(
                sa.text(
                    f"UPDATE {table_name} SET created_by_agent = :true_value "
                    f"WHERE {actor_column} IN "
                    "(SELECT id FROM users WHERE is_ai_agent = :true_value)"
                ).bindparams(true_value=True)
            )

        if "notifications" in table_names:
            notification_columns = _column_names("notifications")
            op.execute(
                sa.text(
                    "UPDATE notifications SET created_by_agent = :true_value "
                    "WHERE sender_id IS NOT NULL AND sender_id IN "
                    "(SELECT id FROM users WHERE is_ai_agent = :true_value)"
                ).bindparams(true_value=True)
            )
            if "comments" in table_names and {"type", "comment_id"} <= notification_columns:
                op.execute(
                    sa.text(
                        "UPDATE notifications SET created_by_agent = :true_value "
                        "WHERE type IN ('comment', 'comment_reply', 'mention') "
                        "AND comment_id IN "
                        "(SELECT id FROM comments WHERE created_by_agent = :true_value)"
                    ).bindparams(true_value=True)
                )
            if "posts" in table_names and {"type", "post_id", "comment_id"} <= notification_columns:
                op.execute(
                    sa.text(
                        "UPDATE notifications SET created_by_agent = :true_value "
                        "WHERE ((type = 'mention' AND comment_id IS NULL) OR type = 'repost') "
                        "AND post_id IN "
                        "(SELECT id FROM posts WHERE created_by_agent = :true_value)"
                    ).bindparams(true_value=True)
                )

        user_indexes = _index_names("users")
        with op.batch_alter_table("users") as batch_op:
            for index_name in ("ix_users_is_ai_agent", "ix_users_ai_config_id"):
                if index_name in user_indexes:
                    batch_op.drop_index(index_name)
            if "ai_config_id" in user_columns:
                batch_op.drop_column("ai_config_id")
            batch_op.drop_column("is_ai_agent")


def downgrade() -> None:
    """恢复旧账号字段并移除来源字段；已删除的 Management 配置 ID 无法无损恢复。"""

    table_names = _table_names()
    if "users" in table_names:
        user_columns = _column_names("users")
        with op.batch_alter_table("users") as batch_op:
            if "is_ai_agent" not in user_columns:
                batch_op.add_column(
                    sa.Column("is_ai_agent", sa.Boolean(), nullable=False, server_default=sa.false())
                )
                batch_op.create_index("ix_users_is_ai_agent", ["is_ai_agent"], unique=False)
            if "ai_config_id" not in user_columns:
                batch_op.add_column(sa.Column("ai_config_id", sa.Integer(), nullable=True))
                batch_op.create_index("ix_users_ai_config_id", ["ai_config_id"], unique=False)

        actor_queries = [
            f"SELECT {actor_column} FROM {table_name} WHERE created_by_agent = :true_value"
            for table_name, actor_column in SOURCE_TABLE_ACTORS.items()
            if table_name in table_names and "created_by_agent" in _column_names(table_name)
        ]
        if actor_queries:
            op.execute(
                sa.text(
                    "UPDATE users SET is_ai_agent = :true_value WHERE id IN ("
                    + " UNION ".join(actor_queries)
                    + ")"
                ).bindparams(true_value=True)
            )

    for table_name in [*SOURCE_TABLE_ACTORS, "notifications"]:
        if table_name not in table_names or "created_by_agent" not in _column_names(table_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column("created_by_agent")
