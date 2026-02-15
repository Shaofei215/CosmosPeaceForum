import random
import json
import time
import threading
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# 创建Flask应用
app = Flask(__name__, static_folder='.')
CORS(app)  # 启用CORS，允许前端访问

# 创建用户类
class User(object):

    def __init__(self, user_id, username, avatar, personal_signature, 
                 monthly_logins, posts_per_login_min, posts_per_login_max,
                 interaction_tendency, post_tendency,
                 post_prompt, comment_prompt, following=None):
        self.id = user_id
        self.username = username
        self.avatar = avatar
        self.personal_signature = personal_signature
        
        # 新架构配置：登录机制
        self.monthly_logins = monthly_logins  # 每月登录次数
        self.posts_per_login_min = posts_per_login_min  # 每次登录最少看帖数
        self.posts_per_login_max = posts_per_login_max  # 每次登录最多看帖数
        self.interaction_tendency = interaction_tendency  # 互动系数（0-1）
        self.post_tendency = post_tendency  # 发帖系数（0-1）
        
        # 保留旧配置兼容（实际使用新配置）
        self.frequency = monthly_logins  # 兼容旧代码
        self.interaction_frequency = monthly_logins  # 兼容旧代码
        
        self.prompt = post_prompt
        self.comment_prompt = comment_prompt
        self.following = following or []  # 关注列表（存储用户ID）

    def get_daily_login_frequency(self):
        """计算每日平均登录频率"""
        return self.monthly_logins / 30  # 假设每月30天
    
    def get_hourly_login_lambda(self):
        """计算每小时的登录泊松分布参数λ"""
        daily_logins = self.get_daily_login_frequency()
        return daily_logins / 24  # 每小时的平均登录数
    
    def get_random_posts_per_login(self):
        """随机决定本次登录看多少条帖子"""
        return random.randint(self.posts_per_login_min, self.posts_per_login_max)

    def post(self):
        """生成帖子内容（调用硅基流动API）"""
        import requests
        
        # 硅基流动API配置
        api_url = "https://api.siliconflow.cn/v1/chat/completions"
        api_key = "sk-kookgpxohtivpdxotdnhgdgrjqidpsnhfptsmwrspjwiiukj"  # 需要替换为实际的API密钥
        
        # API请求参数
        payload = {
            "model": "Pro/moonshotai/Kimi-K2.5",
            "messages": [
                {"role": "system", "content": "你是一个社交平台用户，根据给定的prompt生成自然的帖子内容。"},
                {"role": "user", "content": self.prompt}
            ],
            "temperature": 1.0,
            "max_tokens": 300
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        try:
            # 发送API请求
            response = requests.post(api_url, json=payload, headers=headers)
            response.raise_for_status()  # 检查响应状态
            
            # 解析响应
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            return f"{content}"
        except Exception as e:
            # 错误处理，返回默认内容
            print(f"API调用失败: {str(e)}")
            return f"[{self.username}] 使用prompt: {self.prompt[:50]}..."

    def poisson_probability(self, k, lambda_):
        """计算泊松分布的概率质量函数
        P(X=k) = (e^(-λ) * λ^k) / k!
        """
        if lambda_ < 0:
            return 0
        if k < 0:
            return 0
        if k == 0:
            return math.exp(-lambda_)
        return (lambda_ * self.poisson_probability(k-1, lambda_)) / k

    def generate_poisson(self, lambda_):
        """生成符合泊松分布的随机数
        使用拒绝采样法生成泊松分布随机数
        """
        if lambda_ < 0.000001:
            return 0
        
        # 对于小lambda值，使用直接计算
        if lambda_ < 10:
            p = math.exp(-lambda_)
            k = 0
            s = p
            u = random.random()
            while u > s:
                k += 1
                p *= lambda_ / k
                s += p
            return k
        else:
            # 对于大lambda值，使用正态近似
            # 泊松分布当lambda较大时近似于正态分布N(lambda, lambda)
            x = int(random.normalvariate(lambda_, math.sqrt(lambda_)) + 0.5)
            return max(0, x)
    
    def generate_exponential_interval(self, lambda_):
        """生成符合指数分布的时间间隔
        用于泊松过程中事件之间的时间间隔
        指数分布概率密度函数: f(t) = λe^(-λt)
        使用逆变换法生成: t = -ln(u)/λ
        
        Args:
            lambda_: 事件发生率（单位时间内的平均事件数）
            
        Returns:
            float: 生成的时间间隔
        """
        if lambda_ < 0.000001:
            return float('inf')  # 发生率极低时，返回无穷大间隔
        
        u = random.random()
        # 确保u不为0，避免ln(0)错误
        while u == 0:
            u = random.random()
        
        return -math.log(u) / lambda_


# 导入用户信息
users = []
with open("ai_users_config.json", "r", encoding= "UTF-8") as USER_CONFIG:
    config = json.load(USER_CONFIG)
    for user in config["ai_users"]:
        users.append(User(
            user["id"],
            user["username"],
            user["avatar"],
            user["personal_signature"],
            user["monthly_logins"],
            user["posts_per_login_min"],
            user["posts_per_login_max"],
            user["interaction_tendency"],
            user["post_tendency"],
            user["post_prompt"],
            user["comment_prompt"],
            user.get("following", []))
        )

# 存储帖子数据
posts = []

# 帖子数据的线程锁，用于保护多线程环境下的帖子操作
posts_lock = threading.Lock()

# 存储用户对象映射（用于快速查找）
user_map = {user.id: user for user in users}

# 初始化帖子（创建几条系统欢迎帖，让社区有内容可供互动）
def initialize_posts():
    """初始化帖子，创建几条系统欢迎帖"""
    global posts
    
    initial_posts = [
        {
            "id": 1,
            "author": {
                "id": 0,
                "name": "黑塔空间站官方",
                "avatar": "🛰️",
                "personal_signature": "黑塔女士的空间站"
            },
            "content": "🎉 黑塔社区正式启用啦！欢迎大家在这里分享生活、交流心得~",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stats": {
                "likes": 0,
                "comments": 0,
                "shares": 0
            },
            "interactions": {
                "likes": [],
                "comments": []
            }
        },
        {
            "id": 2,
            "author": {
                "id": 0,
                "name": "星穹列车官方",
                "avatar": "🚂",
                "personal_signature": "愿此行，终抵群星！"
            },
            "content": "星穹列车已正式入驻黑塔社区。愿此行，终抵群星！",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stats": {
                "likes": 0,
                "comments": 0,
                "shares": 0
            },
            "interactions": {
                "likes": [],
                "comments": []
            }
        },
        {
            "id": 3,
            "author": {
                "id": 0,
                "name": "贝洛伯格政府官方",
                "avatar": "🏛️",
                "personal_signature": "秩序与未来并行。"
            },
            "content": "贝洛伯格政府官方黑塔账号已开通。贝洛伯格永远欢迎每一位访客，愿冰雪之城带给你温暖与希望。❄️",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stats": {
                "likes": 0,
                "comments": 0,
                "shares": 0
            },
            "interactions": {
                "likes": [],
                "comments": []
            }
        }
    ]
    
    posts = initial_posts
    print(f"✅ 已初始化 {len(posts)} 条系统欢迎帖")

