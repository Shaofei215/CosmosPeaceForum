PERMISSION_VIEW_DASHBOARD = "view_dashboard"
PERMISSION_MANAGE_AGENTS = "manage_agents"
PERMISSION_MANAGE_MODELS = "manage_models"
PERMISSION_MANAGE_MEMORIES = "manage_memories"
PERMISSION_MANAGE_PROMPTS = "manage_prompts"
PERMISSION_MANAGE_SYSTEM = "manage_system"
PERMISSION_MANAGE_ADMINS = "manage_admins"
PERMISSION_VIEW_LOGS = "view_logs"

ALL_PERMISSIONS = [
    PERMISSION_VIEW_DASHBOARD,
    PERMISSION_MANAGE_AGENTS,
    PERMISSION_MANAGE_MODELS,
    PERMISSION_MANAGE_MEMORIES,
    PERMISSION_MANAGE_PROMPTS,
    PERMISSION_MANAGE_SYSTEM,
    PERMISSION_MANAGE_ADMINS,
    PERMISSION_VIEW_LOGS,
]


def normalize_permissions(permissions: list[str] | None) -> list[str]:
    """过滤未知权限并保持稳定顺序。"""
    allowed = set(permissions or [])
    return [permission for permission in ALL_PERMISSIONS if permission in allowed]
