"""公开平台数据库会话基础设施测试。"""

from pathlib import Path

from social_platform.app.db.session import _ensure_sqlite_database_dir


def test_ensure_sqlite_database_dir_creates_parent(tmp_path: Path) -> None:
    """文件型 SQLite URL 会自动创建缺失的父目录。

    Args:
        tmp_path: pytest 提供的临时目录。
    """

    db_path = tmp_path / "nested" / "data" / "social_platform.sqlite3"

    _ensure_sqlite_database_dir(f"sqlite:///{db_path}")

    assert db_path.parent.exists()
    assert db_path.parent.is_dir()
    assert not db_path.exists()


def test_ensure_sqlite_database_dir_skips_memory_database(tmp_path: Path) -> None:
    """内存 SQLite URL 不会创建无关目录。

    Args:
        tmp_path: pytest 提供的临时目录。
    """

    marker = tmp_path / "should-not-exist"

    _ensure_sqlite_database_dir("sqlite:///:memory:")

    assert not marker.exists()
