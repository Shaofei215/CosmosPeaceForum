# 模型包初始化
# 导入所有模型以确保 SQLAlchemy 正确注册

from app_platform.app.models.user import User
from app_platform.app.models.post import Post
from app_platform.app.models.like import Like
from app_platform.app.models.comment import Comment, CommentLike
from app_platform.app.models.follow import Follow
from app_platform.app.models.email_verification import EmailVerificationCode
from app_platform.app.models.notification import Notification

__all__ = [
    "User",
    "Post",
    "Like",
    "Comment",
    "CommentLike",
    "Follow",
    "EmailVerificationCode",
    "Notification",
]
