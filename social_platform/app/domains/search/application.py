"""搜索领域应用服务兼容入口。"""

from __future__ import annotations

from social_platform.app.services.search_service import (  # noqa: F401
    ensure_search_indexes,
    rebuild_search_indexes,
    search_content,
    search_users,
)
