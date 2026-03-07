"""
AI 行为引擎 - LangGraph 版本

使用 LangGraph 重构单次登录会话流程
对应原代码：ai_behavior.py 中的 AIBehaviorEngine.execute_login_session()

流程：
1. 浏览通知 → 2. 处理通知 → 3. 浏览时间线 → 4. 思考 → 5. 决策 → 6. 执行行动
"""

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
import random
import requests

# 导入项目现有模块
try:
    from .time_system import time_system
    from .llm import LLMClient
except ImportError:
    from time_system import time_system
    from llm import LLMClient


# ==================== 1. 定义状态池 ====================

class AISessionState(TypedDict):
    """
    AI 登录会话状态
    记录会话过程中所有数据
    """
    # 输入
    user_config: Dict[str, Any]           # 用户配置
    platform_user_id: int                 # 平台用户 ID
    
    # 中间数据
    notifications: List[Dict]             # 通知消息列表
    posts: List[Dict]                     # 帖子列表
    thoughts: List[Dict]                  # 思考结果
    post_reflection: Optional[Dict]       # 发帖思考
    decisions: Dict                       # 决策结果
    post_content: Optional[str]           # 生成的帖子内容
    
    # 输出
    actions: List[Dict]                   # 执行的行动列表
    
    # 元数据
    session_stats: Dict[str, int]         # 会话统计
    errors: List[str]                     # 错误信息


# ==================== 2. 定义节点函数 ====================

def check_notifications_node(state: AISessionState) -> Dict:
    """
    节点 1：浏览通知
    
    对应原代码：AIBehaviorEngine._browse_notifications()
    """
    user_config = state["user_config"]
    username = user_config.get("username", "Unknown")
    user_id = state["platform_user_id"]
    
    print(f"\n📬 [{username}] 正在查看互动消息...")
    
    try:
        # 随机决定浏览多少条消息（1-15）
        messages_to_read = random.randint(1, 15)
        print(f"[{username}] 计划查看 {messages_to_read} 条消息")
        
        # 调用 API
        url = f"http://127.0.0.1:8006/notifications"
        params = {
            "user_id": user_id,
            "limit": messages_to_read,
            "is_read": False
        }
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            notifications = response.json()
            print(f"[{username}] 获取到 {len(notifications)} 条未读消息")
            
            # 显示摘要
            for i, notif in enumerate(notifications[:5]):
                actor = notif.get("actor", {}).get("username", "未知")
                notif_type = notif.get("type", "")
                print(f"   [{i+1}] {actor} - {notif_type}")
            
            return {"notifications": notifications}
        else:
            print(f"[{username}] 获取通知失败：HTTP {response.status_code}")
            return {"notifications": []}
            
    except Exception as e:
        print(f"[{username}] 获取通知异常：{e}")
        return {"notifications": []}


