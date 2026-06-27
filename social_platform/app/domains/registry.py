"""领域模型注册入口。

测试或迁移脚本在调用 ``Base.metadata.create_all`` 前导入本模块，确保已迁移
到各领域目录的 SQLAlchemy 模型完成注册。该模块不作为旧路径兼容层使用。
"""

from __future__ import annotations

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.domains.comment.models import Comment, CommentLike
from social_platform.app.domains.content_safety.models import (
    ContentModerationLLMSettings,
    ContentReport,
    ModerationAppeal,
    UserViolationEvent,
)
from social_platform.app.domains.follow.models import Follow
from social_platform.app.domains.hot_topic.models import HotTopic, HotTopicGeneration, HotTopicSettings
from social_platform.app.domains.identity.models import EmailVerificationCode, UserSession
from social_platform.app.domains.invitation.models import RegistrationInvitation
from social_platform.app.domains.notification.models import Notification
from social_platform.app.domains.post.models import PollOption, PollVote, Post
from social_platform.app.domains.reaction.models import Like
from social_platform.app.domains.topic.models import PostTopic, Topic
from social_platform.app.domains.user.models import User

__all__ = [
    "Comment",
    "CommentLike",
    "ContentModerationLLMSettings",
    "ContentReport",
    "ModerationAppeal",
    "UserViolationEvent",
    "Follow",
    "HotTopic",
    "HotTopicGeneration",
    "HotTopicSettings",
    "EmailVerificationCode",
    "Like",
    "Notification",
    "PlatformAdminUser",
    "PollOption",
    "PollVote",
    "Post",
    "PostTopic",
    "RegistrationInvitation",
    "User",
    "UserSession",
    "Topic",
]
