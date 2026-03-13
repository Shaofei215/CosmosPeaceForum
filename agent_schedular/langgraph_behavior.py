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
import json

# 导入项目现有模块
try:
    from .time_system import time_system
    from .llm import LLMClient
except ImportError:
    from time_system import time_system
    from llm import LLMClient


# ==================== API 客户端 ====================

class SocialPlatformAPI:
    """社交平台 API 客户端"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8006"):
        self.base_url = base_url
    
    def get_comments_by_interest(self, post_id: int, interest_score: float) -> List[Dict]:
        """
        根据兴趣系数获取评论和回复
        
        阅读评论数 = floor(兴趣系数 × 5)
        每条评论的回复数 = floor(兴趣系数 × 5)
        例如：兴趣系数 0.6 → 阅读 3 条评论，每条评论阅读 3 条回复，总共 12 条（3 条评论 + 9 条回复）
        
        评论排序：70% 最热 + 30% 最新
        回复排序：70% 最热 + 30% 最新
        
        Args:
            post_id: 帖子 ID
            interest_score: 兴趣系数（0-1）
            
        Returns:
            List[Dict]: 评论列表（包含回复）
        """
        # 计算需要阅读多少条评论和每条评论的回复数
        max_items = 5
        comments_to_read = int(interest_score * max_items)
        replies_per_comment = int(interest_score * max_items)
        
        if comments_to_read <= 0:
            return []
        
        try:
            # 1. 获取评论（使用混合排序：70% 最热 + 30% 最新）
            url = f"{self.base_url}/posts/{post_id}/comments"
            params = {
                "mixed": "true",
                "limit": comments_to_read * 2  # 获取更多以确保去重后足够
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                all_comments = response.json()
                # 只取前 N 条评论
                selected_comments = all_comments[:comments_to_read]
                
                # 2. 为每条评论获取回复（也使用兴趣系数控制数量）
                if replies_per_comment > 0:
                    for comment in selected_comments:
                        comment_id = comment.get("id")
                        # 获取该评论的所有回复（使用混合排序）
                        reply_url = f"{self.base_url}/comments/{comment_id}/replies"
                        reply_params = {
                            "mixed": "true",
                            "limit": replies_per_comment * 2
                        }
                        reply_response = requests.get(reply_url, params=reply_params, timeout=10)
                        
                        if reply_response.status_code == 200:
                            all_replies = reply_response.json()
                            # 只取前 N 条回复
                            comment["replies"] = all_replies[:replies_per_comment]
                        else:
                            comment["replies"] = []
                
                return selected_comments
            else:
                return []
                
        except Exception as e:
            print(f"[API] 获取评论失败：{e}")
            return []
    
    def create_comment(self, post_id: int, user_id: int, content: str) -> Dict:
        """创建评论"""
        url = f"{self.base_url}/posts/{post_id}/comments"
        params = {"author_id": user_id}
        data = {"content": content}
        try:
            response = requests.post(url, params=params, json=data, timeout=10)
            if response.status_code == 201:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_reply(self, comment_id: int, user_id: int, content: str) -> Dict:
        """创建回复"""
        url = f"{self.base_url}/comments/{comment_id}/replies"
        params = {"author_id": user_id}
        data = {"content": content}
        try:
            response = requests.post(url, params=params, json=data, timeout=10)
            if response.status_code == 201:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def like_post(self, post_id: int, user_id: int) -> Dict:
        """点赞帖子"""
        url = f"{self.base_url}/posts/{post_id}/like"
        params = {"user_id": user_id}
        try:
            response = requests.post(url, params=params, timeout=10)
            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def like_comment(self, comment_id: int, user_id: int) -> Dict:
        """点赞评论"""
        url = f"{self.base_url}/comments/{comment_id}/like"
        params = {"user_id": user_id}
        try:
            response = requests.post(url, params=params, timeout=10)
            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def like_reply(self, reply_id: int, user_id: int) -> Dict:
        """点赞回复"""
        url = f"{self.base_url}/replies/{reply_id}/like"
        params = {"user_id": user_id}
        try:
            response = requests.post(url, params=params, timeout=10)
            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def follow_user(self, user_id: int, follower_id: int) -> Dict:
        """关注用户"""
        url = f"{self.base_url}/users/{user_id}/follow"
        params = {"follower_id": follower_id}
        try:
            response = requests.post(url, params=params, timeout=10)
            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_post(self, user_id: int, content: str) -> Dict:
        """创建帖子"""
        url = f"{self.base_url}/posts"
        params = {"author_id": user_id}
        data = {"content": content}
        try:
            response = requests.post(url, params=params, json=data, timeout=10)
            if response.status_code == 201:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_quote_post(self, quote_from_id: int, user_id: int, content: str) -> Dict:
        """创建直接转发帖子"""
        url = f"{self.base_url}/posts/quote"
        params = {
            "quote_from_id": quote_from_id,
            "author_id": user_id,
            "content": content
        }
        try:
            response = requests.post(url, params=params, timeout=10)
            if response.status_code == 201:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_comment_with_repost(self, post_id: int, user_id: int, content: str) -> Dict:
        """创建评论并转发"""
        url = f"{self.base_url}/posts/comment-with-repost"
        params = {
            "post_id": post_id,
            "author_id": user_id,
            "content": content,
            "quote_from_id": post_id  # 通常与被评论的帖子相同
        }
        try:
            response = requests.post(url, params=params, timeout=10)
            if response.status_code == 201:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_reply_with_repost(self, comment_id: int, user_id: int, content: str, quote_from_id: int = None) -> Dict:
        """创建回复并转发"""
        url = f"{self.base_url}/posts/reply-with-repost"
        params = {
            "comment_id": comment_id,
            "author_id": user_id,
            "content": content
        }
        # 如果提供了 quote_from_id，使用它；否则后端会根据 comment_id 推断
        if quote_from_id:
            params["quote_from_id"] = quote_from_id
        
        try:
            response = requests.post(url, params=params, timeout=10)
            if response.status_code == 201:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


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
            
            # 显示所有消息
            for i, notif in enumerate(notifications, 1):
                actor = notif.get("actor", {}).get("username", "未知")
                notif_type = notif.get("type", "")
                
                # 特殊处理转发通知：只展示直接转发
                if notif_type == "quote":
                    post = notif.get("post", {})
                    quote_from_id = post.get("quote_from_id")
                    original_post_id = post.get("original_post_id")
                    
                    # 只展示直接转发（quote_from_id == original_post_id）
                    if quote_from_id != original_post_id:
                        print(f"   [{i}] {actor} - 间接转发（已过滤）")
                        continue
                    
                    # 展示直接转发的详细信息
                    original_post = post.get("original_post", {})
                    original_content = original_post.get("content", "")[:30] if original_post else ""
                    quote_comment = post.get("quote_comment", "")[:30] if post else ""
                    print(f"   [{i}] 🔄 {actor} 转发了你的帖子")
                    print(f"       原帖：\"{original_content}...\"")
                    print(f"       转发评论：\"{quote_comment}...\"")
                else:
                    # 其他类型通知
                    content_preview = notif.get("content", "")[:30] if notif.get("content") else ""
                    if content_preview:
                        print(f"   [{i}] {actor} - {notif_type}: {content_preview}...")
                    else:
                        print(f"   [{i}] {actor} - {notif_type}")
            
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
        
        # 检查 LLM 自我修复是否失败
        if isinstance(result, dict) and result.get("success") == False:
            print(f"[{username}] ⚠️ LLM JSON 解析失败：{result.get('parse_error', '未知错误')}")
            return {"actions": []}
        
        if isinstance(result, dict):
            actions = result.get("actions", [])
            # 确保 actions 是列表
            if not isinstance(actions, list):
                print(f"[{username}] ⚠️ actions 不是列表类型，设为空列表")
                actions = []
            
            print(f"\n🤖 [{username}] LLM 决策完成，将执行 {len(actions)} 个行动")
            
            # 详细打印每个行动
            if actions:
                print(f"\n📋 [{username}] 决策详情:")
                for i, action in enumerate(actions, 1):
                    # 确保每个 action 都是字典
                    if not isinstance(action, dict):
                        print(f"   [{i}] ⚠️ 行动格式错误，跳过")
                        continue
                    
                    action_type = action.get("type", "unknown")
                    
                    # 根据行动类型显示详细信息
                    if action_type == "reply_to_comment":
                        comment_id = action.get("comment_id", "?")
                        content = action.get("content", "")[:30] + ("..." if len(action.get("content", "")) > 30 else "")
                        print(f"   [{i}] 💬 回复评论 ID={comment_id}：\"{content}\"")
                    
                    elif action_type == "reply_to_reply":
                        reply_id = action.get("reply_id", "?")
                        content = action.get("content", "")[:30] + ("..." if len(action.get("content", "")) > 30 else "")
                        print(f"   [{i}] 💬 回复回复 ID={reply_id}：\"{content}\"")
                    
                    elif action_type == "like_comment":
                        comment_id = action.get("comment_id", "?")
                        print(f"   [{i}] 👍 点赞评论 ID={comment_id}")
                    
                    elif action_type == "like_reply":
                        reply_id = action.get("reply_id", "?")
                        print(f"   [{i}] 👍 点赞回复 ID={reply_id}")
                    
                    elif action_type == "skip":
                        print(f"   [{i}] ⏭️ 跳过（不回应）")
                    
                    else:
                        print(f"   [{i}] ❓ 未知行动：{action_type}")
            
            print()
            return {"actions": actions}
        
        print(f"[{username}] LLM 返回格式错误：{type(result)}")
        return {"actions": []}
        
    except Exception as e:
        print(f"[{username}] LLM 处理失败：{e}")
        import traceback
        traceback.print_exc()
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
        
        # 检查 LLM 自我修复是否失败
        if isinstance(result, dict) and result.get("success") == False:
            print(f"[{username}] ⚠️ LLM JSON 解析失败：{result.get('parse_error', '未知错误')}")
            return {"thoughts": [], "post_reflection": None}
        
        if isinstance(result, dict):
            thoughts = result.get("thoughts", [])
            post_reflection = result.get("post_reflection")
            
            # 确保 thoughts 是列表
            if not isinstance(thoughts, list):
                print(f"[{username}] ⚠️ thoughts 不是列表类型，设为空列表")
                thoughts = []
            
            # 创建 API 客户端
            api = SocialPlatformAPI()
            
            # 根据兴趣系数获取评论和回复
            print(f"[{username}] 正在根据兴趣系数获取评论和回复...")
            for t in thoughts:
                # 确保 t 是字典
                if not isinstance(t, dict):
                    continue
                    
                post_id = t.get("post_id")
                interest_score = t.get("interest_score", 0.5)
                
                # 根据兴趣系数获取评论
                comments = api.get_comments_by_interest(post_id, interest_score)
                
                # 找到对应的帖子
                post = None
                for p in posts:
                    if p["id"] == post_id:
                        post = p
                        break
                
                if post:
                    # 将完整的帖子信息和评论添加到思考结果中
                    t["post"] = post
                    t["comments"] = comments
                    t["comments_read"] = len(comments)
                    
                    # 计算总阅读回复数
                    total_replies = sum(len(c.get("replies", [])) for c in comments)
                    t["replies_read"] = total_replies
            
            print(f"[{username}] LLM 思考完成，分析了 {len(thoughts)} 条帖子")
            for i, t in enumerate(thoughts, 1):
                comments_info = f"[阅读了 {t.get('comments_read', 0)} 条评论"
                if t.get('replies_read', 0) > 0:
                    comments_info += f" + {t.get('replies_read', 0)} 条回复"
                comments_info += "]"
                print(f"   [{i}] {t.get('thinking', '')[:50]}... (兴趣：{t.get('interest_score', 0):.2f}) {comments_info}")
            
            return {"thoughts": thoughts, "post_reflection": post_reflection}
        
        print(f"[{username}] LLM 返回格式错误：{type(result)}")
        return {"thoughts": [], "post_reflection": None}
        
    except Exception as e:
        print(f"[{username}] LLM 思考失败：{e}")
        import traceback
        traceback.print_exc()
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
    posts = state.get("posts", [])
    # ✅ 获取之前阶段产生的 actions（如通知处理）
    previous_actions = state.get("actions", [])
    username = user_config.get("username", "Unknown")
    
    print(f"\n[决策] [{username}] 正在决策...")
    
    if not thoughts:
        print(f"[{username}] 没有思考结果，跳过决策")
        # ✅ 保留之前的 actions（如通知处理）
        return {"decisions": {"actions": previous_actions, "decide_to_post": False}}
    
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
7. "quote_post" - 直接转发某条帖子（需要提供 post_id 和 reason，reason 是转发原因/想法，会进入生成阶段基于此生成转发评论）
8. "comment_with_repost" - 评论并转发（需要提供 post_id 和 content）
9. "reply_with_repost" - 回复并转发（需要提供 comment_id 和 content）
10. "skip" - 什么都不做

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
你可以对多个或一个对象执行多个行动，actions 数组可以包含多个行动。例如：
- 可以既点赞又评论
- 可以点赞多条内容
- 可以评论后再回复
- ...你的行动没有限制
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
7. 点赞：最简单的互动，优先级较高，表示赞同该内容 评论/回复：优先级次之，仅想表达更多观点时使用 转发：在想要将内容分享给他人时使用"""
    
    # 构建思考信息，包含帖子和评论
    # thoughts 已经包含 post 和 comments 信息
    thoughts_info = []
    for t in thoughts:
        post = t.get("post", {})
        
        post_data = {
            "post_id": post.get("id", t.get("post_id")),
            "author": post.get("author", {}).get("username", "Unknown"),
            "content": post.get("content", "")[:100],
            "likes_count": post.get("likes_count", 0),
            "comments_count": post.get("comments_count", 0),
            "thinking": t["thinking"],
            "interest_score": t["interest_score"]
        }
        
        # 添加评论信息（已经在 think_node 中获取）
        if t.get("comments"):
            post_data["comments"] = []
            for comment in t["comments"]:
                comment_data = {
                    "comment_id": comment.get("id"),
                    "author": comment.get("author", {}).get("username", "Unknown"),
                    "content": comment.get("content", "")[:80],
                    "likes_count": comment.get("likes_count", 0),
                    "replies_count": len(comment.get("replies", []))
                }
                
                # 添加回复信息
                if comment.get("replies"):
                    comment_data["replies"] = []
                    for reply in comment["replies"]:
                        reply_data = {
                            "reply_id": reply.get("id"),
                            "author": reply.get("author", {}).get("username", "Unknown"),
                            "content": reply.get("content", "")[:60],
                            "likes_count": reply.get("likes_count", 0)
                        }
                        comment_data["replies"].append(reply_data)
                
                post_data["comments"].append(comment_data)
        
        thoughts_info.append(post_data)
    
    user_prompt = f"""基于以下帖子和评论/回复的思考结果，决定你的行动：

{json.dumps(thoughts_info, ensure_ascii=False)}

请输出 JSON 格式的决策结果。可以针对帖子、评论或回复进行互动。"""
    
    try:
        llm_client = LLMClient()
        result = llm_client.chat(user_prompt, system_prompt)
        
        # 检查 LLM 自我修复是否失败
        if isinstance(result, dict) and result.get("success") == False:
            print(f"[{username}] ⚠️ LLM JSON 解析失败：{result.get('parse_error', '未知错误')}")
            print(f"[{username}] 原始内容：{result.get('raw_content', '')[:200]}...")
            return {"decisions": {"actions": [], "decide_to_post": False}}
        
        if isinstance(result, dict):
            actions = result.get("actions", [])
            decide_to_post = result.get("decide_to_post", False)
            
            # 确保 actions 是列表
            if not isinstance(actions, list):
                print(f"[{username}] ⚠️ actions 不是列表类型，设为空列表")
                actions = []
            
            print(f"\n[决策] [{username}] LLM 决策完成")
            print(f"[决策] [{username}] 计划执行 {len(actions)} 个行动，发帖：{decide_to_post}")
            
            # 详细打印每个行动
            if actions:
                print(f"\n[决策] [{username}] 行动列表:")
                for i, action in enumerate(actions, 1):
                    # 确保每个 action 都是字典
                    if not isinstance(action, dict):
                        print(f"   [{i}] ⚠️ 行动格式错误，跳过")
                        continue
                    
                    action_type = action.get("type", "unknown")
                    if action_type == "comment":
                        print(f"   [{i}] 📝 评论帖子 ID={action.get('post_id')}：\"{action.get('content', '')[:30]}...\"")
                    elif action_type == "reply_to_comment":
                        print(f"   [{i}] 💬 回复评论 ID={action.get('comment_id')}：\"{action.get('content', '')[:30]}...\"")
                    elif action_type == "reply_to_reply":
                        print(f"   [{i}] 💬 回复回复 ID={action.get('reply_id')}：\"{action.get('content', '')[:30]}...\"")
                    elif action_type == "like_post":
                        print(f"   [{i}] 👍 点赞帖子 ID={action.get('post_id')}")
                    elif action_type == "like_comment":
                        print(f"   [{i}] 👍 点赞评论 ID={action.get('comment_id')}")
                    elif action_type == "like_reply":
                        print(f"   [{i}] 👍 点赞回复 ID={action.get('reply_id')}")
                    elif action_type == "quote_post":
                        post_id = action.get('post_id')
                        reason = action.get('reason', '')
                        reason_preview = f"（原因：{reason[:30]}...）" if reason else ""
                        print(f"   [{i}] 🔄 直接转发帖子 ID={post_id}{reason_preview}")
                        print(f"       将基于此原因生成转发评论")
                    elif action_type == "comment_with_repost":
                        print(f"   [{i}] 🔄 评论并转发帖子 ID={action.get('post_id')}：\"{action.get('content', '')[:30]}...\"")
                    elif action_type == "reply_with_repost":
                        print(f"   [{i}] 🔄 回复并转发评论 ID={action.get('comment_id')}：\"{action.get('content', '')[:30]}...\"")
                    elif action_type == "follow":
                        print(f"   [{i}] ➕ 关注用户 ID={action.get('user_id')}")
                    else:
                        print(f"   [{i}] ❓ 未知行动：{action_type}")
            
            if decide_to_post:
                print(f"\n[决策] [{username}] ✅ 决定发帖")
            else:
                print(f"\n[决策] [{username}] ❌ 不发帖")
            
            # ✅ 合并之前的 actions（如通知处理）和当前的 actions
            all_actions = previous_actions + actions
            print(f"\n[决策] [{username}] 合并后总行动数：{len(all_actions)} (通知处理：{len(previous_actions)}, 浏览决策：{len(actions)})")
            
            return {"decisions": {"actions": all_actions, "decide_to_post": decide_to_post}}
        
        print(f"[{username}] LLM 返回格式错误：{type(result)}")
        # ✅ 错误情况下也保留之前的 actions
        return {"decisions": {"actions": previous_actions, "decide_to_post": False}}
        
    except Exception as e:
        print(f"[{username}] LLM 决策失败：{e}")
        import traceback
        traceback.print_exc()
        # ✅ 异常情况下也保留之前的 actions
        return {"decisions": {"actions": previous_actions, "decide_to_post": False}}


