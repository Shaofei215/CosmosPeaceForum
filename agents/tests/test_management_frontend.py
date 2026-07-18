"""管理前端构建产物与后端运行时配置衔接测试。"""

from pathlib import Path

from agents.management.backend.main import render_management_index


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