def process_notifications_node(state: AISessionState) -> Dict:
    """
    节点 2：处理通知（LLM 决策如何回应）
    
    对应原代码：AIBehaviorEngine._process_notifications()
    """
    import json
    
    user_config = state["user_config"]
    notifications = state["notifications"]
    username = user_config.get("username", "Unknown")
    user_id = state["platform_user_id"]
    
    print(f"\n🤖 [{username}] 正在思考如何回应互动消息...")
    
    if not notifications:
        print(f"[{username}] 没有需要处理的通知")
        return {"actions": []}
    
    # 构建通知信息（完全按照原程序）
    notifications_info = []
    for notif in notifications:
        actor = notif.get("actor", {}).get("username", "未知用户")
        actor_id = notif.get("actor_id")
        notif_type = notif.get("type", "")
        created_at = notif.get("created_at", "")
        comment_id = notif.get("comment_id")
        reply_id = notif.get("reply_id")
        
        # 获取原内容
        original_content = ""
        if notif.get("post"):
            original_content = f"原帖：\"{notif['post'].get('content', '')[:50]}...\""
        elif notif.get("comment"):
            original_content = f"原评论：\"{notif['comment'].get('content', '')[:50]}...\""
        elif notif.get("reply"):
            original_content = f"原回复：\"{notif['reply'].get('content', '')[:50]}...\""
        
        # 构建消息数据
        notif_data = {
            "type": notif_type,
            "actor": actor,
            "actor_id": actor_id,
            "original": original_content,
            "time": created_at[:16] if created_at else ""
        }
        
        # 根据类型添加对应的 ID
        if comment_id:
            notif_data["comment_id"] = comment_id
        if reply_id:
            notif_data["reply_id"] = reply_id
        
        notifications_info.append(notif_data)
    
    # LLM 决策（原封不动使用原程序提示词）
    personality = user_config.get("personality_prompt", "")
    
    system_prompt = f"""你是{username}，{personality}

你在社交平台收到了 {len(notifications)} 条互动消息，请根据你的性格和兴趣决定如何回应。"""

    user_prompt = f"""请对以下互动消息决定如何回应：

【消息列表】
{json.dumps(notifications_info, ensure_ascii=False, indent=2)}

【可选行动类型】
1. "reply_to_comment" - 回复评论（需要提供 comment_id 和 content，50 字以内）
2. "reply_to_reply" - 回复回复（需要提供 reply_id 和 content，50 字以内）
3. "like_comment" - 点赞评论（需要提供 comment_id）
4. "like_reply" - 点赞回复（需要提供 reply_id）
5. "skip" - 不回应

【说明】
- 你不需要回应所有消息，根据你的兴趣和性格选择
- 回复内容要简洁（50 字以内），符合你的性格
- 对于点赞，通常不需要回应，除非你特别感兴趣
- 对于评论和回复，可以选择文字回应或点赞

【极其重要】你的响应必须是一个合法的 JSON 对象，不要包含任何 markdown 代码块标记。

输出格式：
{{"actions":[{{"type":"reply_to_comment","comment_id":1,"content":"谢谢！"}},{{"type":"like_comment","comment_id":3}}]}}

请输出 JSON 格式的决策结果。"""
    
    try:
        llm_client = LLMClient()
        result = llm_client.chat(user_prompt, system_prompt)
        
        if isinstance(result, dict):
            actions = result.get("actions", [])
            print(f"[{username}] LLM 决策完成，将执行 {len(actions)} 个行动")
            return {"actions": actions}
        
        print(f"[{username}] LLM 返回格式错误")
        return {"actions": []}
        
    except Exception as e:
        print(f"[{username}] LLM 处理失败：{e}")
        return {"actions": []}


def browse_timeline_node(state: AISessionState) -> Dict:
    """
    节点 3：浏览时间线
    
    对应原代码：AIBehaviorEngine._browse()
    """
    user_config = state["user_config"]
    username = user_config.get("username", "Unknown")
    user_id = state["platform_user_id"]
    
    posts_min = user_config.get("posts_per_login_min", 3)
    posts_max = user_config.get("posts_per_login_max", 10)
    n = random.randint(posts_min, posts_max)
    
    print(f"\n📖 [{username}] 正在浏览时间线...")
    print(f"[{username}] 计划浏览 {n} 条帖子 (范围：{posts_min}-{posts_max})")
    
    try:
        # 直接请求后端推荐 API
        # 后端已经实现了完整的推荐算法（热度排序 + 新鲜度加成 + 随机扰动 + 已读过滤）
        # AI 行为引擎不需要关心推荐算法细节，只需要获取排序好的帖子
        url = f"http://127.0.0.1:8006/posts/mixed"
        params = {
            "limit": n,        # 只需要指定数量
            "user_id": user_id # 只需要用户 ID（用于已读过滤）
            # hot_ratio, fresh_ratio, random_ratio 由后端内部管理，不需要传递
        }
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            posts = response.json()
            print(f"[{username}] 获取到 {len(posts)} 条帖子")
            
            # 显示摘要
            for i, post in enumerate(posts):
                author = post.get("author", {}).get("username", "未知")
                content = post.get("content", "")[:35]
                hot_score = post.get("hot_score", 0)
                print(f"   [{i+1}] [热度]{hot_score:3d} {author}: {content}")
            
            return {"posts": posts}
        else:
            print(f"[{username}] 获取帖子失败：HTTP {response.status_code}")
            return {"posts": []}
            
    except Exception as e:
        print(f"[{username}] 浏览时间线异常：{e}")
        return {"posts": []}


