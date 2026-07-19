"""外部 AI 与搜索服务异常的安全格式化工具。

完整异常仅应由调用方使用 ``logger.exception`` 写入服务日志；本模块生成的结果
可安全写入数据库、操作日志以及 API/SSE 响应，避免供应商响应体或凭据泄露。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SafeExternalError:
    """可持久化和对外返回的稳定错误。"""

    code: str
    message: str


def format_external_error(exc: BaseException) -> SafeExternalError:
    """按异常类型和非敏感关键词归类外部服务错误。"""

    name = type(exc).__name__.lower()
    message = str(exc).lower()
    combined = f"{name} {message}"
    if any(token in combined for token in ("authentication", "unauthorized", "api key", "401")):
        return SafeExternalError("AI_AUTH_ERROR", "外部 AI 服务认证失败，请检查 API Key")
    if any(token in combined for token in ("rate", "quota", "credit", "429")):
        return SafeExternalError("AI_RATE_LIMITED", "外部 AI 服务限流或额度不足，请稍后重试")
    if any(token in combined for token in ("timeout", "timed out")):
        return SafeExternalError("AI_TIMEOUT", "外部 AI 服务响应超时，请稍后重试")
    if any(token in combined for token in ("connection", "connecterror", "network", "dns")):
        return SafeExternalError("AI_CONNECTION_ERROR", "无法连接外部 AI 服务，请检查网络与地址")
    if any(token in combined for token in ("badrequest", "invalid request", "400", "model not found")):
        return SafeExternalError("AI_INVALID_REQUEST", "外部 AI 服务拒绝了请求，请检查模型配置")
    if any(token in combined for token in ("server error", "internalserver", "502", "503", "504")):
        return SafeExternalError("AI_PROVIDER_ERROR", "外部 AI 服务暂时不可用，请稍后重试")
    return SafeExternalError("AI_UNKNOWN_ERROR", "外部 AI 服务调用失败，请检查后端日志")
