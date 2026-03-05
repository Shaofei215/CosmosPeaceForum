"""
AI 行为引擎模块 (LLM 版本)
处理 AI 用户登录后的完整活动流程：
登录 → 浏览 → 思考(LLM) → 决策(LLM) → 行动 → 等待下次登录

LLM 集成版本功能：
1. 浏览 - 获取n条推荐帖子，n为ai_user_config.json中的posts_per_login_min/max间的随机整数
2. 思考 - 将 n 条帖子传给 LLM，进行思考和兴趣系数测定
3. 决策 - 将帖子对象和思考结果传入 LLM 进行最终决策
4. 行动 - 将决策结果应用于 social_platform
"""
import json
import random
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from .time_system import time_system
    from .llm import LLMClient
except ImportError:
    from time_system import time_system
    from llm import LLMClient


class AIBehaviorEngine:
    """AI 行为引擎 - 使用 LLM 进行智能决策"""
    
    def __init__(self, api_base_url: str = "http://127.0.0.1:8006", 
                 use_llm: bool = False,
                 llm_config_path: Optional[str] = None):
        """
        初始化 AI 行为引擎
        
        Args:
            api_base_url: 社交平台 API 基础 URL
            use_llm: 是否使用 LLM，默认 False（Demo 模式）
            llm_config_path: LLM 配置文件路径
        """
        self.api_base_url = api_base_url
        self.use_llm = use_llm
        self.llm_client: Optional[LLMClient] = None
        
        if use_llm:
            try:
                self.llm_client = LLMClient(config_path=llm_config_path)
                print("[行为引擎] LLM 客户端初始化成功")
            except Exception as e:
                print(f"[行为引擎] [警告] LLM 初始化失败: {e}，将使用 Demo 模式")
                self.use_llm = False
        
        self.session_stats = {
            "posts_created": 0,
            "comments_created": 0,
            "likes_given": 0,
            "follows_done": 0,
            "sessions_completed": 0,
            "llm_calls": 0
        }
        
        print(f"[行为引擎] 初始化完成，API地址: {api_base_url}，LLM: {'已启用' if use_llm else '已禁用'}")
        # 注意：已读记录现在由服务端管理，客户端无需维护

    def execute_login_session(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行一次完整的登录会话
        
        Args:
            user_config: 用户配置信息
            
        Returns:
            Dict: 会话结果统计
        """
        username = user_config.get("username", "Unknown")
        platform_user_id = user_config.get("platform_user_id")
        
        if not platform_user_id:
            print(f"[{username}] [错误] 缺少平台用户ID，无法执行会话")
            return {"success": False, "error": "Missing platform_user_id"}
        
        print(f"\n{'='*60}")
        print(f"[{username}] 开始登录会话 - {time_system.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        session_result = {
            "username": username,
            "start_time": time_system.now(),
            "actions": [],
            "success": True
        }

        try:
            # 1. 浏览 - 获取 n 条帖子
            posts = self._browse(user_config, platform_user_id)
            
            if not posts:
                print(f"[{username}] 时间线为空，跳过本次会话")
                session_result["actions"].append({"type": "skip", "reason": "Empty timeline"})
            else:
                # 2. 思考 - LLM 分析帖子
                thoughts = self._think(posts, user_config)
                
                # 3. 决策 - LLM 决定行动（传入 user_id 以获取关注列表）
                decisions = self._decide(thoughts, posts, user_config, platform_user_id)
                
                # 4. 行动 - 执行决策
                action_results = self._act(decisions, platform_user_id)
                session_result["actions"] = action_results
                
                # 统计行动结果
                for action in action_results:
                    if action.get("success"):
                        action_type = action.get("type")
                        if action_type == "post":
                            self.session_stats["posts_created"] += 1
                        elif action_type == "comment":
                            self.session_stats["comments_created"] += 1
                        elif action_type == "like":
                            self.session_stats["likes_given"] += 1
                        elif action_type == "follow":
                            self.session_stats["follows_done"] += 1
            
            self.session_stats["sessions_completed"] += 1
            
            print(f"\n[完成] [{username}] 会话完成")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"[{username}] [错误] 会话执行出错: {e}")
            session_result["success"] = False
            session_result["error"] = str(e)
        
        session_result["end_time"] = time_system.now()
        return session_result
    
    def _browse(self, user_config: Dict[str, Any], user_id: int) -> List[Dict[str, Any]]:
        """
        浏览 - 获取三层混合帖子（40%热门 + 30%最新 + 30%随机）
        服务端会自动过滤已读帖子并记录新的已读
        n 在 posts_per_login_min 和 posts_per_login_max 之间随机
        
        Args:
            user_config: 用户配置
            user_id: 平台用户ID
            
        Returns:
            List[Dict]: 帖子列表
        """
        username = user_config.get("username", "Unknown")
        posts_min = user_config.get("posts_per_login_min", 3)
        posts_max = user_config.get("posts_per_login_max", 10)
        
        # 随机决定浏览帖子数量
        n = random.randint(posts_min, posts_max)
        
        print(f"\n[浏览] [{username}] 正在浏览时间线...")
        print(f"[{username}] 计划浏览 {n} 条帖子 (范围: {posts_min}-{posts_max})")
        print(f"[{username}] 浏览策略: 40%热门 + 30%最新 + 30%随机，服务端过滤已读")
        
        try:
            # 直接请求 n 条，服务端会处理已读过滤
            url = f"{self.api_base_url}/posts/mixed"
            params = {
                "limit": n,
                "hot_ratio": 0.4,   # 40%热门
                "fresh_ratio": 0.3, # 30%最新
                "random_ratio": 0.3,# 30%随机
                "user_id": user_id  # 传入用户ID，服务端过滤已读
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                posts = response.json()
                
                print(f"[{username}] 获取到 {len(posts)} 条帖子")

                # 显示帖子摘要（包含热度信息）
                for i, post in enumerate(posts):
                    content_preview = post.get("content", "")[:35] + "..."
                    author = post.get("author", {}).get("username", "Unknown")
                    hot_score = post.get("hot_score", 0)
                    print(f"   [{i+1}] [热度]{hot_score:3d} {author}: {content_preview}")

                return posts
            else:
                print(f"[行为引擎] 获取混合帖子失败: HTTP {response.status_code}")
                # 降级到获取普通时间线
                return self._browse_fallback(user_id, n, username)
                
        except requests.exceptions.ConnectionError:
            print(f"[行为引擎] [错误] 无法连接到社交平台 API")
            return []
        except Exception as e:
            print(f"[行为引擎] 浏览时间线出错: {e}")
            return []
    
    def _browse_fallback(self, user_id: int, n: int, username: str) -> List[Dict[str, Any]]:
        """
        降级方案：获取用户时间线
        """
        try:
            url = f"{self.api_base_url}/feed/{user_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                all_posts = response.json()
                posts = all_posts[:n]
                print(f"[{username}] (降级) 获取到 {len(posts)} 条帖子")
                return posts
            return []
        except:
            return []
    
    def _think(self, posts: List[Dict[str, Any]], user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        思考阶段 - 使用 LLM 分析每条帖子并测定兴趣系数
        
        Args:
            posts: 帖子列表
            user_config: 用户配置
            
        Returns:
            List[Dict]: 每条帖子的思考结果，包含 interest_score (0-1)
        """
        username = user_config.get("username", "Unknown")
        personality = user_config.get("personality_prompt", "")
        
        print(f"\n🤔 [{username}] 正在思考...")
        
        if self.use_llm and self.llm_client:
            return self._think_with_llm(posts, user_config)
        else:
            return self._think_simulated(posts, user_config)
    
    def _think_with_llm(self, posts: List[Dict[str, Any]], user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """使用 LLM 进行思考分析，并根据兴趣系数获取评论"""
        username = user_config.get("username", "Unknown")
        personality = user_config.get("personality_prompt", "")
        
        thoughts = []
        
        print(f"[{username}] 正在分析帖子并测定兴趣系数...")
        
        system_prompt = f"""你是{username}，{personality}

你的任务是对看到的帖子进行思考和兴趣评估。
对于每条帖子，你需要：
1. 简单思考这条帖子内容
2. 给出一个0-1之间的兴趣系数（0=完全不感兴趣，1=非常感兴趣）

【极其重要】你的响应必须是一个合法的JSON对象，不要包含任何markdown代码块标记（如```json或```），不要包含任何解释性文字。

输出格式必须严格如下：
{{"thoughts":[{{"post_id":1,"thinking":"这条帖子很有趣","interest_score":0.8}},{{"post_id":2,"thinking":"这个话题不太感兴趣","interest_score":0.3}}]}}

规则：
1. 只输出JSON，不要换行、不要缩进、不要markdown标记
2. interest_score必须是0到1之间的数字
3. thinking字段使用纯文本，不要有特殊字符
4. 确保JSON格式完整，所有引号、括号必须匹配
5. 必须包含所有帖子的思考结果"""
        
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

请输出JSON格式的思考结果。"""
        
        try:
            result = self.llm_client.chat(user_prompt, system_prompt)
            self.session_stats["llm_calls"] += 1
            
            # 检查结果是否为字典
            if not isinstance(result, dict):
                print(f"[{username}] LLM 返回格式错误: 期望字典，得到 {type(result).__name__}，使用模拟思考")
                return self._think_simulated(posts, user_config)
            
            # 检查是否有解析错误
            if "parse_error" in result:
                print(f"[{username}] LLM 返回解析错误: {result.get('parse_error')}，使用模拟思考")
                return self._think_simulated(posts, user_config)
            
            # 获取思考数据，支持多种可能的字段名
            thoughts_data = result.get("thoughts", [])
            if not thoughts_data and "data" in result:
                thoughts_data = result.get("data", [])
            if not thoughts_data and isinstance(result, list):
                thoughts_data = result
            
            # 将思考结果与帖子关联，并根据兴趣系数获取评论
            for thought in thoughts_data:
                post_id = thought.get("post_id")
                interest_score = thought.get("interest_score", 0.5)
                
                # 找到对应的帖子
                for post in posts:
                    if post["id"] == post_id:
                        # 根据兴趣系数获取评论
                        comments = self._get_comments_by_interest(post_id, interest_score)
                        
                        thoughts.append({
                            "post": post,
                            "thinking": thought.get("thinking", ""),
                            "interest_score": interest_score,
                            "comments": comments,
                            "comments_read": len(comments)
                        })
                        break
            
            print(f"[{username}] LLM 思考完成，分析了 {len(thoughts)} 条帖子")
            for t in thoughts:
                comments_info = f"[阅读了 {t['comments_read']} 条评论]" if t['comments_read'] > 0 else "[未阅读评论]"
                print(f"   [思考] {t['post']['author']['username']}: {t['thinking'][:25]}... (兴趣: {t['interest_score']:.2f}) {comments_info}")
            
        except Exception as e:
            print(f"[{username}] LLM 思考失败: {e}，使用模拟思考")
            thoughts = self._think_simulated(posts, user_config)
        
        return thoughts
    
    def _think_simulated(self, posts: List[Dict[str, Any]], user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """模拟思考（Demo 模式），并根据兴趣系数获取评论"""
        username = user_config.get("username", "Unknown")
        personality = user_config.get("personality_prompt", "")
        
        thoughts = []
        
        print(f"[{username}] 正在模拟分析帖子...")
        
        for post in posts:
            author = post.get("author", {}).get("username", "Unknown")
            content = post.get("content", "")
            post_id = post["id"]
            
            # 基于内容长度和性格生成思考
            if "活泼" in personality or "开朗" in personality:
                thinking_options = [
                    f"哇，{author}发的这个看起来很有趣！",
                    f"{author}说得太对了，我完全同意！",
                    f"这个内容让我心情变好了~"
                ]
                base_score = 0.7
            elif "冷静" in personality or "理性" in personality:
                thinking_options = [
                    f"{author}的观点值得思考...",
                    f"这条信息有一定价值",
                    f"需要进一步分析{author}的观点"
                ]
                base_score = 0.5
            else:
                thinking_options = [
                    f"{author}分享的内容挺有意思的",
                    f"这个话题引起了我的注意",
                    f"{author}说得有道理"
                ]
                base_score = 0.6
            
            # 根据内容调整兴趣系数
            interest_score = base_score + random.uniform(-0.2, 0.2)
            interest_score = max(0.0, min(1.0, interest_score))
            
            # 根据兴趣系数获取评论
            comments = self._get_comments_by_interest(post_id, interest_score)
            
            thoughts.append({
                "post": post,
                "thinking": random.choice(thinking_options),
                "interest_score": interest_score,
                "comments": comments,
                "comments_read": len(comments)
            })
        
        print(f"[{username}] 模拟思考完成，分析了 {len(thoughts)} 条帖子")
        for t in thoughts:
            comments_info = f"[阅读了 {t['comments_read']} 条评论]" if t['comments_read'] > 0 else "[未阅读评论]"
            print(f"   [思考] {t['post']['author']['username']}: {t['thinking'][:25]}... (兴趣: {t['interest_score']:.2f}) {comments_info}")
        
        return thoughts
    
    def _get_comments_by_interest(self, post_id: int, interest_score: float) -> List[Dict[str, Any]]:
        """
        根据兴趣系数获取评论和回复
        
        阅读评论数 = floor(兴趣系数 × 7)
        每条评论的回复数 = floor(兴趣系数 × 7)
        例如：兴趣系数 0.6 → 阅读 4 条评论，每条评论阅读 4 条回复
        
        评论排序：70% 最热 + 30% 最新
        回复排序：70% 最热 + 30% 最新
        
        Args:
            post_id: 帖子 ID
            interest_score: 兴趣系数（0-1）
            
        Returns:
            List[Dict]: 评论列表（包含回复）
        """
        # 计算需要阅读多少条评论和每条评论的回复数
        max_items = 7
        comments_to_read = int(interest_score * max_items)
        replies_per_comment = int(interest_score * max_items)  # 每条评论阅读的回复数
        
        if comments_to_read <= 0:
            return []
        
        try:
            # 1. 获取评论（使用混合排序：70% 最热 + 30% 最新）
            url = f"{self.api_base_url}/posts/{post_id}/comments"
            params = {
                "mixed": "true",
                "limit": comments_to_read * 2  # 获取更多以确保去重后足够
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                all_comments = response.json()
                # 只取前 N 条评论
                selected_comments = all_comments[:comments_to_read]
                
                # 2. 为每条评论获取回复（也使用兴趣系数控制数量和混合排序）
                if replies_per_comment > 0:
                    for comment in selected_comments:
                        comment_id = comment.get("id")
                        # 获取该评论的所有回复（使用混合排序：70% 最热 + 30% 最新）
                        reply_url = f"{self.api_base_url}/comments/{comment_id}/replies"
                        reply_params = {
                            "mixed": "true",
                            "limit": replies_per_comment * 2  # 获取更多以确保去重后足够
                        }
                        reply_response = requests.get(reply_url, params=reply_params, timeout=10)
                        
                        if reply_response.status_code == 200:
                            all_replies = reply_response.json()
                            # 只取前 N 条回复
                            comment["replies"] = all_replies[:replies_per_comment]
                        else:
                            comment["replies"] = []
                    
                    print(f"[兴趣阅读] 兴趣系数 {interest_score:.2f} → 阅读 {comments_to_read} 条评论，每条评论最多 {replies_per_comment} 条回复")
                
                return selected_comments
            else:
                return []
                
        except Exception as e:
            print(f"[行为引擎] 获取评论失败: {e}")
            return []
    
    def _decide(self, thoughts: List[Dict[str, Any]], posts: List[Dict[str, Any]], 
                user_config: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """
        决策阶段 - 使用 LLM 基于思考结果做最终决策
        
        Args:
            thoughts: 思考结果列表
            posts: 帖子列表
            user_config: 用户配置
            user_id: 平台用户ID
            
        Returns:
            Dict: 决策结果
        """
        username = user_config.get("username", "Unknown")
        
        print(f"\n[决策] [{username}] 正在决策...")
        
        # 获取关注列表
        following_list = self._get_following_list(user_id)
        if following_list:
            print(f"[{username}] 已关注 {len(following_list)} 位用户: {', '.join(following_list[:5])}{'...' if len(following_list) > 5 else ''}")
        
        if self.use_llm and self.llm_client:
            return self._decide_with_llm(thoughts, user_config, following_list)
        else:
            return self._decide_simulated(thoughts, user_config, following_list)
    
    def _decide_with_llm(self, thoughts: List[Dict[str, Any]], user_config: Dict[str, Any], 
                         following_list: List[str] = None) -> Dict[str, Any]:
        """使用 LLM 进行决策 - 支持评论、回复、点赞帖子/评论/回复，考虑关注关系"""
        username = user_config.get("username", "Unknown")
        personality = user_config.get("personality_prompt", "")
        
        # 构建关注信息
        following_info = ""
        if following_list:
            following_info = f"\n你关注的用户: {', '.join(following_list)}\n你对关注用户的帖子/评论/回复会有更高的兴趣和互动意愿。"
        
        system_prompt = f"""你是{username}，{personality}{following_info}

基于你对帖子的思考结果和阅读到的评论/回复，决定你的行动。

可选行动类型：
1. "post" - 发布新帖子（需要提供content）
2. "comment" - 评论某条帖子（需要提供post_id和content）
3. "reply_to_comment" - 回复某条评论（需要提供comment_id和content）
4. "reply_to_reply" - 回复某条回复（需要提供reply_id和content）
5. "like_post" - 点赞帖子（需要提供post_id）
6. "like_comment" - 点赞评论（需要提供comment_id）
7. "like_reply" - 点赞回复（需要提供reply_id）
8. "follow" - 关注某用户（需要提供user_id）
9. "skip" - 什么都不做

【发帖指导】
当你选择 "post" 时，表示你想要发布一条新帖子。适合发帖的情况：
- 浏览的内容给了你灵感，想要分享自己的想法或经历
- 想要主动开启一个新话题，与大家讨论
- 有想要表达的情感、观点或日常生活分享
- 不需要针对特定帖子，而是想独立发表内容

发帖内容应该：
- 符合你的性格和身份
- 可以是原创内容，也可以是对浏览内容的感悟
- 长度适中，像真实的社交媒体帖子
- 不需要每条都发，有表达欲望时再发

【字数限制】
- 帖子内容：100字以内为宜
- 评论内容：50字以内为宜
- 回复内容：50字以内为宜
- 保持简洁，像真实社交媒体一样

【多行动说明】
你一次登录可以执行多个行动，actions数组可以包含多个行动。例如：
- 可以既发帖又评论
- 可以点赞多条内容
- 可以评论后再回复
根据你的兴趣和意愿自由组合。

【极其重要】你的响应必须是一个合法的JSON对象，不要包含任何markdown代码块标记，不要包含任何解释性文字。

输出格式必须严格如下（单行JSON）：
{{"actions":[{{"type":"post","content":"今天天气真不错，想出去走走"}},{{"type":"comment","post_id":1,"content":"说得太对了！"}},{{"type":"like_post","post_id":2}},{{"type":"reply_to_comment","comment_id":3,"content":"我也这么觉得"}}]}}

规则：
1. 只输出单行JSON，不要换行、不要缩进、不要markdown标记
2. 确保JSON格式完整，所有引号、括号必须匹配
3. actions数组可以为空（表示skip）
4. content字段使用纯文本，不要有特殊字符
5. 根据兴趣系数和关注关系决定行动：
   - 对关注用户的帖子/评论/回复，兴趣系数自动提高
   - 高兴趣可以评论/回复，中等兴趣可以点赞，低兴趣跳过
6. 发帖是可选的，不要每条都发，有灵感时才发"""
        
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
                            for reply in comment["replies"][:3]  # 最多3条回复
                        ]
                    
                    post_data["comments"].append(comment_data)
            
            thoughts_info.append(post_data)
        
        user_prompt = f"""基于以下帖子和评论/回复的思考结果，决定你的行动：

{json.dumps(thoughts_info, ensure_ascii=False)}

请输出JSON格式的决策结果。可以针对帖子、评论或回复进行互动。"""
        
        try:
            result = self.llm_client.chat(user_prompt, system_prompt)
            self.session_stats["llm_calls"] += 1
            
            # 检查结果是否为字典
            if not isinstance(result, dict):
                print(f"[{username}] LLM 返回格式错误: 期望字典，得到 {type(result).__name__}，使用模拟决策")
                return self._decide_simulated(thoughts, user_config)
            
            # 检查是否有解析错误
            if "parse_error" in result:
                print(f"[{username}] LLM 返回解析错误: {result.get('parse_error')}，使用模拟决策")
                return self._decide_simulated(thoughts, user_config)
            
            # 检查必要的字段，支持多种可能的字段名
            actions = result.get("actions", [])
            if not actions and "data" in result:
                actions = result.get("data", [])
            
            if not actions:
                print(f"[{username}] LLM 返回缺少 'actions' 字段，使用模拟决策")
                return self._decide_simulated(thoughts, user_config)
            
            # 将处理后的 actions 放回 result
            result["actions"] = actions
            
            print(f"[{username}] LLM 决策完成")
            print(f"[{username}] 决策: {json.dumps(result, ensure_ascii=False)}")
            
            return result
            
        except Exception as e:
            print(f"[{username}] LLM 决策失败: {e}，使用模拟决策")
            return self._decide_simulated(thoughts, user_config)
    
    def _decide_simulated(self, thoughts: List[Dict[str, Any]], user_config: Dict[str, Any],
                          following_list: List[str] = None) -> Dict[str, Any]:
        """模拟决策（Demo 模式）- 考虑关注关系"""
        username = user_config.get("username", "Unknown")
        following_list = following_list or []
        
        decisions = {
            "actions": [],
            "reason": "基于兴趣系数和关注关系的模拟决策"
        }
        
        # 决策 1: 是否发帖（基于随机概率）
        if random.random() < 0.3:  # 30% 概率发帖
            post_contents = [
                "今天也是充满活力的一天！",
                "刚刚想到了一些有趣的事情...",
                "大家最近都在忙什么呢？",
                "分享一个今天的小感悟",
                "天气不错，心情也很好~"
            ]
            decisions["actions"].append({
                "type": "post",
                "content": random.choice(post_contents)
            })
        
        # 决策 2: 基于兴趣系数和关注关系选择互动帖子
        if thoughts:
            # 为每条思考添加"有效兴趣系数"（考虑关注关系）
            for thought in thoughts:
                author = thought["post"]["author"]["username"]
                base_score = thought["interest_score"]
                # 如果是关注用户，兴趣系数提高
                if author in following_list:
                    thought["effective_score"] = min(1.0, base_score + 0.3)
                    thought["is_following"] = True
                else:
                    thought["effective_score"] = base_score
                    thought["is_following"] = False
            
            # 按有效兴趣系数排序
            sorted_thoughts = sorted(thoughts, key=lambda x: x["effective_score"], reverse=True)
            
            for thought in sorted_thoughts[:2]:  # 最多互动2条
                if thought["effective_score"] > 0.5:  # 降低阈值
                    post = thought["post"]
                    author = post["author"]["username"]
                    
                    # 对关注用户更倾向于评论，非关注用户更倾向于点赞
                    is_following = author in following_list
                    
                    if is_following and random.random() < 0.7:  # 关注用户70%概率评论
                        comments = [
                            f"@{author} 说得太好了！",
                            f"@{author} 完全同意你的观点",
                            f"@{author} 这个观点很有意思",
                            f"@{author} 感谢分享这么好的内容",
                            f"@{author} 哈哈，确实如此"
                        ]
                        decisions["actions"].append({
                            "type": "comment",
                            "post_id": post["id"],
                            "content": random.choice(comments)
                        })
                    elif random.random() < 0.5:  # 50%概率点赞
                        decisions["actions"].append({
                            "type": "like_post",
                            "post_id": post["id"]
                        })
        
        # 如果没有决策任何行动
        if not decisions["actions"]:
            decisions["actions"].append({"type": "skip", "reason": "没有感兴趣的内容"})
        
        print(f"[{username}] 模拟决策完成")
        print(f"[{username}] 决策: {json.dumps(decisions, ensure_ascii=False)}")
        
        return decisions
    
    def _act(self, decisions: Dict[str, Any], user_id: int) -> List[Dict[str, Any]]:
        """
        行动阶段 - 执行决策
        
        Args:
            decisions: 决策结果
            user_id: 平台用户ID
            
        Returns:
            List[Dict]: 行动结果列表
        """
        results = []
        
        print(f"\n[执行] 开始执行行动...")
        
        for action in decisions.get("actions", []):
            action_type = action.get("type")
            result = {"type": action_type, "success": False}
            
            try:
                if action_type == "post":
                    result.update(self._create_post(user_id, action.get("content", "")))
                elif action_type == "comment":
                    result.update(self._create_comment(user_id, action.get("post_id"), 
                                                       action.get("content", "")))
                elif action_type == "reply_to_comment":
                    result.update(self._create_reply(user_id, action.get("comment_id"), 
                                                    action.get("content", ""), None))
                elif action_type == "reply_to_reply":
                    result.update(self._create_reply(user_id, None, 
                                                    action.get("content", ""), 
                                                    action.get("reply_id")))
                elif action_type == "like_post":
                    result.update(self._like_post(user_id, action.get("post_id")))
                elif action_type == "like_comment":
                    result.update(self._like_comment(user_id, action.get("comment_id")))
                elif action_type == "like_reply":
                    result.update(self._like_reply(user_id, action.get("reply_id")))
                elif action_type == "follow":
                    result.update(self._follow_user(user_id, action.get("user_id")))
                elif action_type == "skip":
                    result["success"] = True
                    result["message"] = "跳过本次行动"
                    print(f"   ⏭️  选择跳过")
                else:
                    # 兼容旧版类型
                    if action_type == "like":
                        result.update(self._like_post(user_id, action.get("post_id")))
                    else:
                        result["error"] = f"未知行动类型: {action_type}"
                        print(f"   [警告] 未知行动类型: {action_type}")
                    
            except Exception as e:
                result["error"] = str(e)
                print(f"   [错误] 行动失败: {e}")
            
            results.append(result)
        
        return results
    
    def _create_post(self, user_id: int, content: str) -> Dict[str, Any]:
        """创建帖子"""
        try:
            url = f"{self.api_base_url}/posts"
            payload = {"content": content}
            params = {"author_id": user_id}
            
            response = requests.post(url, json=payload, params=params, timeout=10)
            
            if response.status_code == 201:
                post = response.json()
                print(f"   📝 发布帖子成功 [ID:{post['id']}]: {content[:40]}...")
                return {"success": True, "post_id": post["id"]}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _create_comment(self, user_id: int, post_id: int, content: str) -> Dict[str, Any]:
        """创建评论"""
        try:
            url = f"{self.api_base_url}/posts/{post_id}/comments"
            payload = {"content": content}
            params = {"author_id": user_id}
            
            response = requests.post(url, json=payload, params=params, timeout=10)
            
            if response.status_code == 201:
                comment = response.json()
                print(f"   [评论] 评论成功 [帖子ID:{post_id}]: {content}")
                return {"success": True, "comment_id": comment["id"]}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _like_post(self, user_id: int, post_id: int) -> Dict[str, Any]:
        """点赞帖子"""
        try:
            url = f"{self.api_base_url}/posts/{post_id}/like"
            params = {"user_id": user_id}
            
            response = requests.post(url, params=params, timeout=10)
            
            if response.status_code == 201:
                print(f"   ❤️  点赞成功 [帖子ID:{post_id}]")
                return {"success": True}
            elif response.status_code == 400:
                print(f"   [警告]  已经点赞过 [帖子ID:{post_id}]")
                return {"success": True, "message": "Already liked"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _follow_user(self, follower_id: int, following_id: int) -> Dict[str, Any]:
        """关注用户"""
        if follower_id == following_id:
            return {"success": False, "error": "Cannot follow self"}
        
        try:
            url = f"{self.api_base_url}/users/{following_id}/follow"
            params = {"follower_id": follower_id}
            
            response = requests.post(url, params=params, timeout=10)
            
            if response.status_code == 201:
                print(f"   🤝 关注成功 [用户ID:{following_id}]")
                return {"success": True}
            elif response.status_code == 400:
                print(f"   [警告]  已经关注过 [用户ID:{following_id}]")
                return {"success": True, "message": "Already following"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _create_reply(self, user_id: int, comment_id: Optional[int], 
                     content: str, parent_reply_id: Optional[int]) -> Dict[str, Any]:
        """创建回复（回复评论或回复回复）"""
        try:
            if not comment_id and not parent_reply_id:
                return {"success": False, "error": "必须提供comment_id或parent_reply_id"}
            
            # 如果只有 parent_reply_id，需要先获取对应的 comment_id
            if parent_reply_id and not comment_id:
                # 通过 API 获取回复信息以找到对应的 comment_id
                reply_info_url = f"{self.api_base_url}/replies/{parent_reply_id}"
                try:
                    reply_response = requests.get(reply_info_url, timeout=5)
                    if reply_response.status_code == 200:
                        reply_data = reply_response.json()
                        comment_id = reply_data.get("comment_id")
                    else:
                        return {"success": False, "error": f"无法获取回复信息: HTTP {reply_response.status_code}"}
                except:
                    # 如果获取失败，尝试直接使用 comment_id=1（兜底方案）
                    print(f"   [警告] 无法获取回复 {parent_reply_id} 的信息，尝试使用默认方案")
                    # 这里我们需要一个更好的方案，暂时返回错误
                    return {"success": False, "error": "回复回复功能需要comment_id"}
            
            # 使用 /comments/{comment_id}/replies 端点
            url = f"{self.api_base_url}/comments/{comment_id}/replies"
            
            payload = {"content": content}
            if parent_reply_id:
                payload["parent_reply_id"] = parent_reply_id
            
            params = {"author_id": user_id}
            
            response = requests.post(url, json=payload, params=params, timeout=10)
            
            if response.status_code == 201:
                reply = response.json()
                target_desc = f"回复ID:{parent_reply_id}" if parent_reply_id else f"评论ID:{comment_id}"
                print(f"   💬 回复成功 [{target_desc}]: {content[:40]}...")
                return {"success": True, "reply_id": reply["id"]}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _like_comment(self, user_id: int, comment_id: int) -> Dict[str, Any]:
        """点赞评论"""
        try:
            url = f"{self.api_base_url}/comments/{comment_id}/like"
            params = {"user_id": user_id}
            
            response = requests.post(url, params=params, timeout=10)
            
            if response.status_code == 201:
                print(f"   ❤️  点赞评论成功 [评论ID:{comment_id}]")
                return {"success": True}
            elif response.status_code == 400:
                print(f"   [警告]  已经点赞过该评论 [评论ID:{comment_id}]")
                return {"success": True, "message": "Already liked"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _like_reply(self, user_id: int, reply_id: int) -> Dict[str, Any]:
        """点赞回复"""
        try:
            url = f"{self.api_base_url}/replies/{reply_id}/like"
            params = {"user_id": user_id}
            
            response = requests.post(url, params=params, timeout=10)
            
            if response.status_code == 201:
                print(f"   ❤️  点赞回复成功 [回复ID:{reply_id}]")
                return {"success": True}
            elif response.status_code == 400:
                print(f"   [警告]  已经点赞过该回复 [回复ID:{reply_id}]")
                return {"success": True, "message": "Already liked"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_following_list(self, user_id: int) -> List[str]:
        """获取用户关注的用户列表（返回用户名列表）"""
        try:
            url = f"{self.api_base_url}/users/{user_id}/following"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                following = response.json()
                # 提取用户名列表
                usernames = [user.get("username", "") for user in following if user.get("username")]
                return usernames
            else:
                return []
                
        except Exception as e:
            print(f"[行为引擎] 获取评论失败：{e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取行为统计"""
        return self.session_stats.copy()
    
    def print_stats(self):
        """打印行为统计"""
        print("\n" + "="*60)
        print("[统计] AI 行为统计")
        print("="*60)
        print(f"完成会话数: {self.session_stats['sessions_completed']}")
        print(f"发布帖子数: {self.session_stats['posts_created']}")
        print(f"发表评论数: {self.session_stats['comments_created']}")
        print(f"点赞次数:   {self.session_stats['likes_given']}")
        print(f"关注次数:   {self.session_stats['follows_done']}")
        if self.use_llm:
            print(f"LLM 调用数: {self.session_stats['llm_calls']}")
        print("="*60)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("="*60)
    print("    AI 行为引擎测试")
    print("="*60)
    print("\n[警告]  请确保社交平台后端已启动: uvicorn app.main:app --reload")
    print("\n默认使用 Demo 模式（模拟 LLM）")
    print("如需使用真实 LLM，请配置 llm_config.json 并设置 use_llm=True\n")
    
    # 创建行为引擎（Demo 模式）
    engine = AIBehaviorEngine(use_llm=False)
    
    # 模拟用户配置
    test_user = {
        "id": 1,
        "username": "三月七",
        "platform_user_id": 1,
        "personal_signature": "今天也是三月七！",
        "personality_prompt": "你是《崩坏：星穹铁道》中开朗活泼、充满好奇心的三月七。",
        "monthly_logins": 50,
        "posts_per_login_min": 4,
        "posts_per_login_max": 14,
        "post_tendency": 0.7,
        "interaction_tendency": 0.9
    }
    
    # 执行一次会话
    result = engine.execute_login_session(test_user)
    
    # 打印统计
    engine.print_stats()
    
    print("\n[完成] 测试完成!")
