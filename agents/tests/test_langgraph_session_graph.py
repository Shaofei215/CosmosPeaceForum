import pytest
from unittest.mock import patch, MagicMock

from agents.agents_scheduler.langgraph.session_graph import (
    build_session_graph,
    get_session_graph,
    get_graph_structure,
    print_graph_structure,
)
from agents.agents_scheduler.langgraph.config import SessionConfig


class TestBuildSessionGraph:
    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.mock_config = SessionConfig()
        self.mock_llm_invoker = MagicMock()
        self.mock_summarize_llm_invoker = MagicMock()

    def test_build_session_graph_with_default_params(self):
        """测试使用默认参数构建图"""
        with patch("agents.agents_scheduler.langgraph.session_graph.get_default_config") as mock_default_config:
            mock_default_config.return_value = self.mock_config
            graph = build_session_graph()

            # 验证图构建成功
            assert graph is not None

    def test_build_session_graph_with_custom_config(self):
        """测试使用自定义配置构建图"""
        graph = build_session_graph(config=self.mock_config)
        assert graph is not None

    def test_build_session_graph_with_both_invokers(self):
        """测试同时传入两个 LLM invoker"""
        with patch("agents.agents_scheduler.langgraph.session_graph.get_default_config") as mock_default_config:
            mock_default_config.return_value = self.mock_config
            graph = build_session_graph(
                config=self.mock_config,
                llm_invoker=self.mock_llm_invoker,
                summarize_llm_invoker=self.mock_summarize_llm_invoker
            )

            # 验证图构建成功
            assert graph is not None

    def test_build_session_graph_summarize_invoker_fallback(self):
        """测试 summarize_llm_invoker 为 None 时使用 llm_invoker"""
        with patch("agents.agents_scheduler.langgraph.session_graph.get_default_config") as mock_default_config:
            mock_default_config.return_value = self.mock_config
            graph = build_session_graph(
                config=self.mock_config,
                llm_invoker=self.mock_llm_invoker,
                summarize_llm_invoker=None
            )

            # 验证图构建成功
            assert graph is not None


class TestGetSessionGraph:
    def test_get_session_graph_singleton(self):
        """测试 get_session_graph 使用单例模式"""
        # 清除全局变量
        import agents.agents_scheduler.langgraph.session_graph as session_graph_module
        original_graph = session_graph_module._session_graph
        session_graph_module._session_graph = None

        try:
            with patch("agents.agents_scheduler.langgraph.session_graph.get_default_config") as mock_config:
                mock_config.return_value = SessionConfig()
                graph1 = get_session_graph()
                graph2 = get_session_graph()

                # 验证返回的是同一个实例
                assert graph1 is graph2
        finally:
            # 恢复原始值
            session_graph_module._session_graph = original_graph


class TestGetGraphStructure:
    def test_get_graph_structure_returns_dict(self):
        """测试 get_graph_structure 返回字典"""
        structure = get_graph_structure()

        assert isinstance(structure, dict)
        assert "nodes" in structure
        assert "edges" in structure
        assert "conditional_edges" in structure

    def test_graph_structure_nodes(self):
        """测试图结构中的节点定义"""
        structure = get_graph_structure()
        nodes = structure["nodes"]

        # 验证包含所有必要节点
        node_names = [n["name"] for n in nodes]
        assert "start" in node_names
        assert "recall_memory" in node_names
        assert "llm_decision" in node_names
        assert "tool_execution" in node_names
        assert "summarize" in node_names
        assert "end" in node_names

    def test_graph_structure_edges(self):
        """测试图结构中的边定义"""
        structure = get_graph_structure()
        edges = structure["edges"]

        # 验证基本边
        edge_pairs = [(e["from"], e["to"]) for e in edges]
        assert ("START", "start") in edge_pairs
        assert ("start", "recall_memory") in edge_pairs
        assert ("recall_memory", "llm_decision") in edge_pairs
        assert ("llm_decision", "tool_execution") in edge_pairs
        assert ("summarize", "end") in edge_pairs
        assert ("end", "END") in edge_pairs

    def test_graph_structure_conditional_edges(self):
        """测试图结构中的条件边定义"""
        structure = get_graph_structure()
        cond_edges = structure["conditional_edges"]

        # 验证条件边
        assert len(cond_edges) == 1
        assert cond_edges[0]["from"] == "tool_execution"
        assert cond_edges[0]["condition"] == "should_continue_edge"

        branches = cond_edges[0]["branches"]
        assert "tool_execution" in branches
        assert "recall_memory" in branches
        assert "summarize" in branches


class TestPrintGraphStructure:
    def test_print_graph_structure_no_error(self):
        """测试 print_graph_structure 不抛出异常"""
        with patch("agents.agents_scheduler.langgraph.session_graph.logger") as mock_logger:
            # 应该不抛出异常
            print_graph_structure()
            # 验证 logger 被调用
            assert mock_logger.info.called