def generate_post_node(state: AISessionState) -> Dict:
    """
    节点 6：生成内容（条件节点）
    
    两种情况：
    1. 决定发帖 → 生成原创帖子
    2. 决定直接转发 → 生成转发评论
    """
    import json
    
    user_config = state["user_config"]
    post_reflection = state["post_reflection"]
    decisions = state.get("decisions", {})
    thoughts = state["thoughts"]
    username = user_config.get("username", "Unknown")
    
    # 检查是否有直接转发的决策
    quote_decision = None
    actions = decisions.get("actions", [])
    for action in actions:
        if action.get("type") == "quote_post":
            quote_decision = action
            break
    
    # 如果有直接转发决策，生成转发评论
    if quote_decision:
        post_id = quote_decision.get("post_id")
        reason = quote_decision.get("reason", "")  # 获取转发原因
        
        # 找到对应的帖子信息
        target_post = None
        for t in thoughts:
            if t.get("post", {}).get("id") == post_id:
                target_post = t["post"]
                break
        
        if not target_post:
            print(f"[{username}] ⚠️ 找不到要转发的帖子 ID={post_id}，跳过生成")
            return {"post_content": None}
        
        print(f"\n🔄 [{username}] 正在生成转发评论...")
        print(f"   转发原因：{reason[:50] if reason else '无'}...")
        
        personality = user_config.get("personality_prompt", "")
        post_content = target_post.get("content", "")[:200]
        post_author = target_post.get("author", {}).get("username", "未知")
        
        system_prompt = f"""你是{username}，{personality}

你要转发一条帖子，请根据你的转发原因生成具体的转发评论。

【被转发的帖子】
作者：{post_author}
内容：{post_content}

【你的转发原因】
{reason if reason else '想分享这个内容'}

【要求】
- 基于你的转发原因生成具体的转发评论
- 符合你的性格和身份
- 可以是赞同、补充、吐槽、感慨等
- 长度 50 字以内
- 像真实的社交媒体转发评论

【极其重要】你的响应必须是一个合法的 JSON 对象，不要包含任何 markdown 代码块标记，不要包含任何解释性文字。

输出格式必须严格如下：
{{"content":"转发评论内容"}}"""
        
        user_prompt = f"""请基于以下信息生成转发评论：

【帖子信息】
作者：{post_author}
内容：{post_content}

【你的转发原因】
{reason if reason else '想分享这个内容'}

请生成你的转发评论，要体现你的转发原因。"""
        
        try:
            llm_client = LLMClient()
            result = llm_client.chat(user_prompt, system_prompt)
            
            # 检查 LLM 自我修复是否失败
            if isinstance(result, dict) and result.get("success") == False:
                print(f"[{username}] ⚠️ LLM JSON 解析失败：{result.get('parse_error', '未知错误')}")
                return {"post_content": None}
            
            if isinstance(result, dict) and result.get("content"):
                content = result["content"]
                # 确保 content 是字符串
                if not isinstance(content, str):
                    print(f"[{username}] ⚠️ content 不是字符串类型")
                    return {"post_content": None}
                print(f"[{username}] 转发评论生成成功：{content[:30]}...")
                
                # 将生成的内容添加到决策中
                quote_decision["generated_content"] = content
                
                return {"post_content": content}
            
            print(f"[{username}] LLM 返回格式错误或无内容：{type(result)}")
            return {"post_content": None}
            
        except Exception as e:
            print(f"[{username}] 生成转发评论失败：{e}")
            import traceback
            traceback.print_exc()
            return {"post_content": None}
    
    # 如果没有转发决策，检查是否有发帖冲动
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
        
        # 检查 LLM 自我修复是否失败
        if isinstance(result, dict) and result.get("success") == False:
            print(f"[{username}] ⚠️ LLM JSON 解析失败：{result.get('parse_error', '未知错误')}")
            return {"post_content": None}
        
        if isinstance(result, dict) and result.get("content"):
            content = result["content"]
            # 确保 content 是字符串
            if not isinstance(content, str):
                print(f"[{username}] ⚠️ content 不是字符串类型")
                return {"post_content": None}
            print(f"[{username}] 帖子内容生成成功：{content[:30]}...")
            return {"post_content": content}
        
        print(f"[{username}] LLM 返回格式错误或无内容：{type(result)}")
        return {"post_content": None}
        
    except Exception as e:
        print(f"[{username}] 生成帖子失败：{e}")
        import traceback
        traceback.print_exc()
        return {"post_content": None}


