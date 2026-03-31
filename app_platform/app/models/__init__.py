# 模型包初始化
# 导入所有模型以确保 SQLAlchemy 正确注册

from app.models.user import User
from app.models.post import Post
from app.models.like import Like
from app.models.comment import Comment, CommentLike
from app.models.follow import Follow
from app.models.email_verification import EmailVerificationCode

__all__ = [
    "User",
    "Post",
    "Like",
    "Comment",
    "CommentLike",
    "Follow",
    "EmailVerificationCode",
]
