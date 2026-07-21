"""共享公开平台访问客户端测试。"""

from io import BytesIO
from unittest.mock import MagicMock, patch

from agents.logging_config import logging_context
from agents.platform_access import PlatformClient


def test_platform_client_adds_explicit_user_and_service_credentials() -> None:
    """共享客户端同时发送显式用户 Token 与可信 Agent 服务身份。"""

    response = MagicMock()
    response.status_code = 200
    response.content = b'{"ok": true}'
    response.json.return_value = {"ok": True}
    client = PlatformClient("http://platform/api/v1", "admin-secret")

    with patch("agents.platform_access.client.requests.request", return_value=response) as request:
        result = client.request("POST", "/posts/", access_token="user-token", json_data={"content": "x"})

    assert result == {"ok": True}
    headers = request.call_args.kwargs["headers"]
    assert headers == {
        "Content-Type": "application/json",
        "Authorization": "Bearer user-token",
        "X-Cosmos-Agent-Source": "agent",
        "X-Cosmos-Agent-Token": "admin-secret",
    }


def test_platform_client_uploads_file_without_overriding_multipart_content_type() -> None:
    """文件上传应让 requests 生成 multipart 边界，并保留用户与服务凭据。"""

    response = MagicMock()
    response.status_code = 200
    response.content = b'{"avatar_url": "uploads/avatar.png"}'
    response.json.return_value = {"avatar_url": "uploads/avatar.png"}
    client = PlatformClient("http://platform/api/v1", "admin-secret")
    image = BytesIO(b"png-data")

    with patch("agents.platform_access.client.requests.request", return_value=response) as request:
        result = client.upload_file(
            "/users/avatar",
            access_token="user-token",
            field_name="file",
            filename="avatar.png",
            file_object=image,
            content_type="image/png",
        )

    assert result == {"avatar_url": "uploads/avatar.png"}
    kwargs = request.call_args.kwargs
    assert "Content-Type" not in kwargs["headers"]
    assert kwargs["headers"]["Authorization"] == "Bearer user-token"
    assert kwargs["files"]["file"] == ("avatar.png", image, "image/png")


def test_platform_client_uploads_file_without_optional_content_type() -> None:
    """未提供 MIME 类型时应使用 requests 支持的二元文件规格。"""

    response = MagicMock()
    response.status_code = 200
    response.content = b'{"ok": true}'
    response.json.return_value = {"ok": True}
    client = PlatformClient("http://platform/api/v1", "admin-secret")
    image = BytesIO(b"image-data")

    with patch("agents.platform_access.client.requests.request", return_value=response) as request:
        result = client.upload_file(
            "/users/avatar",
            access_token="user-token",
            field_name="file",
            filename="avatar.bin",
            file_object=image,
            content_type=None,
        )

    assert result == {"ok": True}
    assert request.call_args.kwargs["files"]["file"] == ("avatar.bin", image)


def test_platform_client_propagates_current_request_id() -> None:
    """Agent 调用公开平台时应沿用当前会话的关联 ID。"""

    response = MagicMock(status_code=200, content=b'{"ok": true}')
    response.json.return_value = {"ok": True}
    client = PlatformClient("http://platform/api/v1", "admin-secret")

    with (
        logging_context(request_id="session-request-1"),
        patch("agents.platform_access.client.requests.request", return_value=response) as request,
    ):
        client.request("GET", "/feeds/", access_token="user-token")

    assert request.call_args.kwargs["headers"]["X-Request-ID"] == "session-request-1"
