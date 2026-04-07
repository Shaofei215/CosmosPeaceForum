# 核心图结构模块
# 定义 LangGraph 的图结构，包括节点、边、路由逻辑等
from typing import Optional, Dict, Any
from langgraph.graph import StateGraph, END, START

from .state import SessionState
from .config import SessionConfig, get_default_config
from .nodes import (
    start_node,
    environment_awareness_node,
    llm_decision_node,
    tool_execution_node,
    summarize_node,
    end_node,
    should_continue_edge,
)


def _default_llm_invoker(system_prompt: str, user_prompt: str) -> str:
    """
    默认的 LLM 调用函数

    这是一个简单的同步占位实现。
    实际使用时需要接入真正的 LLM（如 OpenAI GPT、Claude 等）。
    推荐在 executor.py 中根据配置选择合适的 LLM 实现。

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词

    Returns:
        str: LLM 响应内容

    Raises:
        NotImplementedError: 此函数需要被真正的 LLM 实现替代
    """
    raise NotImplementedError(
        "请在 executor.py 中提供真正的 LLM 调用实现。"
        "推荐使用 langchain-openai 或 anthropic 等库的 ChatModel。"
    )


def build_session_graph(
    config: Optional[SessionConfig] = None,
    llm_invoker: Optional[callable] = None
) -> StateGraph:
    """
    构建完整的会话图

    图结构如下：
    ```
    START -> start -> environment_awareness -> llm_decision
                                                          |
                                                          v
                                                tool_execution
                                                          |
                                                          v
                                              should_continue (条件边)
                                               /           \
                                             /             \
                                            v               v
                                llm_decision (继续)      summarize (结束)
                                                              |
                                                              v
                                                             END
    ```

    流程说明：
    1. start: 初始化状态，重置工作记忆
    2. environment_awareness: 仅在开始时执行一次，获取"主页"信息（profile + 3条feed）
    3. llm_decision: LLM 根据工作记忆（action_history）做决策
    4. tool_execution: 执行 LLM 选择的工具，结果追加到工作记忆
    5. summarize: 会话结束时生成总结

    关键设计：
    - environment_awareness 只在开始时执行一次，之后不再重复获取"主页"
    - LLM 决策基于工作记忆（action_history），而非每次重新获取环境信息
    - 工具的返回值作为上下文，通过 result_summary 传递给 LLM

    Args:
        config: 会话配置，如果为 None 则使用默认配置
        llm_invoker: LLM 调用函数，签名为 (system_prompt: str, user_prompt: str) -> str
                     如果为 None，则使用默认的 _default_llm_invoker

    Returns:
        StateGraph: 编译后的图结构
    """
    if config is None:
        config = get_default_config()

    if llm_invoker is None:
        llm_invoker = _default_llm_invoker

    # 创建图
    graph = StateGraph(SessionState)

    # 添加节点
    graph.add_node("start", start_node)
    graph.add_node("environment_awareness", environment_awareness_node)
    graph.add_node("llm_decision", lambda state: llm_decision_node(state, llm_invoker))
    graph.add_node("tool_execution", tool_execution_node)
    graph.add_node("summarize", lambda state: summarize_node(state, llm_invoker))
    graph.add_node("end", end_node)

    # 设置入口点
    graph.set_entry_point("start")

    # 添加普通边
    # 1. start -> environment_awareness: 初始化后获取主页信息
    graph.add_edge("start", "environment_awareness")
    # 2. environment_awareness -> llm_decision: 获取环境后开始决策
    graph.add_edge("environment_awareness", "llm_decision")
    # 3. llm_decision -> tool_execution: 决策后执行工具
    graph.add_edge("llm_decision", "tool_execution")

    # 添加条件边
    # tool_execution 之后：
    # - 如果未达最大步数且未登出 -> 回到 llm_decision 继续决策
    # - 否则 -> summarize 结束会话
    graph.add_conditional_edges(
        "tool_execution",
        should_continue_edge,
        {
            "llm_decision": "llm_decision",  # 继续决策（基于工作记忆）
            "summarize": "summarize",          # 结束会话
        }
    )

    # 添加结束边
    graph.add_edge("summarize", "end")
    graph.add_edge("end", END)

    # 编译图
    compiled_graph = graph.compile()

    return compiled_graph


# ============================================================
# 预编译的图实例
# ============================================================

# 预编译的图实例，供直接使用
# 注意：由于没有指定 LLM，这个实例的 llm_decision 和 summarize 节点会抛出 NotImplementedError
# 建议在 executor.py 中根据实际使用的 LLM 重新构建
session_graph = build_session_graph()


# ============================================================
# 图信息查询
# ============================================================

def get_graph_structure() -> Dict[str, Any]:
    """
    获取图的结构信息

    用于调试和文档目的。

    Returns:
        Dict[str, Any]: 包含图结构信息的字典
    """
    return {
        "nodes": [
            {
                "name": "start",
                "description": "会话开始，初始化状态，重置工作记忆"
            },
            {
                "name": "environment_awareness",
                "description": "获取主页信息（仅执行一次）：profile + 3条feed"
            },
            {
                "name": "llm_decision",
                "description": "LLM 决策节点，根据工作记忆选择操作"
            },
            {
                "name": "tool_execution",
                "description": "执行 LLM 选择的工具，结果追加到工作记忆"
            },
            {
                "name": "summarize",
                "description": "生成会话总结"
            },
            {
                "name": "end",
                "description": "会话结束"
            }
        ],
        "edges": [
            {"from": "START", "to": "start"},
            {"from": "start", "to": "environment_awareness"},
            {"from": "environment_awareness", "to": "llm_decision"},
            {"from": "llm_decision", "to": "tool_execution"},
            {"from": "summarize", "to": "end"},
            {"from": "end", "to": "END"}
        ],
        "conditional_edges": [
            {
                "from": "tool_execution",
                "condition": "should_continue_edge",
                "branches": {
                    "llm_decision": "继续决策（基于工作记忆，不重新获取环境）",
                    "summarize": "结束会话"
                }
            }
        ]
    }


def print_graph_structure() -> None:
    """
    打印图的机构信息

    用于调试和理解图结构。
    """
    structure = get_graph_structure()

    print("=" * 60)
    print("LangGraph 会话图结构")
    print("=" * 60)

    print("\n【节点列表】")
    for node in structure["nodes"]:
        print(f"  - {node['name']}: {node['description']}")

    print("\n【边列表】")
    for edge in structure["edges"]:
        print(f"  {edge['from']} -> {edge['to']}")

    print("\n【条件边】")
    for cond_edge in structure["conditional_edges"]:
        print(f"  {cond_edge['from']} ({cond_edge['condition']}):")
        for target, desc in cond_edge["branches"].items():
            print(f"    - {target}: {desc}")

    print("\n" + "=" * 60)
