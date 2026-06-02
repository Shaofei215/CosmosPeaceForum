# 模型包初始化
# 导入所有模型以确保 SQLAlchemy 正确注册

from social_platform.app.models.user import User
from social_platform.app.models.post import Post
from social_platform.app.models.like import Like
from social_platform.app.models.comment import Comment, CommentLike
from social_platform.app.models.follow import Follow
from social_platform.app.models.email_verification import EmailVerificationCode
from social_platform.app.models.notification import Notification
from social_platform.app.models.theme import PlatformThemeSettings
from social_platform.app.models.hot_topic import HotTopic, HotTopicGeneration, HotTopicSettings
from social_platform.app.models.content_report import ContentReport
from social_platform.app.models.content_moderation_llm import ContentModerationLLMSettings

__all__ = [
    "User",
    "Post",
    "Like",
    "Comment",
    "CommentLike",
    "Follow",
    "EmailVerificationCode",
    "Notification",
    "PlatformThemeSettings",
    "HotTopic",
    "HotTopicGeneration",
    "HotTopicSettings",
    "ContentReport",
    "ContentModerationLLMSettings",
]
