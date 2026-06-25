"""注册邀请码业务服务。

本模块被平台管理端用于生成和查询邀请码，也被公开注册流程用于校验邮箱与邀请码绑定关系。
"""

from __future__ import annotations

import re
import secrets
import string
from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import or_
from sqlalchemy.orm import Session

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.core.config import get_settings
from social_platform.app.domains.invitation.models import RegistrationInvitation
from social_platform.app.domains.invitation.schemas import InvitationCodeResponse
from social_platform.app.domains.user.models import User


_CODE_ALPHABET = string.ascii_uppercase + string.digits
_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9_-]{0,16}$")


class InvitationRequiredError(Exception):
    """邀请制开启但请求缺少邀请码。"""

    def __init__(self) -> None:
        """初始化缺少邀请码异常。"""

        super().__init__("当前注册需要邀请码")


class InvitationInvalidError(Exception):
    """邀请码不存在、邮箱不匹配或已被使用。"""

    def __init__(self) -> None:
        """初始化无效邀请码异常。"""

        super().__init__("邀请码无效或与邮箱不匹配")


def normalize_invitation_email(email: str) -> str:
    """规范化邀请码绑定邮箱。

    Args:
        email: 原始邮箱地址。

    Returns:
        str: 小写且去除首尾空白的邮箱地址。
    """

    return email.strip().lower()


def normalize_invitation_code(code: str) -> str:
    """规范化邀请码输入。

    Args:
        code: 用户或管理员输入的邀请码。

    Returns:
        str: 去除空白并转换为大写的邀请码。
    """

    return code.strip().upper()


def normalize_invitation_prefix(prefix: str) -> str:
    """校验并规范化邀请码前缀。

    Args:
        prefix: 管理员填写的邀请码前缀。

    Returns:
        str: 规范化后的大写前缀。

    Raises:
        ValueError: 前缀包含不支持字符或超过长度限制。
    """

    normalized_prefix = prefix.strip().upper()
    if not _PREFIX_PATTERN.fullmatch(normalized_prefix):
        raise ValueError("邀请码前缀只能包含字母、数字、短横线或下划线，最长 16 个字符")
    return normalized_prefix


def generate_invitation_code_suffix(length: int = 6) -> str:
    """生成邀请码六位随机字母数字后缀。

    Args:
        length: 后缀长度，默认 6 位。

    Returns:
        str: 大写字母和数字组成的随机字符串。
    """

    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def build_invitation_code(prefix: str, suffix: str) -> str:
    """按前缀和随机后缀构造完整邀请码。

    Args:
        prefix: 已规范化的邀请码前缀。
        suffix: 六位随机字母数字后缀。

    Returns:
        str: 有前缀时返回 ``PREFIX-SUFFIX``，无前缀时仅返回后缀。
    """

    return f"{prefix}-{suffix}" if prefix else suffix


def is_invitation_registration_enabled() -> bool:
    """读取邀请制注册开关。

    Returns:
        bool: 开启返回 True，否则返回 False。
    """

    return get_settings().INVITATION_REGISTRATION_ENABLED


def serialize_invitation(invitation: RegistrationInvitation) -> InvitationCodeResponse:
    """序列化邀请码记录。

    Args:
        invitation: 数据库邀请码模型。

    Returns:
        InvitationCodeResponse: 管理端响应对象。
    """

    return InvitationCodeResponse(
        id=invitation.id,
        email=invitation.email,
        code=invitation.code,
        prefix=invitation.prefix,
        status="used" if invitation.used_by_user_id else "unused",
        created_at=invitation.created_at,
        updated_at=invitation.updated_at,
        created_by_admin_id=invitation.created_by_admin_id,
        created_by_admin_username=(
            invitation.created_by_admin.username if invitation.created_by_admin else None
        ),
        used_by_user_id=invitation.used_by_user_id,
        used_by_username=invitation.used_by_user.username if invitation.used_by_user else None,
        used_at=invitation.used_at,
    )


