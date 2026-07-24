"""通知 SSE 数据库会话生命周期回归测试。"""

from collections.abc import AsyncGenerator, Generator
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient

from social_platform.app.api import deps
from social_platform.app.api.routers import notifications


async def test_notification_stream_has_bounded_lifetime(monkeypatch) -> None:
    """通知 SSE 应使用短会话鉴权，并在达到生命周期上限后结束。"""

    session_closed = False

    class FakeSession:
        """记录通知摘要会话是否关闭。"""

        def close(self) -> None:
            """标记会话已关闭。"""

            nonlocal session_closed
            session_closed = True

    monkeypatch.setattr(notifications, "SessionLocal", FakeSession)
    monkeypatch.setattr(
        notifications.notification_service,
        "get_summary",
        lambda db, user_id: {
            "unread_count": 2,
            "following_count": 3,
            "followers_count": 4,
        },
    )
    monkeypatch.setattr(notifications, "_STREAM_MAX_LIFETIME_SECONDS", 0.0)

    app = FastAPI()
    app.include_router(notifications.router, prefix="/notifications")
    app.dependency_overrides[deps.get_current_user_id_for_stream] = lambda: 7

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/notifications/events")

    assert response.status_code == 200
    assert "notifications.changed" in response.text
    assert '"unread_count": 2' in response.text
    assert session_closed is True


async def test_stream_auth_session_closes_before_response_body(monkeypatch) -> None:
    """流式响应生成正文前应关闭鉴权所用的数据库会话。"""

    session_open = False

    def override_get_db() -> Generator[object, None, None]:
        """提供可观察关闭时机的测试会话。"""

        nonlocal session_open
        session_open = True
        try:
            yield object()
        finally:
            session_open = False

    monkeypatch.setattr(
        deps,
        "get_access_payload",
        lambda token, db, scope: {
            "sub": "7",
            "typ": "access",
            "scope": scope,
            "sid": "session-7",
        },
    )
    monkeypatch.setattr(
        deps,
        "_get_user_from_payload",
        lambda db, payload, include_banned=False: SimpleNamespace(id=7),
    )

    app = FastAPI()
    app.dependency_overrides[deps.get_db] = override_get_db

    @app.get("/events")
    async def stream_events(
        user_id: int = Depends(deps.get_current_user_id_for_stream),
    ) -> StreamingResponse:
        async def event_stream() -> AsyncGenerator[str, None]:
            state = "open" if session_open else "closed"
            yield f"{user_id}:{state}"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/events",
            headers={"Authorization": "Bearer access-token"},
        )

    assert response.status_code == 200
    assert response.text == "7:closed"
    assert session_open is False
