"""统一文章、帖子和评论正文长度。

Revision ID: 0020_content_length_limits
Revises: 0019_violation_count_reversals
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_content_length_limits"
down_revision = "0019_violation_count_reversals"
branch_labels = None
depends_on = None

ARTICLE_CONTENT_MAX_LENGTH = 10_000
POST_CONTENT_MAX_LENGTH = 1_000
COMMENT_CONTENT_MAX_LENGTH = 1_000


def _table_names() -> set[str]:
    """返回当前数据库表名，兼容首次部署和已有数据库迁移。

    Returns:
        set[str]: 当前连接可见的数据库表名。
    """

    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """裁剪超长历史正文并增加字段类型与数据库检查约束。"""

    table_names = _table_names()
    if "posts" in table_names:
        op.execute(
            sa.text(
                "UPDATE posts SET content = substr(content, 1, "
                ":article_max) WHERE type = 'article' AND length(content) > :article_max"
            ).bindparams(article_max=ARTICLE_CONTENT_MAX_LENGTH)
        )
        op.execute(
            sa.text(
                "UPDATE posts SET content = substr(content, 1, "
                ":post_max) WHERE type <> 'article' AND length(content) > :post_max"
            ).bindparams(post_max=POST_CONTENT_MAX_LENGTH)
        )
        with op.batch_alter_table("posts") as batch_op:
            batch_op.alter_column(
                "content",
                existing_type=sa.Text(),
                type_=sa.String(length=ARTICLE_CONTENT_MAX_LENGTH),
                existing_nullable=False,
            )
            batch_op.create_check_constraint(
                "ck_posts_content_article_length",
                f"length(content) <= {ARTICLE_CONTENT_MAX_LENGTH}",
            )
            batch_op.create_check_constraint(
                "ck_posts_content_post_length",
                f"type = 'article' OR length(content) <= {POST_CONTENT_MAX_LENGTH}",
            )

    if "comments" in table_names:
        op.execute(
            sa.text(
                "UPDATE comments SET content = substr(content, 1, :comment_max) "
                "WHERE length(content) > :comment_max"
            ).bindparams(comment_max=COMMENT_CONTENT_MAX_LENGTH)
        )
        with op.batch_alter_table("comments") as batch_op:
            batch_op.alter_column(
                "content",
                existing_type=sa.Text(),
                type_=sa.String(length=COMMENT_CONTENT_MAX_LENGTH),
                existing_nullable=False,
            )
            batch_op.create_check_constraint(
                "ck_comments_content_length",
                f"length(content) <= {COMMENT_CONTENT_MAX_LENGTH}",
            )


def downgrade() -> None:
    """移除正文长度约束并把字段恢复为无长度限制的文本类型。"""

    table_names = _table_names()
    if "comments" in table_names:
        with op.batch_alter_table("comments") as batch_op:
            batch_op.drop_constraint("ck_comments_content_length", type_="check")
            batch_op.alter_column(
                "content",
                existing_type=sa.String(length=COMMENT_CONTENT_MAX_LENGTH),
                type_=sa.Text(),
                existing_nullable=False,
            )

    if "posts" in table_names:
        with op.batch_alter_table("posts") as batch_op:
            batch_op.drop_constraint("ck_posts_content_post_length", type_="check")
            batch_op.drop_constraint("ck_posts_content_article_length", type_="check")
            batch_op.alter_column(
                "content",
                existing_type=sa.String(length=ARTICLE_CONTENT_MAX_LENGTH),
                type_=sa.Text(),
                existing_nullable=False,
            )