def list_registration_invitations(
    db: Session,
    skip: int,
    limit: int,
    keyword: str | None = None,
) -> tuple[list[InvitationCodeResponse], int]:
    """分页读取注册邀请码。

    Args:
        db: 当前数据库会话。
        skip: 跳过数量。
        limit: 返回数量。
        keyword: 可选搜索关键字，匹配邮箱、邀请码或使用人用户名。

    Returns:
        tuple[list[InvitationCodeResponse], int]: 列表项和总数。
    """

    query = db.query(RegistrationInvitation).outerjoin(
        User,
        RegistrationInvitation.used_by_user_id == User.id,
    )
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                RegistrationInvitation.email.like(like),
                RegistrationInvitation.code.like(like),
                User.username.like(like),
            )
        )
    total = query.count()
    invitations = (
        query.order_by(RegistrationInvitation.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [serialize_invitation(invitation) for invitation in invitations], total


def create_registration_invitation(
    db: Session,
    email: str,
    prefix: str,
    admin: PlatformAdminUser,
) -> InvitationCodeResponse:
    """为指定邮箱创建注册邀请码。

    Args:
        db: 当前数据库会话。
        email: 绑定邮箱。
        prefix: 管理员填写的邀请码前缀。
        admin: 当前平台管理员。

    Returns:
        InvitationCodeResponse: 创建后的邀请码响应。

    Raises:
        ValueError: 邮箱已注册、已存在邀请码或前缀不合法。
    """

    normalized_email = normalize_invitation_email(email)
    if db.query(User).filter(User.email == normalized_email).first():
        raise ValueError("该邮箱已存在账号，不能生成邀请码")
    if (
        db.query(RegistrationInvitation)
        .filter(RegistrationInvitation.email == normalized_email)
        .first()
    ):
        raise ValueError("该邮箱已存在邀请码，不能重复生成")

    normalized_prefix = normalize_invitation_prefix(prefix)
    suffix = generate_invitation_code_suffix()
    code = build_invitation_code(normalized_prefix, suffix)
    while db.query(RegistrationInvitation).filter(RegistrationInvitation.code == code).first():
        suffix = generate_invitation_code_suffix()
        code = build_invitation_code(normalized_prefix, suffix)

    invitation = RegistrationInvitation(
        email=normalized_email,
        code=code,
        prefix=normalized_prefix,
        code_suffix=suffix,
        created_by_admin_id=admin.id,
        updated_at=local_now(),
    )
    db.add(invitation)
    db.flush()
    create_operation_log(
        db,
        admin,
        action="create_registration_invitation",
        target_type="registration_invitation",
        target_id=invitation.id,
        details={"email": normalized_email, "prefix": normalized_prefix},
    )
    db.commit()
    db.refresh(invitation)
    return serialize_invitation(invitation)


def get_required_registration_invitation(
    db: Session,
    email: str,
    invitation_code: str | None,
) -> RegistrationInvitation | None:
    """按配置校验注册请求的邀请码。

    Args:
        db: 当前数据库会话。
        email: 注册邮箱。
        invitation_code: 用户提交的邀请码。

    Returns:
        RegistrationInvitation | None: 开启邀请制时返回匹配记录，关闭时返回 None。

    Raises:
        InvitationRequiredError: 开启邀请制但未提交邀请码。
        InvitationInvalidError: 邀请码不存在、邮箱不匹配或已使用。
    """

    if not is_invitation_registration_enabled():
        return None
    if not invitation_code or not invitation_code.strip():
        raise InvitationRequiredError()

    normalized_email = normalize_invitation_email(email)
    normalized_code = normalize_invitation_code(invitation_code)
    invitation = (
        db.query(RegistrationInvitation)
        .filter(
            RegistrationInvitation.email == normalized_email,
            RegistrationInvitation.code == normalized_code,
        )
        .first()
    )
    if invitation is None or invitation.used_by_user_id is not None:
        raise InvitationInvalidError()
    return invitation


def consume_registration_invitation(
    db: Session,
    invitation: RegistrationInvitation | None,
    user_id: int,
) -> None:
    """把邀请码标记为已被指定用户使用。

    Args:
        db: 当前数据库会话。
        invitation: 已校验的邀请码；邀请制关闭时可为 None。
        user_id: 注册成功的用户 ID。

    Raises:
        InvitationInvalidError: 邀请码已被其他用户使用。
    """

    if invitation is None:
        return
    if invitation.used_by_user_id is not None:
        raise InvitationInvalidError()
    invitation.used_by_user_id = user_id
    invitation.used_at = local_now()
    invitation.updated_at = local_now()
