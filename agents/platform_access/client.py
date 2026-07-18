"""显式凭据的公开平台 HTTP 客户端。

本模块不读取 Scheduler 线程上下文，只接收调用方传入的 Access Token。客户端统一
附加 agents 服务来源证明、设置超时并把上游错误转换为不含敏感 Header 的稳定异常。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, BinaryIO

import requests

from agents.platform_access.presenters import normalize_platform_response


def build_agent_service_headers(admin_key: str) -> dict[str, str]:
    """构造可信 Agent 来源 Header；未配置 Secret 时返回空字典。

    Args:
        admin_key: agents 与公开平台共享的管理密钥。

    Returns:
        dict[str, str]: 可合并到内部 HTTP 请求的来源 Header。
    """

    if not admin_key:
        return {}
    return {
        "X-Cosmos-Agent-Source": "agent",
        "X-Cosmos-Agent-Token": admin_key,
    }


@dataclass
class PlatformAccessError(Exception):
    """公开平台请求失败。

    Args:
        message: 可安全记录和展示的错误摘要。
        status_code: 上游 HTTP 状态码；网络错误时为空。
        detail: 上游返回的公开错误详情。
    """

    message: str
    status_code: int | None = None
    detail: str | None = None

    def __str__(self) -> str:
        """返回不包含 Token、Header 或内部 URL 的错误文本。"""

        return self.message


class PlatformAuthenticationError(PlatformAccessError):
    """Access Token 无效或已过期。"""


class PlatformNotFoundError(PlatformAccessError):
    """公开平台资源不存在。"""


class PlatformConnectionError(PlatformAccessError):
    """无法连接公开平台。"""


class PlatformTimeoutError(PlatformAccessError):
    """公开平台请求超时。"""


class PlatformClient:
    """使用显式 Access Token 调用公开平台。

    Args:
        base_url: 公开平台 API 根地址，例如 ``http://social-platform:8000/api/v1``。
        admin_key: 与公开平台共享的 ``ADMIN_KEY``。
        timeout_seconds: 单次请求超时秒数。
    """

    def __init__(self, base_url: str, admin_key: str, timeout_seconds: float = 30) -> None:
        self._base_url = base_url.rstrip("/")
        self._admin_key = admin_key
        self._timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        access_token: str | None,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        """执行平台请求并返回标准化后的 JSON 数据。

        Args:
            method: HTTP 方法。
            endpoint: 以 ``/`` 开头的平台 API 相对路径。
            access_token: 当前公开平台用户的 Access Token；公开读取可为空。
            json_data: 可选 JSON 请求体。
            params: 可选查询参数。

        Returns:
            Any: JSON 对象、数组或空响应对应的空字典。

        Raises:
            PlatformAuthenticationError: 上游返回 401。
            PlatformNotFoundError: 上游返回 404。
            PlatformAccessError: 其他 4xx/5xx 响应。
            PlatformConnectionError: 连接失败。
            PlatformTimeoutError: 请求超时。
        """

        headers = {"Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        headers.update(build_agent_service_headers(self._admin_key))
        if extra_headers:
            headers.update(extra_headers)

        try:
            response = requests.request(
                method=method,
                url=f"{self._base_url}{endpoint}",
                headers=headers,
                json=json_data,
                params=params,
                timeout=self._timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise PlatformTimeoutError("API 请求超时，请稍后重试") from exc
        except requests.exceptions.ConnectionError as exc:
            raise PlatformConnectionError("无法连接到 API 服务器，请检查网络连接") from exc
        except requests.exceptions.RequestException as exc:
            raise PlatformAccessError("平台请求异常") from exc

        return self._decode_response(response)

    def upload_file(
        self,
        endpoint: str,
        *,
        access_token: str,
        field_name: str,
        filename: str,
        file_object: BinaryIO,
        content_type: str | None,
    ) -> Any:
        """以 multipart/form-data 向公开平台上传单个文件。

        该方法只接收已经确定的平台相对路径，供头像等受控网关入口使用；文件类型、
        大小和业务权限仍由公开平台验证。

        Args:
            endpoint: 以 ``/`` 开头的平台 API 相对路径。
            access_token: 当前公开平台用户的 Access Token。
            field_name: 上游 multipart 文件字段名。
            filename: 对外提交的文件名。
            file_object: 可读取的二进制文件对象。
            content_type: 客户端声明的 MIME 类型。

        Returns:
            Any: 标准化后的公开平台 JSON 响应。

        Raises:
            PlatformAccessError: 上游返回错误响应或请求异常。
            PlatformConnectionError: 无法连接公开平台。
            PlatformTimeoutError: 请求超时。
        """

        headers = build_agent_service_headers(self._admin_key)
        headers["Authorization"] = f"Bearer {access_token}"
        file_spec = (
            (filename, file_object, content_type)
            if content_type is not None
            else (filename, file_object)
        )
        try:
            response = requests.request(
                method="POST",
                url=f"{self._base_url}{endpoint}",
                headers=headers,
                files={field_name: file_spec},
                timeout=self._timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise PlatformTimeoutError("API 请求超时，请稍后重试") from exc
        except requests.exceptions.ConnectionError as exc:
            raise PlatformConnectionError("无法连接到 API 服务器，请检查网络连接") from exc
        except requests.exceptions.RequestException as exc:
            raise PlatformAccessError("平台请求异常") from exc

        return self._decode_response(response)

    def _decode_response(self, response: requests.Response) -> Any:
        """校验并解析公开平台响应。

        Args:
            response: requests 返回的 HTTP 响应。

        Returns:
            Any: JSON 对象、数组或空响应对应的空字典。

        Raises:
            PlatformAuthenticationError: 上游返回 401。
            PlatformNotFoundError: 上游返回 404。
            PlatformAccessError: 其他 4xx/5xx 响应。
        """

        detail = self._response_detail(response)
        if response.status_code == 401:
            raise PlatformAuthenticationError(
                "认证失败，Token 可能已过期，请重新登录",
                status_code=401,
                detail=detail,
            )
        if response.status_code == 404:
            raise PlatformNotFoundError("资源不存在", status_code=404, detail=detail)
        if response.status_code >= 400:
            raise PlatformAccessError(
                f"请求失败 ({response.status_code})",
                status_code=response.status_code,
                detail=detail,
            )
        if not response.content:
            return {}
        return normalize_platform_response(response.json())

    @staticmethod
    def _response_detail(response: requests.Response) -> str:
        """提取公开错误详情，解析失败时回退到响应正文。"""

        if not response.content:
            return ""
        try:
            payload = response.json()
        except ValueError:
            return response.text
        if isinstance(payload, dict):
            return str(payload.get("detail", payload.get("message", response.text)))
        return response.text