def think_node(state: AISessionState) -> Dict:
    """
    节点 4：思考（LLM 分析帖子并测定兴趣系数）
    
    对应原代码：AIBehaviorEngine._think_with_llm()
    """
    import json
    
    user_config = state["user_config"]
    posts = state["posts"]
    username = user_config.get("username", "Unknown")
    
    print(f"\n🤔 [{username}] 正在思考...")
    
    if not posts:
        print(f"[{username}] 没有帖子可以思考")
        return {"thoughts": [], "post_reflection": None}
    
    # LLM 思考（原封不动使用原程序提示词）
    personality = user_config.get("personality_prompt", "")
    
    system_prompt = f"""你是{username}，{personality}

你的任务是对看到的帖子进行思考和兴趣评估，并思考是否有发帖的冲动。

【任务 1：帖子思考】
对于每条帖子，你需要：
1. 简单思考这条帖子内容
2. 给出一个 0-1 之间的兴趣系数（0=完全不感兴趣，1=非常感兴趣）

【任务 2：发帖思考】
浏览这些内容后，你是否有想要表达的欲望？
- 有冲动不一定要发，只是内心的表达欲
- 想分享什么主题？（经历/观点/情感/日常生活）
- 注意：只需要确定主题方向，不需要生成具体内容

【极其重要】你的响应必须是一个合法的 JSON 对象，不要包含任何 markdown 代码块标记（如```json 或 ```），不要包含任何解释性文字。

输出格式必须严格如下：
{{"thoughts":[{{"post_id":1,"thinking":"这条帖子很有趣","interest_score":0.8}}],"post_reflection":{{"has_intention":true,"theme":"想分享今天遇到的有趣事情"}}}}

规则：
1. 只输出 JSON，不要换行、不要缩进、不要 markdown 标记
2. interest_score 必须是 0 到 1 之间的数字
3. thinking 字段使用纯文本，不要有特殊字符
4. post_reflection 是可选的，如果没有发帖冲动可以省略
5. 确保 JSON 格式完整，所有引号、括号必须匹配
6. 必须包含所有帖子的思考结果"""
    
    # 构建帖子信息
    posts_info = []
    for post in posts:
        posts_info.append({
            "id": post["id"],
            "author": post.get("author", {}).get("username", "Unknown"),
            "content": post["content"],
            "created_at": post.get("created_at", "")
        })
    
    user_prompt = f"""请对以下帖子进行思考和兴趣评估：

{json.dumps(posts_info, ensure_ascii=False, indent=2)}

请输出 JSON 格式的思考结果。"""
    
    try:
        llm_client = LLMClient()
        result = llm_client.chat(user_prompt, system_prompt)
        
        if isinstance(result, dict):
            thoughts = result.get("thoughts", [])
            post_reflection = result.get("post_reflection")
            
            print(f"[{username}] LLM 思考完成，分析了 {len(thoughts)} 条帖子")
            for t in thoughts[:3]:
                print(f"   - {t.get('thinking', '')[:30]}... (兴趣：{t.get('interest_score', 0):.2f})")
            
            return {"thoughts": thoughts, "post_reflection": post_reflection}
        
        print(f"[{username}] LLM 返回格式错误")
        return {"thoughts": [], "post_reflection": None}
        
    except Exception as e:
        print(f"[{username}] LLM 思考失败：{e}")
        return {"thoughts": [], "post_reflection": None}


