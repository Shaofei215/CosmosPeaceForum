"""公开平台 SPA 静态文件目录边界回归测试。"""

from pathlib import Path

import pytest
from starlette.exceptions import HTTPException

from social_platform.app.core.static_files import SPAStaticFiles, render_spa_index


def test_spa_static_files_never_serve_files_outside_dist(tmp_path) -> None:
    """父目录、编码路径和符号链接均不能读取 dist 外的数据库文件。"""

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("SPA INDEX", encoding="utf-8")
    (dist / "app.js").write_text("SAFE ASSET", encoding="utf-8")
    secret = tmp_path / "secret.sqlite3"
    secret.write_text("DATABASE SECRET", encoding="utf-8")
    (dist / "database.sqlite3").symlink_to(secret)
    static_files = SPAStaticFiles(directory=dist, html=True)
    normal_path, normal_stat = static_files.lookup_path("app.js")
    assert normal_path == str(dist / "app.js")
    assert normal_stat is not None

    missing_path, missing_stat = static_files.lookup_path("client/route")
    fallback_path, fallback_stat = static_files.lookup_path("index.html")
    assert (missing_path, missing_stat) == ("", None)
    assert fallback_path == str(dist / "index.html")
    assert fallback_stat is not None

    for path in (
        "../secret.sqlite3",
        "%2e%2e/secret.sqlite3",
        "database.sqlite3",
        secret.as_posix(),
    ):
        resolved_path, stat_result = static_files.lookup_path(path)
        assert resolved_path == ""
        assert stat_result is None


def test_render_spa_index_injects_escaped_runtime_config(tmp_path: Path) -> None:
    """入口页面应注入经过 HTML 转义的平台配置。"""

    index_file = tmp_path / "index.html"
    index_file.write_text(
        (
            '<meta name="platform-display-name" content="__PLATFORM_DISPLAY_NAME__">'
            '<meta name="api-v1-prefix" content="__API_V1_PREFIX__">'
            "<title>__PLATFORM_DISPLAY_NAME__</title>"
        ),
        encoding="utf-8",
    )

    html = render_spa_index(
        index_file,
        {
            "__PLATFORM_DISPLAY_NAME__": '和平 & "论坛" <测试>',
            "__API_V1_PREFIX__": "/custom/api",
        },
    )

    escaped_name = "和平 &amp; &quot;论坛&quot; &lt;测试&gt;"
    assert html.count(escaped_name) == 2
    assert 'content="/custom/api"' in html
    assert "__PLATFORM_DISPLAY_NAME__" not in html
    assert "__API_V1_PREFIX__" not in html


@pytest.mark.asyncio
async def test_spa_static_files_serves_injected_index_for_client_routes(
    tmp_path: Path,
) -> None:
    """首页和客户端路由应返回注入配置后的同一入口页面。"""

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("RAW INDEX", encoding="utf-8")
    static_files = SPAStaticFiles(
        directory=dist,
        html=True,
        index_html="CONFIGURED INDEX",
        excluded_prefixes=("/custom/api", "/uploads"),
    )
    for path in (".", "index.html", "posts/1"):
        response = await static_files.get_response(
            path,
            {"type": "http", "method": "GET", "path": f"/{path}", "headers": []},
        )
        assert response.body == b"CONFIGURED INDEX"

    with pytest.raises(HTTPException) as exc_info:
        await static_files.get_response(
            "custom/api/missing",
            {
                "type": "http",
                "method": "GET",
                "path": "/custom/api/missing",
                "headers": [],
            },
        )

    assert exc_info.value.status_code == 404
