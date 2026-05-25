"""Add flat two-level comment thread roots.

Revision ID: 0004_flat_comment_threads
Revises: 0003_performance_indexes
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_flat_comment_threads"
down_revision = "0003_performance_indexes"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if table_name not in _table_names() or index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns)


def _backfill_root_comment_ids() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, parent_id FROM comments")).mappings().all()
    parent_by_id = {int(row["id"]): row["parent_id"] for row in rows}

    def find_root(comment_id: int) -> int | None:
        parent_id = parent_by_id.get(comment_id)
        if parent_id is None:
            return None

        seen = {comment_id}
        current_id = int(parent_id)
        while parent_by_id.get(current_id) is not None:
            if current_id in seen:
                return int(parent_id)
            seen.add(current_id)
            current_id = int(parent_by_id[current_id])
        return current_id

    for row in rows:
        comment_id = int(row["id"])
        root_id = find_root(comment_id)
        if root_id is None:
            continue
        bind.execute(
            sa.text("UPDATE comments SET root_comment_id = :root_id WHERE id = :comment_id"),
            {"root_id": root_id, "comment_id": comment_id},
        )

    bind.execute(sa.text("UPDATE comments SET reply_count = 0"))
    counts = bind.execute(
        sa.text(
            "SELECT root_comment_id, COUNT(*) AS reply_count "
            "FROM comments WHERE root_comment_id IS NOT NULL GROUP BY root_comment_id"
        )
    ).mappings().all()
    for row in counts:
        bind.execute(
            sa.text("UPDATE comments SET reply_count = :reply_count WHERE id = :root_id"),
            {"reply_count": int(row["reply_count"]), "root_id": int(row["root_comment_id"])},
        )


def upgrade() -> None:
    if "comments" not in _table_names():
        return

    if "root_comment_id" not in _column_names("comments"):
        op.add_column("comments", sa.Column("root_comment_id", sa.Integer(), nullable=True))

    _backfill_root_comment_ids()
    _create_index_if_missing(
        "idx_comments_post_root_latest",
        "comments",
        ["post_id", "root_comment_id", "created_at", "id"],
    )
    _create_index_if_missing(
        "idx_comments_post_root_heat",
        "comments",
        ["post_id", "root_comment_id", "heat_score", "created_at", "id"],
    )


def downgrade() -> None:
    pass
