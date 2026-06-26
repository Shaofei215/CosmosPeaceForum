from fastapi import APIRouter

from social_platform.app.admin.api import (
    announcements,
    admins,
    auth,
    content,
    dashboard,
    hot_topics,
    logs,
    users,
)

admin_router = APIRouter(prefix="/admin")

admin_router.include_router(auth.router)
admin_router.include_router(dashboard.router)
admin_router.include_router(users.router)
admin_router.include_router(content.router)
admin_router.include_router(hot_topics.router)
admin_router.include_router(announcements.router)
admin_router.include_router(admins.router)
admin_router.include_router(logs.router)

__all__ = ["admin_router"]
