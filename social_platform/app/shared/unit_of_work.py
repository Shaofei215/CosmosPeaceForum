"""事务工作单元工具。

该模块把数据库提交与回滚收束到统一入口，方便领域服务保持一致的事务语义。
领域事件的提交后处理由 ``shared.events`` 中的 SQLAlchemy 钩子自动触发。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session


def commit_session(session: Session) -> None:
    """提交当前数据库会话。

    Args:
        session: 当前 SQLAlchemy 会话。

    Raises:
        Exception: SQLAlchemy 提交过程中抛出的异常会原样向上抛出。
    """

    session.commit()


def rollback_session(session: Session) -> None:
    """回滚当前数据库会话。

    Args:
        session: 当前 SQLAlchemy 会话。
    """

    session.rollback()


@contextmanager
def unit_of_work(session: Session) -> Generator[Session, None, None]:
    """围绕现有会话创建一个轻量事务边界。

    Args:
        session: 由 FastAPI 依赖或测试夹具创建的 SQLAlchemy 会话。

    Yields:
        Session: 原始数据库会话。

    Raises:
        Exception: 业务逻辑或提交失败时原样抛出，并在抛出前回滚事务。
    """

    try:
        yield session
        commit_session(session)
    except Exception:
        rollback_session(session)
        raise
