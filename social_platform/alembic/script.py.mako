<%
revises = ", ".join(down_revision) if isinstance(down_revision, (tuple, list)) else (down_revision or "")
%>"""${message}。

Revision ID: ${up_revision}
Revises:${f" {revises}" if revises else ""}
Create Date: ${create_date}

本文件由 Alembic 生成，供应用启动入口按版本顺序升级或回退数据库结构。
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}


revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """按当前 revision 定义应用数据库结构升级。"""

    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """按当前 revision 定义回退数据库结构升级。"""

    ${downgrades if downgrades else "pass"}
