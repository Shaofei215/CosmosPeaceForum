import sys
import types
from types import SimpleNamespace
from unittest.mock import patch

from agents.agents_scheduler.langgraph.tools.web_search import web_search


def _config(**overrides):
    values = {
        "web_search_enabled": True,
        "tavily_api_key": "test-key",
        "tavily_topic": "",
        "tavily_max_results": None,
        "tavily_search_depth": "",
        "tavily_include_domains": "",
        "tavily_exclude_domains": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TestWebSearch:
    @patch("agents.agents_scheduler.langgraph.tools.web_search.get_session_config")
    def test_web_search_disabled(self, mock_config):
        mock_config.return_value = _config(web_search_enabled=False, tavily_api_key="")

        result = web_search.invoke({"query": "Tavily LangChain"})

        assert result["action"] == "联网搜索未启用，无法检索网络信息"
        assert result["data"]["results"] == []

    @patch("agents.agents_scheduler.langgraph.tools.web_search.get_session_config")
    def test_web_search_missing_api_key(self, mock_config):
        mock_config.return_value = _config(tavily_api_key="")

        result = web_search.invoke({"query": "Tavily LangChain"})

        assert result["action"] == "Tavily API Key 未配置，无法联网搜索"
        assert result["data"]["topic"] == "general"
        assert result["data"]["max_results"] == 10
        assert result["data"]["results"] == []

    @patch("agents.agents_scheduler.langgraph.tools.web_search.get_session_config")
    def test_web_search_success_with_fake_tavily(self, mock_config, monkeypatch):
        mock_config.return_value = _config(
            tavily_topic="news",
            tavily_max_results=2,
            tavily_search_depth="basic",
            tavily_include_domains="example.com, docs.example.com",
            tavily_exclude_domains="spam.example",
        )

        fake_module = types.ModuleType("langchain_tavily")
        captured = {}

        class FakeTavilySearch:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                captured["init"] = kwargs

            def invoke(self, args):
                captured["invoke"] = args
                assert args["query"] == "LangChain Tavily"
                return {
                    "answer": "Tavily can be used as a LangChain tool.",
                    "results": [
                        {
                            "title": "Tavily search integration",
                            "url": "https://docs.langchain.com/",
                            "content": "Integrate with Tavily.",
                            "score": 0.9,
                            "published_date": "2026-07-29",
                        }
                    ],
                    "response_time": 0.1,
                }

        fake_module.TavilySearch = FakeTavilySearch
        monkeypatch.setitem(sys.modules, "langchain_tavily", fake_module)

        result = web_search.invoke({
            "query": "LangChain Tavily",
            "topic": "finance",
            "max_results": 7,
            "search_depth": "advanced",
            "time_range": "week",
            "include_domains": ["llm.example"],
            "exclude_domains": ["llm-spam.example"],
        })

        assert result["action"] == "联网搜索了「LangChain Tavily」"
        assert captured["init"]["max_results"] == 2
        assert captured["invoke"] == {
            "query": "LangChain Tavily",
            "topic": "news",
            "search_depth": "basic",
            "time_range": "week",
            "include_domains": ["example.com", "docs.example.com"],
            "exclude_domains": ["spam.example"],
        }
        assert result["data"]["topic"] == "news"
        assert result["data"]["search_depth"] == "basic"
        assert result["data"]["max_results"] == 2
        assert "response_time" not in result["data"]
        assert result["data"]["results"][0]["title"] == "Tavily search integration"
        assert result["data"]["results"][0]["published_date"] == "2026-07-29"

    @patch("agents.agents_scheduler.langgraph.tools.web_search.get_session_config")
    def test_absolute_dates_map_to_tavily_dates_and_override_time_range(
        self,
        mock_config,
        monkeypatch,
    ):
        mock_config.return_value = _config()
        fake_module = types.ModuleType("langchain_tavily")
        captured = {}

        class FakeTavilySearch:
            def __init__(self, **_kwargs):
                pass

            def invoke(self, args):
                captured.update(args)
                return {"results": [{"title": "result"}]}

        fake_module.TavilySearch = FakeTavilySearch
        monkeypatch.setitem(sys.modules, "langchain_tavily", fake_module)

        web_search.invoke({
            "query": "date range",
            "time_range": "month",
            "start_time": "2026-07-01",
            "end_time": "2026-07-29",
        })

        assert captured["start_date"] == "2026-07-01"
        assert captured["end_date"] == "2026-07-29"
        assert "time_range" not in captured

    def test_web_search_tool_name(self):
        assert web_search.name == "web_search"

    def test_web_search_exposes_unified_llm_parameters(self):
        properties = web_search.args_schema.model_json_schema()["properties"]
        assert set(properties) == {
            "query",
            "topic",
            "max_results",
            "search_depth",
            "time_range",
            "start_time",
            "end_time",
            "include_domains",
            "exclude_domains",
        }
        assert properties["max_results"]["default"] == 10
