# 验证码清理定时任务
# 定期清理过期的验证码记录，防止数据库膨胀
import logging
from datetime import timedelta

from sqlalchemy import and_

from social_platform.app.core.timezone import local_now
from social_platform.app.db.session import SessionLocal
from social_platform.app.domains.identity.models import EmailVerificationCode

logger = logging.getLogger(__name__)


def cleanup_expired_verification_codes() -> None:
    """
    清理过期的验证码记录

    删除以下记录：
    - 已使用的验证码（超过7天）
    - 已过期的验证码（超过7天）

    保留最近7天内的记录，以便审计和问题排查
    """
    db = SessionLocal()
    try:
        cutoff_date = local_now() - timedelta(days=7)

        expired_codes = db.query(EmailVerificationCode).filter(
            and_(
                (
                    EmailVerificationCode.used.is_(True)
                ) | (
                    EmailVerificationCode.expires_at < local_now()
                ),
                EmailVerificationCode.created_at < cutoff_date
            )
        ).all()

        count = len(expired_codes)

        if count > 0:
            for code in expired_codes:
                db.delete(code)

            db.commit()
            logger.info("已删除 %s 条过期验证码记录", count)
        else:
            logger.info("无需清理的过期验证码记录")

    except Exception:
        db.rollback()
        logger.exception("验证码清理失败")
    finally:
        db.close()
