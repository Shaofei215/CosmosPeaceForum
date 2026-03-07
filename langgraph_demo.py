"""
LangGraph 最小实例 - 5 分钟理解核心概念

这个例子演示 LangGraph 的核心概念：
1. State（状态）- 数据如何在图中传递
2. Node（节点）- 处理函数
3. Edge（边）- 连接节点的箭头
4. Graph（图）- 由节点和边组成

运行方式：
    python langgraph_demo.py

依赖安装：
    pip install langgraph langchain-core
"""

from typing import TypedDict, List
from langgraph.graph import StateGraph, END


# ==================== 1. 定义状态 ====================
# State 就是一个 TypedDict（带类型注解的字典）
# 它定义了数据在图中如何流动

class AgentState(TypedDict):
    """
    定义我们的状态结构
    这就像是一个数据容器，在节点之间传递
    """
    input_text: str      # 输入文本
    processed_text: str  # 处理后的文本
    result: str         # 最终结果
    step_count: int     # 步骤计数


# ==================== 2. 定义节点函数 ====================
# Node 就是普通的 Python 函数
# 输入：当前状态
# 输出：要更新的状态（字典）

def process_node(state: AgentState):
    """
    节点 1：处理文本
    
    输入：state["input_text"] - 原始输入
    输出：state["processed_text"] - 处理后的文本
    """
    print(f"\n[节点 1] 处理文本...")
    print(f"  输入：{state['input_text']}")
    
    # 处理逻辑（简单示例：转大写）
    processed = state['input_text'].upper()
    
    # 返回更新的状态
    # 只返回变化的部分，其他字段保持不变
    return {
        "processed_text": processed,
        "step_count": state['step_count'] + 1
    }


def analyze_node(state: AgentState):
    """
    节点 2：分析文本
    
    输入：state["processed_text"] - 处理后的文本
    输出：state["result"] - 分析结果
    """
    print(f"\n[节点 2] 分析文本...")
    print(f"  输入：{state['processed_text']}")
    
    # 分析逻辑（示例：计算长度）
    length = len(state['processed_text'])
    result = f"文本长度：{length} 字符"
    
    return {
        "result": result,
        "step_count": state['step_count'] + 1
    }


def format_node(state: AgentState):
    """
    节点 3：格式化输出
    
    输入：state["result"] - 分析结果
    输出：最终格式化结果
    """
    print(f"\n[节点 3] 格式化输出...")
    print(f"  输入：{state['result']}")
    
    # 格式化逻辑
    final_output = f"=== 最终结果 ===\n{state['result']}\n================"
    
    return {
        "result": final_output,  # 覆盖 result 字段
        "step_count": state['step_count'] + 1
    }


# ==================== 3. 构建图 ====================

