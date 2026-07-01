from agents.agents_scheduler.langgraph.tools.support.result_context import (
    format_merged_tool_context_result,
    is_merged_tool_context_result,
    merge_recall_memory_result,
    merge_web_search_result,
)


class TestToolResultContext:
    def test_merge_recall_memory_result_wraps_previous_result(self):
        previous = {"post": {"id": 1, "content": "hello"}}
        recall = {"query": "hello", "memories": [{"content": "old hello"}]}

        result = merge_recall_memory_result(previous, recall)

        assert is_merged_tool_context_result(result)
        assert result["current_view"] == previous
        assert result["explicit_recalls"] == [recall]
        assert result["web_searches"] == []

    def test_merge_recall_memory_result_keeps_existing_searches(self):
        previous = {
            "current_view": {"post": {"id": 1}},
            "explicit_recalls": [{"query": "first", "memories": []}],
            "web_searches": [{"query": "news", "results": []}],
        }
        recall = {"query": "second", "memories": []}

        result = merge_recall_memory_result(previous, recall)

        assert result["current_view"] == {"post": {"id": 1}}
        assert [item["query"] for item in result["explicit_recalls"]] == ["first", "second"]
        assert [item["query"] for item in result["web_searches"]] == ["news"]

    def test_merge_recall_memory_result_accepts_legacy_context_shape(self):
        previous = {
            "current_view": {"post": {"id": 1}},
            "explicit_recalls": [{"query": "first", "memories": []}],
        }
        recall = {"query": "second", "memories": []}

        result = merge_recall_memory_result(previous, recall)

        assert result["current_view"] == {"post": {"id": 1}}
        assert [item["query"] for item in result["explicit_recalls"]] == ["first", "second"]
        assert result["web_searches"] == []

    def test_merge_web_search_result_wraps_previous_result(self):
        previous = {"post": {"id": 1, "content": "hello"}}
        search = {"query": "hello", "results": [{"title": "Hello"}]}

        result = merge_web_search_result(previous, search)

        assert is_merged_tool_context_result(result)
        assert result["current_view"] == previous
        assert result["explicit_recalls"] == []
        assert result["web_searches"] == [search]

    def test_merge_web_search_result_keeps_existing_recalls(self):
        previous = {
            "current_view": {"post": {"id": 1}},
            "explicit_recalls": [{"query": "first", "memories": []}],
            "web_searches": [],
        }
        search = {"query": "second", "results": []}

        result = merge_web_search_result(previous, search)

        assert result["current_view"] == {"post": {"id": 1}}
        assert [item["query"] for item in result["explicit_recalls"]] == ["first"]
        assert result["web_searches"] == [search]

    def test_format_merged_tool_context_result(self):
        result = {
            "current_view": {"post": {"id": 1}},
            "explicit_recalls": [
                {
                    "query": "hello",
                    "memories": [{"content": "old hello", "time_description": "刚刚"}],
                }
            ],
            "web_searches": [
                {
                    "query": "LangChain Tavily",
                    "search_depth": "advanced",
                    "results": [{"title": "Tavily", "url": "https://example.com", "content": "Search docs"}],
                }
            ],
        }

        formatted = format_merged_tool_context_result(
            result,
            lambda current_view: f"view={current_view['post']['id']}",
        )

        assert "view=1" in formatted
        assert "主动回想" in formatted
        assert "old hello" in formatted
        assert "联网搜索" in formatted
        assert "https://example.com" in formatted

    def test_merge_removes_stale_unread_count_from_previous_view(self):
        previous = {"post": {"id": 1}, "unread_count": 5}

        result = merge_recall_memory_result(previous, {"query": "hello", "memories": []})

        assert result["current_view"] == {"post": {"id": 1}}
