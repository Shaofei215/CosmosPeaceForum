# 验证码清理定时任务
# 定期清理过期的验证码记录，防止数据库膨胀
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.email_verification import EmailVerificationCode
from app.db.session import SessionLocal


def cleanup_expired_verification_codes():
    """
    清理过期的验证码记录

    删除以下记录：
    - 已使用的验证码（超过7天）
    - 已过期的验证码（超过7天）

    保留最近7天内的记录，以便审计和问题排查
    """
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=7)

        expired_codes = db.query(EmailVerificationCode).filter(
            and_(
                (
                    EmailVerificationCode.used == True
                ) | (
                    EmailVerificationCode.expires_at < datetime.utcnow()
                ),
                EmailVerificationCode.created_at < cutoff_date
            )
        ).all()

        count = len(expired_codes)

        if count > 0:
            for code in expired_codes:
                db.delete(code)

            db.commit()
            print(f"[清理任务] 已删除 {count} 条过期验证码记录")
        else:
            print(f"[清理任务] 无需清理的过期验证码记录")

    except Exception as e:
        db.rollback()
        print(f"[清理任务] 清理失败: {e}")
    finally:
        db.close()
