"""增加分级用户违规状态与不可回退的违规事件表。

Revision ID: 0018_user_violation_events
Revises: 0017_moderation_appeals
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_user_violation_events"
down_revision = "0017_moderation_appeals"
branch_labels = None
depends_on = None


COUNTED_CATEGORIES = ("publish", "comment", "interaction", "avatar", "username", "bio")


def _columns(table_name: str) -> set[str]:
    """返回表的现有字段名，支持运行期创建过管理表的数据库幂等升级。

    Args:
        table_name: 待读取的数据库表名。

    Returns:
        set[str]: 表不存在时返回空集合，否则返回字段名集合。
    """

    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """扩展处罚状态并创建违规事件表，不回填历史处罚次数。

    Returns:
        None: Alembic 通过当前迁移上下文直接执行 DDL。
    """

    moderation_columns = _columns("platform_user_moderations")
    if moderation_columns:
        additions: list[sa.Column] = [sa.Column("account_current_event_id", sa.Integer(), nullable=True)]
        for category in COUNTED_CATEGORIES:
            additions.extend(
                [
                    sa.Column(
                        f"{category}_violation_count",
                        sa.Integer(),
                        nullable=False,
                        server_default="0",
                    ),
                    sa.Column(
                        f"{category}_permanently_banned",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.false(),
                    ),
                    sa.Column(f"{category}_current_event_id", sa.Integer(), nullable=True),
                ]
            )
            if category in {"avatar", "username", "bio"}:
                additions.extend(
                    [
                        sa.Column(f"{category}_banned_until", sa.DateTime(), nullable=True),
                        sa.Column(f"{category}_ban_reason", sa.Text(), nullable=True),
                    ]
                )
        for column in additions:
            if column.name not in moderation_columns:
                op.add_column("platform_user_moderations", column)

    if not _columns("user_violation_events"):
        op.create_table(
            "user_violation_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("category", sa.String(length=20), nullable=False),
            sa.Column("violation_count", sa.Integer(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("source_type", sa.String(length=30), server_default="manual", nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("dedup_key", sa.String(length=100), nullable=True),
            sa.Column("notification_id", sa.Integer(), nullable=True),
            sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("restriction_until", sa.DateTime(), nullable=True),
            sa.Column("is_permanent", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("released_at", sa.DateTime(), nullable=True),
            sa.Column("released_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["created_by_admin_id"], ["platform_admin_users.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["released_by_admin_id"], ["platform_admin_users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("dedup_key", name="uq_user_violation_events_dedup_key"),
        )
        op.create_index("ix_user_violation_events_id", "user_violation_events", ["id"])
        op.create_index("ix_user_violation_events_user_id", "user_violation_events", ["user_id"])
        op.create_index("ix_user_violation_events_category", "user_violation_events", ["category"])
        op.create_index(
            "idx_user_violation_events_user_category",
            "user_violation_events",
            ["user_id", "category", "created_at"],
        )
        op.create_index(
            "ix_user_violation_events_dedup_key",
            "user_violation_events",
            ["dedup_key"],
            unique=True,
        )
        op.create_index(
            "ix_user_violation_events_notification_id",
            "user_violation_events",
            ["notification_id"],
        )

    if "violation_event_id" not in _columns("moderation_appeals"):
        with op.batch_alter_table("moderation_appeals") as batch_op:
            batch_op.add_column(sa.Column("violation_event_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_moderation_appeals_violation_event_id",
                "user_violation_events",
                ["violation_event_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index(
                "ix_moderation_appeals_violation_event_id", ["violation_event_id"]
            )


def downgrade() -> None:
    """移除违规事件和新增状态字段。

    Returns:
        None: Alembic 通过当前迁移上下文直接执行 DDL。
    """

    if "violation_event_id" in _columns("moderation_appeals"):
        with op.batch_alter_table("moderation_appeals") as batch_op:
            batch_op.drop_index("ix_moderation_appeals_violation_event_id")
            batch_op.drop_constraint("fk_moderation_appeals_violation_event_id", type_="foreignkey")
            batch_op.drop_column("violation_event_id")
    if _columns("user_violation_events"):
        op.drop_table("user_violation_events")
    moderation_columns = _columns("platform_user_moderations")
    for category in reversed(COUNTED_CATEGORIES):
        for suffix in ("ban_reason", "banned_until") if category in {"avatar", "username", "bio"} else ():
            name = f"{category}_{suffix}"
            if name in moderation_columns:
                op.drop_column("platform_user_moderations", name)
        for suffix in ("current_event_id", "permanently_banned", "violation_count"):
            name = f"{category}_{suffix}"
            if name in moderation_columns:
                op.drop_column("platform_user_moderations", name)
    if "account_current_event_id" in moderation_columns:
        op.drop_column("platform_user_moderations", "account_current_event_id")