def execute_actions_node(state: AISessionState) -> Dict:
    """
    节点 7：执行行动
    
    对应原代码：AIBehaviorEngine._act()
    """
    import time
    
    user_config = state["user_config"]
    decisions = state["decisions"]
    post_content = state.get("post_content")
    username = user_config.get("username", "Unknown")
    user_id = state["platform_user_id"]
    
    # 创建 API 客户端
    api = SocialPlatformAPI()
    
    print(f"\n{'='*60}")
    print(f"[执行] [{username}] 开始执行行动...")
    print(f"{'='*60}")
    
    actions = decisions.get("actions", [])
    results = []
    success_count = 0
    
    for i, action in enumerate(actions, 1):
        action_type = action.get("type")
        result = {"type": action_type, "success": False}
        
        # 详细打印行动信息
        if action_type == "comment":
            post_id = action.get('post_id')
            content = action.get('content', '')
            print(f"\n   [{i}/{len(actions)}] 📝 评论帖子")
            print(f"       目标：帖子 ID={post_id}")
            print(f"       内容：\"{content}\"")
            
            # 调用 API
            api_result = api.create_comment(post_id, user_id, content)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
                
        elif action_type == "reply_to_comment":
            comment_id = action.get('comment_id')
            content = action.get('content', '')
            print(f"\n   [{i}/{len(actions)}] 💬 回复评论")
            print(f"       目标：评论 ID={comment_id}")
            print(f"       内容：\"{content}\"")
            
            # 调用 API
            api_result = api.create_reply(comment_id, user_id, content)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
                
        elif action_type == "reply_to_reply":
            # 暂时简化处理，回复回复也使用 create_reply
            comment_id = action.get('comment_id', action.get('reply_id'))
            content = action.get('content', '')
            print(f"\n   [{i}/{len(actions)}] 💬 回复回复")
            print(f"       目标：评论 ID={comment_id}")
            print(f"       内容：\"{content}\"")
            
            # 调用 API
            api_result = api.create_reply(comment_id, user_id, content)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
                
        elif action_type == "like_post":
            post_id = action.get('post_id')
            print(f"\n   [{i}/{len(actions)}] 👍 点赞帖子")
            print(f"       目标：帖子 ID={post_id}")
            
            # 调用 API
            api_result = api.like_post(post_id, user_id)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
                
        elif action_type == "like_comment":
            comment_id = action.get('comment_id')
            print(f"\n   [{i}/{len(actions)}] 👍 点赞评论")
            print(f"       目标：评论 ID={comment_id}")
            
            # 调用 API
            api_result = api.like_comment(comment_id, user_id)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
                
        elif action_type == "like_reply":
            reply_id = action.get('reply_id')
            print(f"\n   [{i}/{len(actions)}] 👍 点赞回复")
            print(f"       目标：回复 ID={reply_id}")
            
            # 调用 API
            api_result = api.like_reply(reply_id, user_id)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
                
        elif action_type == "follow":
            target_user_id = action.get('user_id')
            print(f"\n   [{i}/{len(actions)}] ➕ 关注用户")
            print(f"       目标：用户 ID={target_user_id}")
            
            # 调用 API
            api_result = api.follow_user(target_user_id, user_id)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
        
        elif action_type == "quote_post":
            post_id = action.get('post_id')
            content = action.get('generated_content', '')  # 从生成阶段获取
            print(f"\n   [{i}/{len(actions)}] 🔄 直接转发帖子")
            print(f"       目标：帖子 ID={post_id}")
            print(f"       转发评论：\"{content}\"")
            
            # 调用 API
            api_result = api.create_quote_post(post_id, user_id, content)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
        
        elif action_type == "comment_with_repost":
            post_id = action.get('post_id')
            content = action.get('content', '')
            print(f"\n   [{i}/{len(actions)}] 🔄 评论并转发")
            print(f"       目标：帖子 ID={post_id}")
            print(f"       评论内容：\"{content}\"")
            
            # 调用 API
            api_result = api.create_comment_with_repost(post_id, user_id, content)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
        
        elif action_type == "reply_with_repost":
            comment_id = action.get('comment_id')
            content = action.get('content', '')
            quote_from_id = action.get('quote_from_id', comment_id)  # 默认使用 comment_id，后端会处理
            print(f"\n   [{i}/{len(actions)}] 🔄 回复并转发")
            print(f"       目标：评论 ID={comment_id}")
            print(f"       回复内容：\"{content}\"")
            
            # 调用 API
            api_result = api.create_reply_with_repost(comment_id, user_id, content, quote_from_id)
            if api_result["success"]:
                result["success"] = True
                success_count += 1
                print(f"       状态：✅ 成功")
            else:
                print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
        
        else:
            print(f"\n   [{i}/{len(actions)}] ❓ 执行未知行动：{action_type}")
            print(f"       状态：⚠️ 跳过")
        
        results.append(result)
        # 避免请求过快
        time.sleep(0.3)
    
    # 如果有帖子内容，执行发帖
    if post_content:
        print(f"\n   [发帖] 📝 发布新帖子")
        print(f"       内容：\"{post_content}\"")
        
        # 调用 API
        api_result = api.create_post(user_id, post_content)
        if api_result["success"]:
            results.append({"type": "post", "content": post_content, "success": True})
            success_count += 1
            print(f"       状态：✅ 成功")
        else:
            results.append({"type": "post", "content": post_content, "success": False})
            print(f"       状态：❌ 失败 - {api_result.get('error', '未知错误')}")
    
    print(f"\n{'='*60}")
    print(f"[执行] [{username}] 执行完成")
    print(f"[执行] 成功：{success_count}/{len(actions) + (1 if post_content else 0)} 个行动")
    print(f"{'='*60}")
    
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
    """
    条件：是否要生成内容
    
    两种情况需要进入生成阶段：
    1. 决定发帖（decide_to_post=True）
    2. 决定直接转发（quote_post 行动）- 需要生成转发评论
    """
    decisions = state.get("decisions", {})
    
    # 检查是否决定发帖
    if decisions.get("decide_to_post", False):
        return "generate"
    
    # 检查是否有直接转发的决策
    actions = decisions.get("actions", [])
    for action in actions:
        if action.get("type") == "quote_post":
            return "generate"
    
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
