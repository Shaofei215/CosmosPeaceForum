import sys
import types
from unittest.mock import MagicMock, patch

from agents.agents_scheduler.langgraph.tools.web_search import (
    merge_web_search_result,
    web_search,
)


class TestWebSearch:
    @patch("agents.agents_scheduler.langgraph.tools.web_search.get_session_config")
    def test_web_search_disabled(self, mock_config):
        mock_config.return_value = MagicMock(web_search_enabled=False, tavily_api_key="")

        result = web_search.invoke({"query": "Tavily LangChain"})

        assert result["action"] == "联网搜索未启用，无法检索网络信息"
        assert result["data"]["results"] == []

    @patch("agents.agents_scheduler.langgraph.tools.web_search.get_session_config")
    def test_web_search_missing_api_key(self, mock_config):
        mock_config.return_value = MagicMock(web_search_enabled=True, tavily_api_key="")

        result = web_search.invoke({"query": "Tavily LangChain"})

        assert result["action"] == "Tavily API Key 未配置，无法联网搜索"
        assert result["data"]["total"] == 0

    @patch("agents.agents_scheduler.langgraph.tools.web_search.get_session_config")
    def test_web_search_success_with_fake_tavily(self, mock_config, monkeypatch):
        mock_config.return_value = MagicMock(web_search_enabled=True, tavily_api_key="test-key")

        fake_module = types.ModuleType("langchain_tavily")

        class FakeTavilySearch:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def invoke(self, args):
                assert args["query"] == "LangChain Tavily"
                assert args["search_depth"] == "advanced"
                return {
                    "answer": "Tavily can be used as a LangChain tool.",
                    "results": [
                        {
                            "title": "Tavily search integration",
                            "url": "https://docs.langchain.com/",
                            "content": "Integrate with Tavily.",
                            "score": 0.9,
                        }
                    ],
                    "response_time": 0.1,
                }

        fake_module.TavilySearch = FakeTavilySearch
        monkeypatch.setitem(sys.modules, "langchain_tavily", fake_module)

        result = web_search.invoke({
            "query": "LangChain Tavily",
            "max_results": 3,
            "search_depth": "depth",
        })

        assert result["action"] == "联网搜索了「LangChain Tavily」，获得1条结果"
        assert result["data"]["search_depth"] == "advanced"
        assert result["data"]["max_results"] == 3
        assert result["data"]["results"][0]["title"] == "Tavily search integration"

    def test_web_search_tool_name(self):
        assert web_search.name == "web_search"


class TestWebSearchResultHelpers:
    def test_merge_web_search_result_wraps_previous_result(self):
        previous = {"post": {"id": 1, "content": "hello"}}
        search = {"query": "hello", "results": [{"title": "Hello"}], "total": 1}

        result = merge_web_search_result(previous, search)

        assert result["current_view"] == previous
        assert result["explicit_recalls"] == []
        assert result["web_searches"] == [search]

    def test_merge_web_search_result_keeps_existing_recalls(self):
        previous = {
            "current_view": {"post": {"id": 1}},
            "explicit_recalls": [{"query": "first", "memories": [], "total": 0}],
            "web_searches": [],
        }
        search = {"query": "second", "results": [], "total": 0}

        result = merge_web_search_result(previous, search)

        assert result["current_view"] == {"post": {"id": 1}}
        assert [item["query"] for item in result["explicit_recalls"]] == ["first"]
        assert result["web_searches"] == [search]