# 调用初始化
initialize_posts()


class AIScheduler:
    """AI用户调度器"""
    
    # 类级别配置：测试模式下的时间缩放比例
    # 例如：test_hour_duration = 10 表示 10秒 = 1小时
    # 修改为 20 则表示 20秒 = 1小时
    test_hour_duration = 20  # 测试模式下每小时的持续时间（秒），可自由调节
    
    def __init__(self, users):
        self.users = users
        self.running = True
        self.test_mode = True  # 测试模式，使用缩短的时间单位
        # 统计相关属性
        self.statistics_start_time = time.time()  # 统计开始时间
        self.statistics_authors = set()  # 存储统计周期内的发帖作者ID（用于去重）
        self.statistics_post_count = 0  # 统计周期内的帖子数量
        self.statistics_lock = threading.Lock()  # 统计操作的线程锁
        self.statistics_thread = None  # 统计线程
        self.statistics_running = True
    
    def record_post_statistics(self, author_id):
        """记录发帖统计（在API调用前执行，避免延迟影响统计准确性）
        
        Args:
            author_id: 发帖作者ID
        """
        with self.statistics_lock:
            self.statistics_authors.add(author_id)
            self.statistics_post_count += 1
    
    def reset_statistics(self):
        """重置统计数据"""
        with self.statistics_lock:
            self.statistics_start_time = time.time()
            self.statistics_authors.clear()
            self.statistics_post_count = 0
    
    def calculate_statistics(self):
        """计算统计数据
        
        Returns:
            tuple: (发帖人数, 发帖总数量)
        """
        with self.statistics_lock:
            return len(self.statistics_authors), self.statistics_post_count
    
    def print_statistics(self):
        """打印统计结果"""
        poster_count, post_count = self.calculate_statistics()
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{current_time}] 发帖人数: {poster_count}人, 发帖总数量: {post_count}条")
    
    def start_statistics_timer(self):
        """启动统计定时器"""
        def timer_task():
            while self.statistics_running:
                # 计算下一次统计的时间间隔
                if self.test_mode:
                    # 测试模式：24个测试小时 = 24 * test_hour_duration 秒
                    interval = 24 * self.test_hour_duration
                else:
                    # 正常模式：24小时 = 86400秒
                    interval = 86400
                
                # 等待到下一次统计
                time.sleep(interval)
                
                # 打印统计结果
                self.print_statistics()
                
                # 重置统计数据
                self.reset_statistics()
        
        # 在新线程中运行定时器
        self.statistics_thread = threading.Thread(target=timer_task)
        self.statistics_thread.daemon = True
        self.statistics_thread.start()
    
    def stop_statistics(self):
        """停止统计模块"""
        self.statistics_running = False
        if self.statistics_thread:
            self.statistics_thread.join(timeout=1.0)
    
    def start(self):
        """启动调度器"""
        if self.test_mode:
            print("=== AI社交平台测试模式 ===")
            print(f"时间尺度：每{self.test_hour_duration}秒模拟1小时\n")
        else:
            print("=== AI社交平台正常模式 ===")
        
        print("用户信息:")
        for user in self.users:
            daily_login = user.get_daily_login_frequency()
            hourly_lambda = user.get_hourly_login_lambda()
            p0 = user.poisson_probability(0, hourly_lambda)
            p1 = user.poisson_probability(1, hourly_lambda)
            p2 = user.poisson_probability(2, hourly_lambda)
            print(f"{user.avatar} {user.username} - 每月登录: {user.monthly_logins}次 - "
                  f"每日平均: {daily_login:.2f}次 - 看帖: {user.posts_per_login_min}-{user.posts_per_login_max}条 - "
                  f"互动系数: {user.interaction_tendency} - 发帖系数: {user.post_tendency} - "
                  f"每小时λ: {hourly_lambda:.4f}")
        
        print("\n=== 开始随机发帖 ===")
        print("按Ctrl+C停止测试\n")
        
        # 启动统计定时器
        self.start_statistics_timer()
        
        # 启动模拟
        try:
            self.run_simulation()
        except KeyboardInterrupt:
            print("\n测试已停止")
            # 停止统计模块
            self.stop_statistics()
    
    def _add_like_to_comment(self, target_post, target_comment, user, interaction_time):
        """给评论添加点赞
        
        Args:
            target_post: 目标帖子
            target_comment: 目标评论
            user: 点赞用户
            interaction_time: 点赞时间
        """
        with posts_lock:
            # 检查是否已点赞
            existing_like = next((like for like in target_comment.get("likes", []) if like["user_id"] == user.id), None)
            if existing_like:
                return
            
            # 添加点赞记录
            like_record = {
                "user_id": user.id,
                "username": user.username,
                "avatar": user.avatar,
                "timestamp": interaction_time
            }
            
            if "likes" not in target_comment:
                target_comment["likes"] = []
            target_comment["likes"].append(like_record)
            target_comment["likes_count"] = len(target_comment["likes"])

    def _add_like_to_post(self, target_post, user, interaction_time):
        """为帖子添加点赞
        
        Args:
            target_post: 目标帖子
            user: 点赞用户
            interaction_time: 互动时间
        """
        with posts_lock:
            # 检查用户是否已经点赞过
            for like in target_post["interactions"]["likes"]:
                if like["user_id"] == user.id:
                    return  # 已经点赞过，不重复添加
            
            # 添加点赞记录
            like_record = {
                "user_id": user.id,
                "username": user.username,
                "avatar": user.avatar,
                "timestamp": interaction_time
            }
            target_post["interactions"]["likes"].append(like_record)
            target_post["stats"]["likes"] = len(target_post["interactions"]["likes"])

    def _add_comment_to_post(self, target_post, user, content, interaction_time, parent_comment_id=None, reply_to_user=None):
        """为帖子添加评论（支持两层评论）
        
        Args:
            target_post: 目标帖子
            user: 评论用户
            content: 评论内容
            interaction_time: 互动时间
            parent_comment_id: 父评论ID（如果是回复评论）
            reply_to_user: 被回复的用户名（用于显示"回复 @用户名"）
        """
        with posts_lock:
            comment_record = {
                "id": len(target_post["interactions"]["comments"]) + 1,
                "user_id": user.id,
                "username": user.username,
                "avatar": user.avatar,
                "content": content,
                "timestamp": interaction_time,
                "parent_id": parent_comment_id,  # null表示一级评论，有值表示二级评论
                "reply_to": reply_to_user  # 被回复的用户名
            }
            target_post["interactions"]["comments"].append(comment_record)
            target_post["stats"]["comments"] = len(target_post["interactions"]["comments"])

    def _execute_login_session(self, user, simulation_time):
        """执行一次登录会话（新架构核心方法）
        
        模拟用户登录 -> 浏览帖子 -> 决策互动/发帖 -> 登出
        
        Args:
            user: 用户对象
            simulation_time: 当前模拟时间
        """
        # 计算登录时间
        if self.test_mode:
            simulated_hours = int(simulation_time / self.test_hour_duration)
            remaining_seconds = simulation_time % self.test_hour_duration
            simulated_minutes = int((remaining_seconds / self.test_hour_duration) * 60)
            display_hour = simulated_hours % 24
            login_time = f"{display_hour:02d}:{simulated_minutes:02d}"
        else:
            login_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. 随机决定本次登录看多少条帖子
        posts_to_view = user.get_random_posts_per_login()
        
        # 2. 获取最近N条帖子（排除自己的）
        with posts_lock:
            available_posts = [p for p in posts if p["author"]["id"] != user.id]
        
        if not available_posts:
            print(f"{user.avatar} {user.username} 在 {login_time} 登录了，但社区没有可浏览的帖子")
            return
        
        # 获取最近posts_to_view条帖子
        recent_posts = available_posts[-posts_to_view:]
        
        # 3. 为每个帖子准备候选评论
        posts_with_comments = []
        for post in recent_posts:
            top_level_comments = [c for c in post.get("interactions", {}).get("comments", []) if c.get("parent_id") is None]
            candidate_comments = []
            if top_level_comments:
                sorted_comments = sorted(top_level_comments, key=lambda c: c.get("likes_count", 0), reverse=True)
                candidate_comments = sorted_comments[:3]
            posts_with_comments.append({
                "post": post,
                "comments": candidate_comments
            })
        
        # 4. 调用AI进行批量决策
        decision = self._get_login_session_decision(user, posts_with_comments)
        
        if not decision:
            print(f"{user.avatar} {user.username} 在 {login_time} 登录了，但决策失败")
            return
        
        # 5. 执行决策
        actions_performed = []
        
        # 5.1 执行帖子互动
        post_interactions = decision.get("post_interactions", [])
        for interaction in post_interactions:
            post_id = interaction.get("post_id")
            action = interaction.get("action", "none")
            content = interaction.get("content", "").strip()
            
            # 找到对应的帖子
            target_post = next((p for p in recent_posts if p["id"] == post_id), None)
            if not target_post:
                continue
            
            if action == "like":
                self._add_like_to_post(target_post, user, login_time)
                actions_performed.append(f"赞了 {target_post['author']['name']} 的帖子")
            elif action == "comment" and content:
                self._add_comment_to_post(target_post, user, content, login_time)
                actions_performed.append(f"评论了 {target_post['author']['name']} 的帖子: {content}")
            elif action == "like_and_comment" and content:
                self._add_like_to_post(target_post, user, login_time)
                self._add_comment_to_post(target_post, user, content, login_time)
                actions_performed.append(f"赞并评论了 {target_post['author']['name']} 的帖子: {content}")
        
        # 5.2 执行评论互动
        comment_interactions = decision.get("comment_interactions", [])
        for interaction in comment_interactions:
            post_id = interaction.get("post_id")
            comment_id = interaction.get("comment_id")
            action = interaction.get("action", "none")
            content = interaction.get("content", "").strip()
            
            # 找到对应的帖子和评论
            post_data = next((pd for pd in posts_with_comments if pd["post"]["id"] == post_id), None)
            if not post_data:
                continue
            
            target_comment = next((c for c in post_data["comments"] if c["id"] == comment_id), None)
            if not target_comment:
                continue
            
            if action == "like":
                self._add_like_to_comment(post_data["post"], target_comment, user, login_time)
                actions_performed.append(f"赞了 {target_comment['username']} 的评论")
            elif action == "reply" and content:
                self._add_comment_to_post(
                    post_data["post"],
                    user,
                    content,
                    login_time,
                    parent_comment_id=target_comment["id"],
                    reply_to_user=target_comment["username"]
                )
                actions_performed.append(f"回复了 {target_comment['username']} 的评论: {content}")
            elif action == "like_and_reply" and content:
                self._add_like_to_comment(post_data["post"], target_comment, user, login_time)
                self._add_comment_to_post(
                    post_data["post"],
                    user,
                    content,
                    login_time,
                    parent_comment_id=target_comment["id"],
                    reply_to_user=target_comment["username"]
                )
                actions_performed.append(f"赞并回复了 {target_comment['username']} 的评论: {content}")
        
        # 5.3 执行发帖（如果有）
        new_post = decision.get("new_post", {})
        if new_post and new_post.get("should_post", False):
            post_content = new_post.get("content", "").strip()
            if post_content:
                self.record_post_statistics(user.id)
                
                # 创建新帖子
                with posts_lock:
                    new_post_obj = {
                        "id": len(posts) + 1,
                        "author": {
                            "id": user.id,
                            "name": user.username,
                            "avatar": user.avatar
                        },
                        "content": post_content,
                        "timestamp": login_time,
                        "interactions": {
                            "likes": [],
                            "comments": []
                        },
                        "stats": {
                            "likes": 0,
                            "comments": 0
                        }
                    }
                    posts.append(new_post_obj)
                
                actions_performed.append(f"发布了新帖子: {post_content}")
        
        # 6. 输出登录会话结果
        if actions_performed:
            actions_str = "，".join(actions_performed)
            print(f"{user.avatar} {user.username} 在 {login_time} 登录并: {actions_str}")
        else:
            print(f"{user.avatar} {user.username} 在 {login_time} 登录了，但只是浏览，没有互动")

    def _get_login_session_decision(self, user, posts_with_comments):
        """调用API获取登录会话的批量决策
        
        Args:
            user: 用户对象
            posts_with_comments: 包含帖子和评论的列表
            
        Returns:
            dict: 包含post_interactions, comment_interactions, new_post的决策字典
        """
        import requests
        import json
        
        api_url = "https://api.siliconflow.cn/v1/chat/completions"
        api_key = "sk-kookgpxohtivpdxotdnhgdgrjqidpsnhfptsmwrspjwiiukj"
        
        # 构建帖子列表文本，标记关注状态
        posts_text = ""
        for i, post_data in enumerate(posts_with_comments, 1):
            post = post_data["post"]
            comments = post_data["comments"]
            likes = len(post.get("interactions", {}).get("likes", []))
            comments_count = len(post.get("interactions", {}).get("comments", []))
            
            # 检查是否是关注的人
            is_following = post['author']['id'] in user.following
            following_tag = " 【你关注的】" if is_following else ""
            
            posts_text += f"\n\n【帖子{i}】ID:{post['id']}{following_tag}"
            posts_text += f"\n作者：{post['author']['name']}"
            posts_text += f"\n内容：{post['content']}"
            posts_text += f"\n点赞：{likes} · 评论：{comments_count}"
            
            if comments:
                posts_text += "\n热门评论："
                for j, comment in enumerate(comments, 1):
                    comment_likes = comment.get("likes_count", 0)
                    posts_text += f"\n  {j}. {comment['username']}: {comment['content']} (👍{comment_likes}) [评论ID:{comment['id']}]"
        
        # 构建关注列表文本
        following_text = ""
        if user.following:
            following_names = []
            for uid in user.following:
                # 从user_map中查找用户名
                followed_user = user_map.get(uid)
                if followed_user:
                    following_names.append(followed_user.username)
            if following_names:
                following_text = f"\n你关注的人：{', '.join(following_names)}"
        
        system_prompt = "你是一个社交平台用户，正在浏览多个帖子。请根据你的个性、互动系数和发帖系数，批量决定如何互动。你会优先关注你关注的人的动态。只输出JSON格式。"
        
        user_prompt = f"""你的个性设定：{user.comment_prompt}

你的互动系数：{user.interaction_tendency}（0.0-1.0，越高越喜欢互动）
你的发帖系数：{user.post_tendency}（0.0-1.0，越高越喜欢发帖）
{following_text}

系数参考：
- 0.0-0.3：很少互动/发帖，喜欢潜水浏览
- 0.4-0.6：偶尔互动/发帖，看心情
- 0.7-1.0：活跃互动/发帖，话痨型

你看到了以下{len(posts_with_comments)}条帖子：{posts_text}

请批量决定你的行为：

【对帖子的互动】post_interactions数组
每个元素包含：
- post_id: 帖子ID
- action: "like"(点赞) / "comment"(评论) / "like_and_comment"(点赞+评论) / "none"(跳过)
- content: 评论内容（如果action是comment或like_and_comment）

【对评论的互动】comment_interactions数组
每个元素包含：
- post_id: 所属帖子ID
- comment_id: 评论ID
- action: "like"(点赞) / "reply"(回复) / "like_and_reply"(点赞+回复) / "none"(跳过)
- content: 回复内容（如果action是reply或like_and_reply）

【是否发帖】new_post对象
- should_post: true/false（基于你的发帖系数{user.post_tendency}决定）
- content: 帖子内容（如果should_post为true）

请以JSON格式回复：
{{
    "post_interactions": [
        {{"post_id": 1, "action": "like", "content": ""}},
        {{"post_id": 2, "action": "comment", "content": "说得好！"}}
    ],
    "comment_interactions": [
        {{"post_id": 1, "comment_id": 1, "action": "reply", "content": "同意！"}}
    ],
    "new_post": {{
        "should_post": true/false,
        "content": "你的帖子内容"
    }}
}}

重要提示：
1. 根据你的互动系数{user.interaction_tendency}决定互动多少条帖子/评论
2. 根据你的发帖系数{user.post_tendency}决定是否发帖
3. 系数低的可以全部跳过，系数高的可以多互动几条
4. 标记为【你关注的】的帖子是你关注的人发的，你可能会更感兴趣，优先互动
5. 保持自然，符合你的个性设定"""
        
        payload = {
            "model": "Pro/moonshotai/Kimi-K2.5",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 800
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        try:
            response = requests.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"].strip()
            
            # 解析JSON响应
            try:
                json_start = ai_response.find("{")
                json_end = ai_response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = ai_response[json_start:json_end]
                    decision = json.loads(json_str)
                    return decision
            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {e}, 响应: {ai_response}")
                pass
            
            # 如果JSON解析失败，返回空决策
            return {
                "post_interactions": [],
                "comment_interactions": [],
                "new_post": {"should_post": False, "content": ""}
            }
            
        except Exception as e:
            print(f"登录会话决策API调用失败: {str(e)}")
            return {
                "post_interactions": [],
                "comment_interactions": [],
                "new_post": {"should_post": False, "content": ""}
            }

    def run_simulation(self):
        """运行模拟（新架构：基于登录机制）- 使用多线程避免API阻塞
        
        每个角色按泊松分布触发登录，登录后批量浏览帖子并决策互动/发帖
        """
        # 初始化每个用户的下次登录时间
        next_login_times = {}
        simulation_time = 0  # 模拟时间（秒）
        real_start_time = time.time()  # 真实开始时间
        
        # 为每个用户计算初始下次登录时间
        for user in self.users:
            # 计算登录lambda（每秒的事件率）
            if self.test_mode:
                # 测试模式：test_hour_duration秒模拟1小时
                time_scale_factor = 3600 / self.test_hour_duration
                login_lambda_per_second = user.get_hourly_login_lambda() * time_scale_factor / 3600
            else:
                # 正常模式：直接计算每秒的事件率
                login_lambda_per_second = user.get_hourly_login_lambda() / 3600
            
            # 生成首次登录时间间隔（秒），并转换为绝对时间
            login_interval = user.generate_exponential_interval(login_lambda_per_second)
            next_login_times[user.id] = simulation_time + login_interval
        
        print("\n=== 开始基于登录机制的AI社交模拟 ===\n")
        print("按Ctrl+C停止测试\n")
        
        # 使用线程池处理登录会话任务
        max_workers = min(len(self.users) * 2, 20)
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 存储正在执行的任务
                pending_futures = {}
                
                while self.running:
                    # 找到最早的下次登录时间
                    if not next_login_times:
                        break
                    
                    # 找出最早的登录事件
                    user_id = min(next_login_times, key=next_login_times.get)
                    min_time = next_login_times[user_id]
                    
                    # 计算需要等待的真实时间
                    if self.test_mode:
                        # 测试模式：min_time已经是缩放后的秒数
                        wait_time = min_time - simulation_time
                        if wait_time > 0:
                            time.sleep(wait_time)
                        simulation_time = min_time
                    else:
                        # 正常模式：min_time是真实的秒数间隔
                        current_real_time = time.time()
                        elapsed_real_time = current_real_time - real_start_time
                        wait_time = min_time - elapsed_real_time
                        if wait_time > 0:
                            time.sleep(wait_time)
                        simulation_time = min_time
                    
                    # 获取对应的用户
                    user = user_map[user_id]
                    
                    # 执行登录会话（新架构核心）
                    future = executor.submit(self._execute_login_session, user, simulation_time)
                    pending_futures[f'login_{user_id}'] = future
                    
                    # 计算下一次登录时间
                    if self.test_mode:
                        time_scale_factor = 3600 / self.test_hour_duration
                        login_lambda_per_second = user.get_hourly_login_lambda() * time_scale_factor / 3600
                    else:
                        login_lambda_per_second = user.get_hourly_login_lambda() / 3600
                    
                    interval = user.generate_exponential_interval(login_lambda_per_second)
                    next_login_times[user_id] = simulation_time + interval
                    
                    # 清理已完成的任务
                    completed_tasks = [key for key, fut in list(pending_futures.items()) if fut.done()]
                    for key in completed_tasks:
                        del pending_futures[key]
                        
        except KeyboardInterrupt:
            print("\n测试已停止")
            # 停止统计模块
            self.stop_statistics()


# 根路由 - 返回前端页面
@app.route('/')
def index():
    """返回前端页面"""
    return send_from_directory('.', 'social-platform.html')

# 静态文件服务
@app.route('/<path:filename>')
def serve_static(filename):
    """提供静态文件服务"""
    return send_from_directory('.', filename)

# API路由
@app.route('/api/posts', methods=['GET'])
def get_posts():
    """获取所有帖子"""
    return jsonify(posts)

@app.route('/api/users', methods=['GET'])
def get_users():
    """获取所有用户"""
    user_list = []
    for user in users:
        user_list.append({
            "id": user.id,
            "username": user.username,
            "avatar": user.avatar,
            "personal_signature": user.personal_signature
        })
    return jsonify(user_list)


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user_detail(user_id):
    """获取用户详细信息"""
    user = user_map.get(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    
    # 获取该用户的所有帖子
    user_posts = [p for p in posts if p["author"]["id"] == user_id]
    
    # 获取关注者列表
    followers = []
    for u in users:
        if user_id in u.following:
            followers.append({
                "id": u.id,
                "username": u.username,
                "avatar": u.avatar
            })
    
    # 获取关注列表的详细信息
    following_details = []
    for following_id in user.following:
        following_user = user_map.get(following_id)
        if following_user:
            following_details.append({
                "id": following_user.id,
                "username": following_user.username,
                "avatar": following_user.avatar
            })
    
    return jsonify({
        "id": user.id,
        "username": user.username,
        "avatar": user.avatar,
        "personal_signature": user.personal_signature,
        "posts": user_posts,
        "posts_count": len(user_posts),
        "followers": followers,
        "followers_count": len(followers),
        "following": following_details,
        "following_count": len(following_details)
    })


# 运行测试
if __name__ == "__main__":
    # 启动模拟
    scheduler = AIScheduler(users)
    
    # 在新线程中运行模拟
    simulation_thread = threading.Thread(target=scheduler.start)
    simulation_thread.daemon = True
    simulation_thread.start()
    
    # 启动Flask应用（关闭调试模式，避免重复启动模拟线程）
    # 启动Flask应用，绑定到0.0.0.0允许外部访问
    app.run(debug=False, host='0.0.0.0', port=5000)