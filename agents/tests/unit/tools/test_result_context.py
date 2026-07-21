from agents.agents_scheduler.langgraph.tools.support.result_context import (
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

    def test_merge_removes_stale_unread_count_from_previous_view(self):
        previous = {"post": {"id": 1}, "unread_count": 5}

        result = merge_recall_memory_result(previous, {"query": "hello", "memories": []})

        assert result["current_view"] == {"post": {"id": 1}}
