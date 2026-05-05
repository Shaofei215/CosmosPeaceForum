import pytest
from unittest.mock import patch, MagicMock
import requests

from agents.agents_scheduler.langgraph.tools.utils import (
    _get_api_base_url,
    _make_request,
    _get_follow_status_text,
    _expand_username_by_relation,
    _expand_content_mentions_by_relation,
    _standardize_post,
    _standardize_comment,
    _standardize_notification,
    _standardize_posts_list,
    _standardize_comments_list,
    _get_current_user,
    _get_user,
    _get_post,
    _get_comment,
    _get_post_comments,
    _get_comment_replies,
    _get_user_posts,
    _get_global_feed,
    get_social_tools,
    get_all_tools_for_summarize,
)
from agents.agents_scheduler.langgraph.tools.types import (
    ToolExecutionError,
    AuthenticationError,
    NotFoundError,
    UnauthorizedError,
)


class TestGetApiBaseUrl:
    def test_get_api_base_url(self):
        with patch("agents.agents_scheduler.scheduler.config.get_scheduler_config") as mock_config:
            mock_config.return_value.api_base_url = "http://localhost:8000"
            result = _get_api_base_url()
            assert result == "http://localhost:8000"


class TestMakeRequest:
    @patch("agents.agents_scheduler.langgraph.tools.utils.requests.request")
    @patch("agents.agents_scheduler.langgraph.tools.utils.get_current_token")
    @patch("agents.agents_scheduler.langgraph.tools.utils._get_api_base_url")
    def test_make_request_success(self, mock_base_url, mock_token, mock_request):
        mock_base_url.return_value = "http://localhost:8000"
        mock_token.return_value = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response

        result = _make_request("GET", "/users/1")
        assert result == {"status": "ok"}
        mock_request.assert_called_once_with(
            method="GET",
            url="http://localhost:8000/users/1",
            headers={"Content-Type": "application/json", "Authorization": "Bearer test_token"},
            json=None,
            params=None,
            timeout=30
        )

    @patch("agents.agents_scheduler.langgraph.tools.utils.requests.request")
    @patch("agents.agents_scheduler.langgraph.tools.utils.get_current_token")
    @patch("agents.agents_scheduler.langgraph.tools.utils._get_api_base_url")
    def test_make_request_401(self, mock_base_url, mock_token, mock_request):
        mock_base_url.return_value = "http://localhost:8000"
        mock_token.return_value = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_request.return_value = mock_response

        with pytest.raises(AuthenticationError):
            _make_request("GET", "/users/1")

    @patch("agents.agents_scheduler.langgraph.tools.utils.requests.request")
    @patch("agents.agents_scheduler.langgraph.tools.utils.get_current_token")
    @patch("agents.agents_scheduler.langgraph.tools.utils._get_api_base_url")
    def test_make_request_404(self, mock_base_url, mock_token, mock_request):
        mock_base_url.return_value = "http://localhost:8000"
        mock_token.return_value = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b'{"detail": "Not found"}'
        mock_response.json.return_value = {"detail": "Not found"}
        mock_request.return_value = mock_response

        with pytest.raises(NotFoundError):
            _make_request("GET", "/users/999")

    @patch("agents.agents_scheduler.langgraph.tools.utils.requests.request")
    @patch("agents.agents_scheduler.langgraph.tools.utils.get_current_token")
    @patch("agents.agents_scheduler.langgraph.tools.utils._get_api_base_url")
    def test_make_request_500(self, mock_base_url, mock_token, mock_request):
        mock_base_url.return_value = "http://localhost:8000"
        mock_token.return_value = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b'{"detail": "Server error"}'
        mock_response.json.return_value = {"detail": "Server error"}
        mock_request.return_value = mock_response

        with pytest.raises(ToolExecutionError):
            _make_request("GET", "/users/1")

    @patch("agents.agents_scheduler.langgraph.tools.utils.requests.request")
    @patch("agents.agents_scheduler.langgraph.tools.utils.get_current_token")
    @patch("agents.agents_scheduler.langgraph.tools.utils._get_api_base_url")
    def test_make_request_connection_error(self, mock_base_url, mock_token, mock_request):
        mock_base_url.return_value = "http://localhost:8000"
        mock_token.return_value = "test_token"
        mock_request.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(ToolExecutionError):
            _make_request("GET", "/users/1")

    @patch("agents.agents_scheduler.langgraph.tools.utils.requests.request")
    @patch("agents.agents_scheduler.langgraph.tools.utils.get_current_token")
    @patch("agents.agents_scheduler.langgraph.tools.utils._get_api_base_url")
    def test_make_request_timeout(self, mock_base_url, mock_token, mock_request):
        mock_base_url.return_value = "http://localhost:8000"
        mock_token.return_value = "test_token"
        mock_request.side_effect = requests.exceptions.Timeout()

        with pytest.raises(ToolExecutionError):
            _make_request("GET", "/users/1")

    @patch("agents.agents_scheduler.langgraph.tools.utils.requests.request")
    @patch("agents.agents_scheduler.langgraph.tools.utils.get_current_token")
    @patch("agents.agents_scheduler.langgraph.tools.utils._get_api_base_url")
    def test_make_request_with_token_param(self, mock_base_url, mock_token, mock_request):
        mock_base_url.return_value = "http://localhost:8000"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response

        _make_request("GET", "/users/1", token="custom_token")
        mock_token.assert_not_called()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer custom_token"

    @patch("agents.agents_scheduler.langgraph.tools.utils.requests.request")
    @patch("agents.agents_scheduler.langgraph.tools.utils.get_current_token")
    @patch("agents.agents_scheduler.langgraph.tools.utils._get_api_base_url")
    def test_make_request_no_token(self, mock_base_url, mock_token, mock_request):
        mock_base_url.return_value = "http://localhost:8000"
        mock_token.return_value = None
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response

        _make_request("GET", "/users/1")
        call_kwargs = mock_request.call_args[1]
        assert "Authorization" not in call_kwargs["headers"]

    @patch("agents.agents_scheduler.langgraph.tools.utils.requests.request")
    @patch("agents.agents_scheduler.langgraph.tools.utils.get_current_token")
    @patch("agents.agents_scheduler.langgraph.tools.utils._get_api_base_url")
    def test_make_request_empty_response(self, mock_base_url, mock_token, mock_request):
        mock_base_url.return_value = "http://localhost:8000"
        mock_token.return_value = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b''
        mock_request.return_value = mock_response

        result = _make_request("POST", "/users/1", json_data={"name": "test"})
        assert result == {}


