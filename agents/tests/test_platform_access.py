"""共享公开平台访问客户端测试。"""

from unittest.mock import MagicMock, patch

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