def decide_node(state: AISessionState) -> Dict:
    """
    节点 5：决策（LLM 决定行动）
    
    对应原代码：AIBehaviorEngine._decide_with_llm()
    """
    import json
    
    user_config = state["user_config"]
    thoughts = state["thoughts"]
    post_reflection = state["post_reflection"]
    username = user_config.get("username", "Unknown")
    
    print(f"\n[决策] [{username}] 正在决策...")
    
    if not thoughts:
        print(f"[{username}] 没有思考结果，跳过决策")
        return {"decisions": {"actions": [], "decide_to_post": False}}
    
    # 获取关注列表（简化版本，实际应该调用 API）
    following_list = []  # TODO: 从后端获取关注列表
    
    # LLM 决策（原封不动使用原程序提示词）
    personality = user_config.get("personality_prompt", "")
    
    # 构建关注信息
    following_info = ""
    if following_list:
        following_info = f"\n你关注的用户：{', '.join(following_list)}\n你对关注用户的帖子/评论/回复会有更高的兴趣和互动意愿。"
    
    # 构建发帖思考信息
    post_reflection_info = ""
    if post_reflection and post_reflection.get("has_intention"):
        theme = post_reflection.get("theme", "")
        post_reflection_info = f"\n\n【发帖冲动】\n浏览内容后，你产生了发帖的冲动：\n- 主题：{theme}\n- 注意：有冲动不一定要发，可以选择发或不发"
    
    system_prompt = f"""你是{username}，{personality}{following_info}{post_reflection_info}

基于你对帖子的思考结果和阅读到的评论/回复，决定你的行动。

可选行动类型（不包含发帖，发帖决策单独处理）：
1. "comment" - 评论某条帖子（需要提供 post_id 和 content）
2. "reply_to_comment" - 回复某条评论（需要提供 comment_id 和 content）
3. "reply_to_reply" - 回复某条回复（需要提供 reply_id 和 content）
4. "like_post" - 点赞帖子（需要提供 post_id）
5. "like_comment" - 点赞评论（需要提供 comment_id）
6. "like_reply" - 点赞回复（需要提供 reply_id）
7. "skip" - 什么都不做

【发帖决策】
如果你有发帖冲动，现在需要决定是否真的发帖：
- 有冲动不一定要发，根据你的人设和当前情境决定
- 如果决定发帖，设置 "decide_to_post": true
- 如果不发帖，设置 "decide_to_post": false

【字数限制】
- 评论内容：50 字以内为宜
- 回复内容：50 字以内为宜
- 保持简洁，像真实社交媒体一样

【多行动说明】
你一次登录可以对多个或一个对象执行多个行动，actions 数组可以包含多个行动。例如：
- 可以既点赞又评论
- 可以点赞多条内容
- 可以评论后再回复
- ...
根据你的兴趣和意愿自由互动。

【极其重要】你的响应必须是一个合法的 JSON 对象，不要包含任何 markdown 代码块标记，不要包含任何解释性文字。

输出格式必须严格如下（单行 JSON）：
{{"actions":[{{"type":"comment","post_id":1,"content":"说得太对了！"}},{{"type":"like_post","post_id":2}}],"decide_to_post":false}}

规则：
1. 只输出单行 JSON，不要换行、不要缩进、不要 markdown 标记
2. 确保 JSON 格式完整，所有引号、括号必须匹配
3. actions 数组可以为空（表示 skip）
4. content 字段使用纯文本，不要有特殊字符
5. 根据兴趣系数和关注关系决定行动：
   - 对关注用户的帖子/评论/回复，更感兴趣
   - 高兴趣可以多互动，低兴趣可以少互动甚至跳过
6. decide_to_post 必须为 true 或 false，表示是否决定发帖
7. 点赞：最简单的互动，优先级较高，表示赞同该内容 评论/回复：优先级次之，仅想表达更多观点时使用"""
    
    # 构建思考信息，包含帖子和评论
    thoughts_info = []
    for t in thoughts:
        post_data = {
            "post_id": t["post"]["id"],
            "author": t["post"]["author"]["username"],
            "content": t["post"]["content"][:100],
            "thinking": t["thinking"],
            "interest_score": t["interest_score"]
        }
        
        # 添加评论信息
        if t.get("comments"):
            post_data["comments"] = []
            for comment in t["comments"]:
                comment_data = {
                    "comment_id": comment.get("id"),
                    "author": comment.get("author", {}).get("username", "Unknown"),
                    "content": comment.get("content", "")[:80]
                }
                
                # 添加回复信息
                if comment.get("replies"):
                    comment_data["replies"] = [
                        {
                            "reply_id": reply.get("id"),
                            "author": reply.get("author", {}).get("username", "Unknown"),
                            "content": reply.get("content", "")[:60]
                        }
                        for reply in comment["replies"]
                    ]
                
                post_data["comments"].append(comment_data)
        
        thoughts_info.append(post_data)
    
    user_prompt = f"""基于以下帖子和评论/回复的思考结果，决定你的行动：

{json.dumps(thoughts_info, ensure_ascii=False)}

请输出 JSON 格式的决策结果。可以针对帖子、评论或回复进行互动。"""
    
    try:
        llm_client = LLMClient()
        result = llm_client.chat(user_prompt, system_prompt)
        
        if isinstance(result, dict):
            actions = result.get("actions", [])
            decide_to_post = result.get("decide_to_post", False)
            
            print(f"[{username}] LLM 决策完成")
            print(f"[{username}] 决策：{len(actions)} 个行动，发帖：{decide_to_post}")
            
            return {"decisions": {"actions": actions, "decide_to_post": decide_to_post}}
        
        print(f"[{username}] LLM 返回格式错误")
        return {"decisions": {"actions": [], "decide_to_post": False}}
        
    except Exception as e:
        print(f"[{username}] LLM 决策失败：{e}")
        return {"decisions": {"actions": [], "decide_to_post": False}}


