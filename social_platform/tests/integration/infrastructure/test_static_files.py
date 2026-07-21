"""公开平台 SPA 静态文件目录边界回归测试。"""

from social_platform.app.core.static_files import SPAStaticFiles


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
