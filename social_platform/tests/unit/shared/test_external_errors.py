"""外部 AI 错误对外格式化回归测试。"""

import pytest

from social_platform.app.shared.external_errors import format_external_error


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (RuntimeError("401 invalid API key SECRET_SENTINEL"), "AI_AUTH_ERROR"),
        (RuntimeError("429 quota exceeded SECRET_SENTINEL"), "AI_RATE_LIMITED"),
        (TimeoutError("SECRET_SENTINEL"), "AI_TIMEOUT"),
        (ConnectionError("SECRET_SENTINEL"), "AI_CONNECTION_ERROR"),
        (RuntimeError("503 provider failure SECRET_SENTINEL"), "AI_PROVIDER_ERROR"),
        (RuntimeError("SECRET_SENTINEL"), "AI_UNKNOWN_ERROR"),
    ],
)
def test_external_error_message_is_stable_and_hides_raw_provider_text(
    exc: BaseException,
    code: str,
) -> None:
    """安全错误包含稳定分类，但不包含原始供应商响应文本。"""

    safe = format_external_error(exc)
    assert safe.code == code
    assert "SECRET_SENTINEL" not in safe.message