def generate_post_node(state: AISessionState) -> Dict:
    """
    节点 6：生成帖子内容（条件节点）
    
    对应原代码：AIBehaviorEngine._generate_post_content()
    """
    import json
    
    user_config = state["user_config"]
    post_reflection = state["post_reflection"]
    thoughts = state["thoughts"]
    username = user_config.get("username", "Unknown")
    
    if not post_reflection or not post_reflection.get("has_intention"):
        print(f"[{username}] 没有发帖冲动，跳过")
        return {"post_content": None}
    
    print(f"\n📝 [{username}] 正在生成帖子内容...")
    
    theme = post_reflection.get("theme", "")
    personality = user_config.get("personality_prompt", "")
    
    system_prompt = f"""你是{username}，{personality}

基于你浏览社交平台的发帖冲动，生成一条原创帖子。

【发帖主题】
{theme}

【要求】
- 符合你的性格和身份
- 可以是原创内容，也可以是对浏览内容的感悟
- 长度 100 字以内
- 像真实的社交媒体帖子

【极其重要】你的响应必须是一个合法的 JSON 对象，不要包含任何 markdown 代码块标记，不要包含任何解释性文字。

输出格式必须严格如下：
{{"content":"帖子内容"}}"""
    
    user_prompt = f"""请基于以下发帖冲动生成帖子：

发帖主题：{theme}

请生成你的帖子内容。"""
    
    try:
        llm_client = LLMClient()
        result = llm_client.chat(user_prompt, system_prompt)
        
        if isinstance(result, dict) and result.get("content"):
            content = result["content"]
            print(f"[{username}] 帖子内容生成成功：{content[:30]}...")
            return {"post_content": content}
        
        print(f"[{username}] LLM 返回格式错误")
        return {"post_content": None}
        
    except Exception as e:
        print(f"[{username}] 生成帖子失败：{e}")
        return {"post_content": None}


def execute_actions_node(state: AISessionState) -> Dict:
    """
    节点 7：执行行动
    
    对应原代码：AIBehaviorEngine._act()
    """
    user_config = state["user_config"]
    decisions = state["decisions"]
    post_content = state.get("post_content")
    username = user_config.get("username", "Unknown")
    user_id = state["platform_user_id"]
    
    print(f"\n[执行] [{username}] 开始执行行动...")
    
    actions = decisions.get("actions", [])
    results = []
    
    for i, action in enumerate(actions, 1):
        action_type = action.get("type")
        print(f"   [{i}] 执行：{action_type}")
        
        # 简化执行（实际项目中需要完整实现）
        result = {"type": action_type, "success": True}
        results.append(result)
    
    # 如果有帖子内容，执行发帖
    if post_content:
        print(f"   [发帖] 发布：{post_content[:30]}...")
        # 简化发帖（实际项目中需要调用 API）
        results.append({"type": "post", "content": post_content, "success": True})
    
    print(f"[{username}] 执行完成，共 {len(results)} 个行动")
    
    return {"actions": results}


# ==================== 3. 定义条件函数 ====================

def should_process_notifications(state: AISessionState) -> str:
    """条件：是否有通知需要处理"""
    if state["notifications"]:
        return "process"
    else:
        return "skip"


def has_posts(state: AISessionState) -> str:
    """条件：是否有帖子"""
    if state["posts"]:
        return "think"
    else:
        return "end"


def should_generate_post(state: AISessionState) -> str:
    """条件：是否要发帖"""
    decisions = state.get("decisions", {})
    if decisions.get("decide_to_post", False):
        return "generate"
    else:
        return "execute"


# ==================== 4. 构建图 ====================

