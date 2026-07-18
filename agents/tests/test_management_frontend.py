"""管理前端构建产物与后端运行时配置衔接测试。"""

from pathlib import Path

import pytest
from fastapi import HTTPException

from agents.management.backend.main import render_management_index, resolve_frontend_path


def test_render_management_index_injects_escaped_platform_name(tmp_path: Path) -> None:
    """入口页面应注入经过 HTML 转义的平台展示名称。"""
    index_file = tmp_path / "index.html"
    index_file.write_text(
        (
            '<meta name="platform-display-name" content="__PLATFORM_DISPLAY_NAME__">'
            "<title>__PLATFORM_DISPLAY_NAME__</title>"
        ),
        encoding="utf-8",
    )

    html = render_management_index(index_file, '和平 & "论坛" <测试>')

    escaped_name = "和平 &amp; &quot;论坛&quot; &lt;测试&gt;"
    assert html.count(escaped_name) == 2
    assert "__PLATFORM_DISPLAY_NAME__" not in html


def test_resolve_frontend_path_rejects_parent_directory_escape(tmp_path: Path) -> None:
    """前端回退路由不得读取构建目录之外的 Management 数据文件。"""

    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "management.db").write_bytes(b"sensitive")

    with pytest.raises(HTTPException) as exc_info:
        resolve_frontend_path(frontend_dist, "../../data/management.db")

    assert exc_info.value.status_code == 404


def test_resolve_frontend_path_rejects_symlink_escape(tmp_path: Path) -> None:
    """构建目录内指向外部敏感文件的符号链接也不得被返回。"""

    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    secret_file = tmp_path / "management.db"
    secret_file.write_bytes(b"sensitive")
    (frontend_dist / "database").symlink_to(secret_file)

    with pytest.raises(HTTPException) as exc_info:
        resolve_frontend_path(frontend_dist, "database")

    assert exc_info.value.status_code == 404


def test_resolve_frontend_path_accepts_file_inside_dist(tmp_path: Path) -> None:
    """正常的前端构建文件仍应解析为构建目录内的绝对路径。"""

    frontend_dist = tmp_path / "frontend" / "dist"
    assets_dir = frontend_dist / "assets"
    assets_dir.mkdir(parents=True)
    asset_file = assets_dir / "app.js"
    asset_file.write_text("console.log('ok');", encoding="utf-8")

    assert resolve_frontend_path(frontend_dist, "assets/app.js") == asset_file.resolve()