class TestStandardizePost:
    def test_standardize_post_basic(self):
        post_data = {
            "id": 1,
            "author_id": 10,
            "author_name": "testuser",
            "content": "hello world",
            "created_at": "2024-01-01",
            "like_count": 5,
            "comment_count": 3,
            "is_liked": False,
            "author_bio": "bio text"
        }
        with patch("agents.agents_scheduler.langgraph.tools.utils._expand_username_by_relation", return_value="testuser"), \
             patch("agents.agents_scheduler.langgraph.tools.utils._expand_content_mentions_by_relation", return_value="hello world"), \
             patch("agents.agents_scheduler.langgraph.tools.utils._get_follow_status_text", return_value=""):
            result = _standardize_post(post_data)
            assert result["id"] == 1
            assert result["author_id"] == 10
            assert result["author_username"] == "testuser"
            assert result["content"] == "hello world"
            assert result["like_count"] == 5
            assert result["comment_count"] == 3
            assert result["is_liked"] is False

    def test_standardize_post_with_nested_author(self):
        post_data = {
            "id": 1,
            "author": {"username": "nested_user", "bio": "nested bio"},
            "content": "test",
            "created_at": "",
            "like_count": 0,
            "comment_count": 0,
            "is_liked": True,
        }
        with patch("agents.agents_scheduler.langgraph.tools.utils._expand_username_by_relation", return_value="nested_user"), \
             patch("agents.agents_scheduler.langgraph.tools.utils._expand_content_mentions_by_relation", return_value="test"), \
             patch("agents.agents_scheduler.langgraph.tools.utils._get_follow_status_text", return_value=""):
            result = _standardize_post(post_data)
            assert result["author_username"] == "nested_user"
            assert result["author_bio"] == "nested bio"


class TestStandardizeComment:
    def test_standardize_comment_basic(self):
        comment_data = {
            "id": 1,
            "owner_id": 10,
            "owner": {"username": "commenter"},
            "content": "good post",
            "created_at": "2024-01-01",
            "parent_id": None,
            "like_count": 2,
            "reply_count": 1,
            "is_liked": False,
        }
        with patch("agents.agents_scheduler.langgraph.tools.utils._expand_username_by_relation", return_value="commenter"), \
             patch("agents.agents_scheduler.langgraph.tools.utils._expand_content_mentions_by_relation", return_value="good post"):
            result = _standardize_comment(comment_data)
            assert result["id"] == 1
            assert result["author_id"] == 10
            assert result["author_username"] == "commenter"
            assert result["content"] == "good post"
            assert result["like_count"] == 2
            assert result["reply_count"] == 1


