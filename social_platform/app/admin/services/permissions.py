PERMISSION_VIEW_DASHBOARD = "view_dashboard"
PERMISSION_MANAGE_USERS = "manage_users"
PERMISSION_MANAGE_CONTENT = "manage_content"
PERMISSION_MANAGE_ADMINS = "manage_admins"
PERMISSION_VIEW_LOGS = "view_logs"

ALL_PERMISSIONS = [
    PERMISSION_VIEW_DASHBOARD,
    PERMISSION_MANAGE_USERS,
    PERMISSION_MANAGE_CONTENT,
    PERMISSION_MANAGE_ADMINS,
    PERMISSION_VIEW_LOGS,
]


def normalize_permissions(permissions: list[str] | None) -> list[str]:
    """过滤未知权限并保持稳定顺序。"""
    allowed = set(permissions or [])
    return [permission for permission in ALL_PERMISSIONS if permission in allowed]