def build_ai_session_graph() -> StateGraph:
    """
    构建 AI 登录会话流程图
    
    流程：
    check_notifications → process_notifications → browse_timeline → think → decide
                                                               ↓
    end ← execute_actions ← generate_post (条件)
    """
    
    workflow = StateGraph(AISessionState)
    
    # 添加节点
    workflow.add_node("check_notifications", check_notifications_node)
    workflow.add_node("process_notifications", process_notifications_node)
    workflow.add_node("browse_timeline", browse_timeline_node)
    workflow.add_node("think", think_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("generate_post", generate_post_node)
    workflow.add_node("execute_actions", execute_actions_node)
    
    # 设置入口
    workflow.set_entry_point("check_notifications")
    
    # 添加条件边
    workflow.add_conditional_edges(
        "check_notifications",
        should_process_notifications,
        {
            "process": "process_notifications",
            "skip": "browse_timeline"
        }
    )
    
    workflow.add_conditional_edges(
        "browse_timeline",
        has_posts,
        {
            "think": "think",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "decide",
        should_generate_post,
        {
            "generate": "generate_post",
            "execute": "execute_actions"
        }
    )
    
    # 添加普通边
    workflow.add_edge("process_notifications", "browse_timeline")
    workflow.add_edge("think", "decide")
    workflow.add_edge("generate_post", "execute_actions")
    workflow.add_edge("execute_actions", END)
    
    return workflow


# ==================== 5. LangGraph 行为引擎类 ====================

class LangGraphBehaviorEngine:
    """
    LangGraph 版本的 AI 行为引擎
    
    使用方式：
    engine = LangGraphBehaviorEngine()
    result = engine.execute_login_session(user_config, platform_user_id)
    """
    
    def __init__(self, use_llm: bool = True):
        """
        初始化 LangGraph 行为引擎
        
        Args:
            use_llm: 是否使用 LLM（默认 True）
        """
        self.use_llm = use_llm
        self.app = None
        self._initialize_graph()
        print(f"[LangGraph 引擎] 初始化完成，LLM: {'已启用' if use_llm else '已禁用'}")
    
    def _initialize_graph(self):
        """初始化并编译图"""
        workflow = build_ai_session_graph()
        self.app = workflow.compile()
        print("[LangGraph 引擎] 图已编译")
    
    def execute_login_session(
        self,
        user_config: Dict[str, Any],
        platform_user_id: int
    ) -> Dict[str, Any]:
        """
        执行一次完整的登录会话
        
        Args:
            user_config: 用户配置
            platform_user_id: 平台用户 ID
            
        Returns:
            Dict: 会话结果
        """
        username = user_config.get("username", "Unknown")
        
        print(f"\n{'='*60}")
        print(f"[{username}] 开始登录会话 - LangGraph 版本")
        print(f"{'='*60}")
        
        # 准备初始状态
        initial_state = {
            "user_config": user_config,
            "platform_user_id": platform_user_id,
            "notifications": [],
            "posts": [],
            "thoughts": [],
            "post_reflection": None,
            "decisions": {},
            "post_content": None,
            "actions": [],
            "session_stats": {
                "posts_created": 0,
                "comments_created": 0,
                "likes_given": 0,
                "follows_done": 0
            },
            "errors": []
        }
        
        try:
            # 运行图
            result = self.app.invoke(initial_state)
            
            print(f"\n{'='*60}")
            print(f"[{username}] 会话完成")
            print(f"{'='*60}")
            
            return result
            
        except Exception as e:
            print(f"\n[{username}] 会话执行出错：{e}")
            initial_state["errors"].append(str(e))
            return initial_state


# ==================== 6. 测试代码 ====================

def test_langgraph_engine():
    """测试 LangGraph 行为引擎"""
    print("="*60)
    print("LangGraph 行为引擎测试")
    print("="*60)
    
    # 模拟用户配置
    test_user = {
        "id": 1,
        "username": "三月七",
        "platform_user_id": 1,
        "personal_signature": "今天也是三月七！",
        "personality_prompt": "你是《崩坏：星穹铁道》中开朗活泼、充满好奇心的三月七。",
        "monthly_logins": 50,
        "posts_per_login_min": 4,
        "posts_per_login_max": 14
    }
    
    # 创建引擎
    engine = LangGraphBehaviorEngine(use_llm=False)  # 测试时禁用 LLM
    
    # 执行会话
    result = engine.execute_login_session(test_user, test_user["platform_user_id"])
    
    # 打印结果
    print("\n【会话结果】")
    print(f"执行行动数：{len(result.get('actions', []))}")
    print(f"错误数：{len(result.get('errors', []))}")
    
    if result.get("actions"):
        print("\n行动列表:")
        for i, action in enumerate(result["actions"], 1):
            print(f"  {i}. {action.get('type', 'unknown')}")


if __name__ == "__main__":
    test_langgraph_engine()