class TestStandardizeNotification:
    def test_standardize_notification_includes_sender_follow_status(self):
        notification_data = {
            "id": 1,
            "type": "follow",
            "sender": {"id": 10, "username": "sender", "bio": "bio"},
            "resource_type": "user",
            "resource_id": 10,
            "source_content": None,
            "is_read": False,
            "created_at": "2024-01-01",
        }
        with patch("agents.agents_scheduler.langgraph.tools.utils._expand_username_by_relation", return_value="sender"), \
             patch("agents.agents_scheduler.langgraph.tools.utils._expand_content_mentions_by_relation", return_value=""), \
             patch("agents.agents_scheduler.langgraph.tools.utils._get_follow_status_text", return_value="未关注"):
            result = _standardize_notification(notification_data, current_user_id=99)
            assert result["sender_id"] == 10
            assert result["sender_username"] == "sender"
            assert result["sender_follow_status"] == "未关注"


class TestStandardizeLists:
    def test_standardize_posts_list(self):
        posts = [
            {"id": 1, "author_name": "user1", "content": "post1", "created_at": "", "like_count": 0, "comment_count": 0, "is_liked": False},
            {"id": 2, "author_name": "user2", "content": "post2", "created_at": "", "like_count": 0, "comment_count": 0, "is_liked": True},
        ]
        with patch("agents.agents_scheduler.langgraph.tools.utils._standardize_post") as mock_std:
            mock_std.return_value = {"id": 0}
            result = _standardize_posts_list(posts)
            assert len(result) == 2
            assert mock_std.call_count == 2

    def test_standardize_comments_list(self):
        comments = [
            {"id": 1, "owner": {"username": "u1"}, "owner_id": 1, "content": "c1", "created_at": "", "parent_id": None, "like_count": 0, "reply_count": 0, "is_liked": False},
            {"id": 2, "owner": {"username": "u2"}, "owner_id": 2, "content": "c2", "created_at": "", "parent_id": None, "like_count": 0, "reply_count": 0, "is_liked": False},
        ]
        with patch("agents.agents_scheduler.langgraph.tools.utils._standardize_comment") as mock_std:
            mock_std.return_value = {"id": 0}
            result = _standardize_comments_list(comments)
            assert len(result) == 2
            assert mock_std.call_count == 2


class TestGetSocialTools:
    def test_get_social_tools_returns_list(self):
        tools = get_social_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_social_tools_does_not_contain_write_memory(self):
        tools = get_social_tools()
        tool_names = [t.name.lower() for t in tools]
        assert "write_memory" not in tool_names

    def test_get_social_tools_contains_expected_tools(self):
        tools = get_social_tools()
        tool_names = [t.name.lower() for t in tools]
        expected_names = [
            "get_profile", "toggle_post_like", "toggle_comment_like",
            "create_comment", "toggle_follow", "create_post", "logout",
            "get_user_profile", "get_global_feed", "expand_post",
            "expand_comments", "get_post_detail", "scroll_global_feed",
            "scroll_user_posts",
        ]
        for name in expected_names:
            assert name in tool_names, f"Missing tool: {name}"

    def test_get_social_tools_caching(self):
        tools1 = get_social_tools()
        tools2 = get_social_tools()
        assert tools1 is tools2

    def test_get_social_tools_with_relation_map(self):
        mock_relation_map = MagicMock()
        tools = get_social_tools(relation_map=mock_relation_map)
        assert isinstance(tools, list)
        assert len(tools) > 0


class TestGetAllToolsForSummarize:
    def test_get_all_tools_for_summarize_returns_list(self):
        tools = get_all_tools_for_summarize()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_all_tools_for_summarize_contains_write_memory(self):
        tools = get_all_tools_for_summarize()
        tool_names = [t.name.lower() for t in tools]
        assert "write_memory" in tool_names

    def test_get_all_tools_for_summarize_only_write_memory(self):
        tools = get_all_tools_for_summarize()
        tool_names = [t.name.lower() for t in tools]
        assert tool_names == ["write_memory"]