def build_simple_graph():
    """
    构建一个简单的线性流程图：
    
    process_node → analyze_node → format_node → END
    """
    
    # 创建图（指定状态类型）
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("process", process_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("format", format_node)
    
    # 设置入口点（从哪个节点开始）
    workflow.set_entry_point("process")
    
    # 添加边（连接节点）
    workflow.add_edge("process", "analyze")    # process → analyze
    workflow.add_edge("analyze", "format")     # analyze → format
    workflow.add_edge("format", END)           # format → 结束
    
    # 编译图（准备运行）
    app = workflow.compile()
    
    return app


# ==================== 4. 运行图 ====================

def run_simple_graph():
    """运行简单示例"""
    print("=" * 60)
    print("LangGraph 最小实例 - 线性流程")
    print("=" * 60)
    
    # 构建图
    app = build_simple_graph()
    
    # 准备输入数据
    input_data = {
        "input_text": "hello world",
        "processed_text": "",
        "result": "",
        "step_count": 0
    }
    
    print(f"\n【输入】{input_data['input_text']}")
    print("-" * 60)
    
    # 运行图
    result = app.invoke(input_data)
    
    print("-" * 60)
    print(f"\n【输出】{result['result']}")
    print(f"【执行步数】{result['step_count']} 步")
    print("=" * 60)
    
    return result


# ==================== 5. 条件分支示例 ====================

def should_continue(state: AgentState):
    """
    条件函数：决定是否继续
    
    根据文本长度决定走哪条路
    """
    text_length = len(state['processed_text'])
    
    if text_length > 10:
        return "long_text"
    else:
        return "short_text"


def handle_long_text(state: AgentState):
    """处理长文本"""
    print(f"\n[长文本处理] 输入长度：{len(state['processed_text'])}")
    return {
        "result": "这是一个长文本，需要特殊处理",
        "step_count": state['step_count'] + 1
    }


def handle_short_text(state: AgentState):
    """处理短文本"""
    print(f"\n[短文本处理] 输入长度：{len(state['processed_text'])}")
    return {
        "result": "这是一个短文本，简单处理即可",
        "step_count": state['step_count'] + 1
    }


def build_conditional_graph():
    """
    构建一个带条件分支的图：
    
                /→ handle_long_text → END
    process → check_length
                \→ handle_short_text → END
    """
    
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("process", process_node)
    workflow.add_node("check_length", analyze_node)
    workflow.add_node("handle_long", handle_long_text)
    workflow.add_node("handle_short", handle_short_text)
    
    # 设置入口
    workflow.set_entry_point("process")
    
    # 添加条件边（关键！）
    workflow.add_conditional_edges(
        "check_length",           # 从哪个节点出来
        should_continue,          # 条件函数
        {
            "long_text": "handle_long",    # 如果返回"long_text"，走这条路
            "short_text": "handle_short"   # 如果返回"short_text"，走这条路
        }
    )
    
    # 两条路最终都结束
    workflow.add_edge("handle_long", END)
    workflow.add_edge("handle_short", END)
    
    app = workflow.compile()
    return app


def run_conditional_graph():
    """运行条件分支示例"""
    print("\n" + "=" * 60)
    print("LangGraph 示例 - 条件分支")
    print("=" * 60)
    
    app = build_conditional_graph()
    
    # 测试 1：短文本
    print("\n【测试 1】短文本")
    result1 = app.invoke({
        "input_text": "hi",
        "processed_text": "",
        "result": "",
        "step_count": 0
    })
    print(f"结果：{result1['result']}")
    
    # 测试 2：长文本
    print("\n【测试 2】长文本")
    result2 = app.invoke({
        "input_text": "hello world this is a long text",
        "processed_text": "",
        "result": "",
        "step_count": 0
    })
    print(f"结果：{result2['result']}")
    
    print("=" * 60)


# ==================== 6. 类比项目实际场景 ====================

class AISessionState(TypedDict):
    """
    类比到我们的 AI 社交平台项目
    这是单次登录会话的状态
    """
    user_config: dict       # 用户配置
    notifications: list     # 通知消息
    posts: list            # 帖子列表
    thoughts: list         # 思考结果
    decisions: dict        # 决策结果
    actions: list          # 执行的行动


def browse_notifications_node(state: AISessionState):
    """节点 1：浏览通知（类比项目）"""
    print(f"\n[浏览通知] 用户 {state['user_config']['username']} 正在查看通知...")
    # 模拟获取通知
    notifications = ["通知 1", "通知 2"]
    return {"notifications": notifications}


def browse_timeline_node(state: AISessionState):
    """节点 2：浏览时间线（类比项目）"""
    print(f"\n[浏览时间线] 用户正在浏览帖子...")
    # 模拟获取帖子
    posts = [
        {"id": 1, "author": "三月七", "content": "今天天气真好！"},
        {"id": 2, "author": "姬子", "content": "来杯咖啡吗？"}
    ]
    return {"posts": posts}


def think_node(state: AISessionState):
    """节点 3：思考（类比项目）"""
    print(f"\n[思考] 用户正在分析帖子并测定兴趣系数...")
    thoughts = [
        {"post_id": 1, "thinking": "看起来很有趣", "interest_score": 0.8},
        {"post_id": 2, "thinking": "有点意思", "interest_score": 0.6}
    ]
    return {"thoughts": thoughts}


def decide_node(state: AISessionState):
    """节点 4：决策（类比项目）"""
    print(f"\n[决策] 用户决定执行行动...")
    decisions = {
        "actions": [
            {"type": "like_post", "post_id": 1},
            {"type": "comment", "post_id": 2, "content": "好呀！"}
        ]
    }
    return {"decisions": decisions}


def execute_actions_node(state: AISessionState):
    """节点 5：执行行动（类比项目）"""
    print(f"\n[执行行动] 用户执行了 {len(state['decisions']['actions'])} 个行动")
    for action in state['decisions']['actions']:
        print(f"  - 执行：{action['type']}")
    return {"actions": state['decisions']['actions']}


def build_ai_session_graph():
    """
    构建 AI 会话流程图（简化版项目）：
    
    browse_notifications → browse_timeline → think → decide → execute → END
    """
    
    workflow = StateGraph(AISessionState)
    
    # 添加节点
    workflow.add_node("browse_notifications", browse_notifications_node)
    workflow.add_node("browse_timeline", browse_timeline_node)
    workflow.add_node("think", think_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("execute", execute_actions_node)
    
    # 设置入口
    workflow.set_entry_point("browse_notifications")
    
    # 添加边
    workflow.add_edge("browse_notifications", "browse_timeline")
    workflow.add_edge("browse_timeline", "think")
    workflow.add_edge("think", "decide")
    workflow.add_edge("decide", "execute")
    workflow.add_edge("execute", END)
    
    app = workflow.compile()
    return app


def run_ai_session_demo():
    """运行 AI 会话演示（最接近实际项目）"""
    print("\n" + "=" * 60)
    print("LangGraph 示例 - AI 登录会话（项目简化版）")
    print("=" * 60)
    
    app = build_ai_session_graph()
    
    # 准备输入（模拟用户配置）
    input_data = {
        "user_config": {
            "username": "三月七",
            "personality": "活泼开朗"
        },
        "notifications": [],
        "posts": [],
        "thoughts": [],
        "decisions": {},
        "actions": []
    }
    
    print(f"\n【用户】{input_data['user_config']['username']} 开始登录会话")
    print("-" * 60)
    
    # 运行会话
    result = app.invoke(input_data)
    
    print("-" * 60)
    print(f"\n【会话完成】共执行 {len(result['actions'])} 个行动")
    print("=" * 60)
    
    return result


# ==================== 主函数 ====================

if __name__ == "__main__":
    print("\n" + "🌲" * 30)
    print("LangGraph 最小实例教程")
    print("🌲" * 30)
    
    # 示例 1：最简单的线性流程
    run_simple_graph()
    
    # 示例 2：条件分支
    run_conditional_graph()
    
    # 示例 3：AI 会话演示（最接近实际项目）
    run_ai_session_demo()
    
    print("\n" + "🌲" * 30)
    print("教程完成！")
    print("🌲" * 30)
    print("\n关键概念总结：")
    print("1. State = TypedDict（数据容器）")
    print("2. Node = 普通函数（处理逻辑）")
    print("3. Edge = 连接箭头（流程方向）")
    print("4. Graph = StateGraph（组合节点和边）")
    print("5. 编译 = graph.compile()")
    print("6. 运行 = app.invoke(input)")
    print("\n就这么简单！")
