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

    def __init__(self, user_id, username, avatar, personal_signature, post_frequency, interaction_frequency, post_prompt, comment_prompt, following=None, following_weight=0.0):
        self.id = user_id
        self.username = username
        self.avatar = avatar
        self.personal_signature = personal_signature
        self.frequency = post_frequency
        self.interaction_frequency = interaction_frequency
        self.prompt = post_prompt
        self.comment_prompt = comment_prompt
        self.following = following or []  # 关注列表（存储用户ID）
        self.following_weight = following_weight  # 关注权重（互动概率提升幅度）

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

    def get_daily_frequency(self):
        """计算每日平均发帖频率"""
        return self.frequency / 30  # 假设每月30天

    def get_hourly_lambda(self):
        """计算每小时的泊松分布参数λ"""
        daily_freq = self.get_daily_frequency()
        return daily_freq / 24  # 每小时的平均发帖数

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

    def get_daily_interaction_frequency(self):
        """计算每日平均互动频率"""
        return self.interaction_frequency / 30  # 假设每月30天

    def get_hourly_interaction_lambda(self):
        """计算每小时的互动泊松分布参数λ"""
        daily_freq = self.get_daily_interaction_frequency()
        return daily_freq / 24  # 每小时的平均互动数


# 导入用户信息
users = []
with open("ai_users_config.json", "r", encoding= "UTF-8") as USER_CONFIG:
    config = json.load(USER_CONFIG)
    for user in config["ai_users"]:
        users.append(User(
            user["id"],
            user["username"],
            user["avatar"],
            user["personal_signture"],
            user["post_frequency"],
            user["interaction_frequency"],
            user["post_prompt"],
            user["comment_prompt"],
            user.get("following", []),
            user.get("following_weight", 0.0))
        )

# 存储帖子数据
posts = []

# 帖子数据的线程锁，用于保护多线程环境下的帖子操作
posts_lock = threading.Lock()

# 存储用户对象映射（用于快速查找）
user_map = {user.id: user for user in users}


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
            daily_freq = user.get_daily_frequency()
            hourly_lambda = user.get_hourly_lambda()  # 每小时泊松分布参数λ
            # 计算每小时发帖0次、1次、2次的概率
            p0 = user.poisson_probability(0, hourly_lambda)
            p1 = user.poisson_probability(1, hourly_lambda)
            p2 = user.poisson_probability(2, hourly_lambda)
            print(f"{user.avatar} {user.username} - 每月发帖: {user.frequency}帖 - 每日平均: {daily_freq:.2f}帖 - 每小时λ: {hourly_lambda:.4f} - P(0): {p0:.4f}, P(1): {p1:.4f}, P(2+): {1-p0-p1:.4f}")
        
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
    
    def _execute_post_poisson(self, user, simulation_time):
        """执行基于泊松过程的发帖操作"""
        # 计算显示的发帖时间（基于执行发帖操作时的系统时间，而非API返回时间）
        if self.test_mode:
            # 测试模式：test_hour_duration秒模拟1小时
            # 计算模拟的小时数和分钟数
            simulated_hours = int(simulation_time / self.test_hour_duration)
            remaining_seconds = simulation_time % self.test_hour_duration
            simulated_minutes = int((remaining_seconds / self.test_hour_duration) * 60)
            display_hour = simulated_hours % 24  # 小时部分模24，超过23时归零
            post_time = f"{display_hour:02d}:{simulated_minutes:02d}"
        else:
            # 正常模式：使用执行发帖操作时的实际系统时间
            post_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 在API调用前记录统计（避免API延迟影响统计准确性）
        self.record_post_statistics(user.id)
        
        # 生成帖子内容
        content = user.post()
        # 输出发帖信息（显示的是执行发帖操作时的时间，而非API返回时间）
        print(f"{user.avatar} {user.username} 在 {post_time} 发帖: {content}")
        
        # 存储帖子到全局posts列表
        global posts
        post_id = len(posts) + 1
        post = {
            "id": post_id,
            "author": {
                        "id": user.id,
                        "name": user.username,
                        "avatar": user.avatar,
                        "personal_signature": user.personal_signature
                    },
            "content": content,
            "timestamp": post_time,
            "stats": {
                "likes": 0,
                "comments": 0,
                "shares": 0
            },
            "interactions": {
                "likes": [],  # 点赞列表，存储点赞用户的信息
                "comments": []  # 评论列表，存储评论详情
            }
        }
        posts.append(post)

    def _check_and_trigger_interaction(self, user, simulation_time, executor, pending_futures):
        """检查并触发互动操作
        
        Args:
            user: 当前用户对象
            simulation_time: 当前模拟时间
            executor: 线程池执行器
            pending_futures: 待处理任务字典
        """
        # 计算互动概率（使用泊松分布）
        if self.test_mode:
            # 测试模式：test_hour_duration秒模拟1小时
            time_scale_factor = 3600 / self.test_hour_duration
            lambda_per_second = user.get_hourly_interaction_lambda() * time_scale_factor / 3600
        else:
            # 正常模式
            lambda_per_second = user.get_hourly_interaction_lambda() / 3600
        
        # 生成指数分布的时间间隔，判断是否触发互动
        interval = user.generate_exponential_interval(lambda_per_second)
        
        # 如果生成的间隔很小（在合理范围内），则触发互动
        # 这里使用一个阈值来判断是否触发，可以根据需要调整
        threshold = 3600 if not self.test_mode else self.test_hour_duration  # 正常模式1小时，测试模式使用配置的缩放
        
        if interval < threshold and len(posts) > 0:
            # 获取最新的一条帖子进行互动
            target_post = posts[-1]
            
            # 避免用户对自己的帖子互动
            if target_post["author"]["id"] != user.id:
                # 提交互动任务到线程池
                future = executor.submit(self._execute_interaction, user, target_post, simulation_time)
                pending_futures[f"interaction_{user.id}_{simulation_time}"] = future

    def _execute_interaction(self, user, target_post, simulation_time):
        """执行互动操作（点赞、评论或点赞并评论）
        
        Args:
            user: 互动用户对象
            target_post: 目标帖子
            simulation_time: 当前模拟时间
        """
        # 计算互动时间
        if self.test_mode:
            simulated_hours = int(simulation_time / self.test_hour_duration)
            remaining_seconds = simulation_time % self.test_hour_duration
            simulated_minutes = int((remaining_seconds / self.test_hour_duration) * 60)
            display_hour = simulated_hours % 24
            interaction_time = f"{display_hour:02d}:{simulated_minutes:02d}"
        else:
            interaction_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 调用API进行互动决策
        decision = self._get_interaction_decision(user, target_post)
        
        # 获取帖子作者名称
        author_name = target_post.get('author', {}).get('name', '未知用户')
        
        if decision:
            action = decision.get("action", "none")
            comment_content = decision.get("content", "")
            
            # 执行相应的互动操作
            if action == "like":
                self._add_like_to_post(target_post, user, interaction_time)
                print(f"{user.avatar} {user.username} 在 {interaction_time} 赞了 {author_name} 的帖子")
                
            elif action == "comment":
                self._add_comment_to_post(target_post, user, comment_content, interaction_time)
                print(f"{user.avatar} {user.username} 在 {interaction_time} 评论了 {author_name} 的帖子: {comment_content}")
                
            elif action == "like_and_comment":
                self._add_like_to_post(target_post, user, interaction_time)
                self._add_comment_to_post(target_post, user, comment_content, interaction_time)
                print(f"{user.avatar} {user.username} 在 {interaction_time} 赞并评论了 {author_name} 的帖子: {comment_content}")
                
            elif action == "none" or action == "":
                # 不执行任何互动，但打印浏览记录
                print(f"{user.avatar} {user.username} 在 {interaction_time} 看到了 {author_name} 的帖子，但不做任何互动")

    def _execute_interaction_event(self, user, simulation_time):
        """执行独立的互动事件
        
        与发帖独立的互动时间线，当触发时随机选择一条帖子进行互动
        支持关注机制：被关注者的帖子有更高概率被选中
        
        Args:
            user: 互动用户对象
            simulation_time: 当前模拟时间
        """
        # 计算互动时间
        if self.test_mode:
            simulated_hours = int(simulation_time / self.test_hour_duration)
            remaining_seconds = simulation_time % self.test_hour_duration
            simulated_minutes = int((remaining_seconds / self.test_hour_duration) * 60)
            display_hour = simulated_hours % 24
            interaction_time = f"{display_hour:02d}:{simulated_minutes:02d}"
        else:
            interaction_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 随机选择一条帖子进行互动（排除自己的帖子）
        with posts_lock:
            available_posts = [p for p in posts if p["author"]["id"] != user.id]
            
        if not available_posts:
            print(f"{user.avatar} {user.username} 在 {interaction_time} 浏览了社区，但没有可互动的帖子")
            return
        
        # 从最近10条帖子中选择，支持关注权重
        recent_posts = available_posts[-10:]
        
        if user.following and user.following_weight > 0:
            # 使用加权随机选择
            weights = []
            for post in recent_posts:
                author_id = post["author"]["id"]
                if author_id in user.following:
                    # 被关注者的帖子权重提升
                    weights.append(1.0 + user.following_weight)
                else:
                    weights.append(1.0)
            
            # 加权随机选择
            import random
            target_post = random.choices(recent_posts, weights=weights, k=1)[0]
        else:
            # 普通随机选择
            import random
            target_post = random.choice(recent_posts)
        
        # 调用原有的互动执行逻辑
        self._execute_interaction(user, target_post, simulation_time)

    def _get_interaction_decision(self, user, target_post):
        """调用API获取互动决策
        
        Args:
            user: 用户对象
            target_post: 目标帖子
            
        Returns:
            dict: 包含action和content的决策字典
        """
        import requests
        
        api_url = "https://api.siliconflow.cn/v1/chat/completions"
        api_key = "sk-kookgpxohtivpdxotdnhgdgrjqidpsnhfptsmwrspjwiiukj"
        
        system_prompt = "你是一个社交平台用户，正在浏览帖子并决定是否互动。请根据你的个性和帖子内容，做出互动决策。只输出JSON格式。"
        user_prompt = f"""你的个性设定：{user.comment_prompt}

帖子作者：{target_post['author']['name']}
帖子内容：{target_post['content']}

请决定你的互动行为，从以下选项中选择：
1. like - 仅点赞
2. comment - 仅评论
3. like_and_comment - 点赞并评论
4. none - 不互动

请以JSON格式回复，格式如下：
{{"action": "like|comment|like_and_comment|none", "content": "评论内容（如果不需要评论则为空）"}}"""
        
        payload = {
            "model": "Pro/moonshotai/Kimi-K2.5",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 150
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
            import json
            # 尝试提取JSON部分（模型可能会返回额外的文本）
            try:
                # 查找JSON开始和结束的位置
                json_start = ai_response.find("{")
                json_end = ai_response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = ai_response[json_start:json_end]
                    decision = json.loads(json_str)
                    return decision
            except json.JSONDecodeError:
                pass
            
            # 如果JSON解析失败，根据关键词判断
            action = "none"
            content = ""
            
            if "like_and_comment" in ai_response.lower() or ("点赞" in ai_response and "评论" in ai_response):
                action = "like_and_comment"
                # 尝试提取评论内容
                lines = ai_response.split("\n")
                for line in lines:
                    if "content" in line.lower() or "评论" in line:
                        content = line.split(":")[-1].strip().strip('"').strip("'}")
                        break
            elif "comment" in ai_response.lower() or "评论" in ai_response:
                action = "comment"
                lines = ai_response.split("\n")
                for line in lines:
                    if "content" in line.lower() or "评论" in line:
                        content = line.split(":")[-1].strip().strip('"').strip("'}")
                        break
            elif "like" in ai_response.lower() or "点赞" in ai_response:
                action = "like"
            
            return {"action": action, "content": content}
            
        except Exception as e:
            print(f"互动决策API调用失败: {str(e)}")
            return {"action": "none", "content": ""}

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

    def _add_comment_to_post(self, target_post, user, content, interaction_time):
        """为帖子添加评论
        
        Args:
            target_post: 目标帖子
            user: 评论用户
            content: 评论内容
            interaction_time: 互动时间
        """
        with posts_lock:
            comment_record = {
                "user_id": user.id,
                "username": user.username,
                "avatar": user.avatar,
                "content": content,
                "timestamp": interaction_time
            }
            target_post["interactions"]["comments"].append(comment_record)
            target_post["stats"]["comments"] = len(target_post["interactions"]["comments"])

    def run_simulation(self):
        """运行模拟（基于泊松过程）- 使用多线程避免API阻塞
        
        同时调度发帖和互动事件，两者有独立的时间线
        """
        # 初始化每个用户的下次发帖时间和下次互动时间
        next_post_times = {}
        next_interaction_times = {}
        simulation_time = 0  # 模拟时间（秒）
        real_start_time = time.time()  # 真实开始时间
        
        # 为每个用户计算初始下次发帖时间和下次互动时间
        for user in self.users:
            # 计算发帖lambda（每秒的事件率）
            if self.test_mode:
                # 测试模式：test_hour_duration秒模拟1小时
                # 时间缩放因子：3600秒真实时间 / test_hour_duration秒模拟时间
                time_scale_factor = 3600 / self.test_hour_duration
                # 每小时lambda * 时间缩放因子 = 测试模式下每"模拟小时"的事件数
                # 再除以3600转换为每秒的事件率
                post_lambda_per_second = user.get_hourly_lambda() * time_scale_factor / 3600
                interaction_lambda_per_second = user.get_hourly_interaction_lambda() * time_scale_factor / 3600
            else:
                # 正常模式：直接计算每秒的事件率
                # 每小时lambda / 3600秒 = 每秒的事件率
                post_lambda_per_second = user.get_hourly_lambda() / 3600
                interaction_lambda_per_second = user.get_hourly_interaction_lambda() / 3600
            
            # 生成首次发帖时间间隔（秒），并转换为绝对时间
            post_interval = user.generate_exponential_interval(post_lambda_per_second)
            next_post_times[user.id] = simulation_time + post_interval
            
            # 生成首次互动时间间隔（秒），并转换为绝对时间
            interaction_interval = user.generate_exponential_interval(interaction_lambda_per_second)
            next_interaction_times[user.id] = simulation_time + interaction_interval
        
        print("\n=== 开始基于泊松过程的随机发帖和互动 ===\n")
        print("按Ctrl+C停止测试\n")
        
        # 使用线程池处理发帖和互动任务
        max_workers = min(len(self.users) * 3, 30)  # 增加线程数以处理更多并发
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 存储正在执行的任务
                pending_futures = {}
                
                while self.running:
                    # 找到最早的下次事件时间（发帖或互动）
                    all_next_times = {}
                    
                    # 添加发帖时间
                    for user_id, next_time in next_post_times.items():
                        all_next_times[('post', user_id)] = next_time
                    
                    # 添加互动时间
                    for user_id, next_time in next_interaction_times.items():
                        all_next_times[('interaction', user_id)] = next_time
                    
                    if not all_next_times:
                        break
                    
                    # 找出最早的事件
                    min_event = min(all_next_times, key=all_next_times.get)
                    min_time = all_next_times[min_event]
                    event_type, user_id = min_event
                    
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
                    
                    if event_type == 'post':
                        # 执行发帖
                        future = executor.submit(self._execute_post_poisson, user, simulation_time)
                        pending_futures[f'post_{user_id}'] = future
                        
                        # 计算下一次发帖时间
                        if self.test_mode:
                            time_scale_factor = 3600 / self.test_hour_duration
                            post_lambda_per_second = user.get_hourly_lambda() * time_scale_factor / 3600
                        else:
                            post_lambda_per_second = user.get_hourly_lambda() / 3600
                        
                        interval = user.generate_exponential_interval(post_lambda_per_second)
                        next_post_times[user_id] = simulation_time + interval
                        
                    elif event_type == 'interaction':
                        # 执行互动
                        if len(posts) > 0:  # 确保有帖子可以互动
                            future = executor.submit(self._execute_interaction_event, user, simulation_time)
                            pending_futures[f'interaction_{user_id}'] = future
                        
                        # 计算下一次互动时间
                        if self.test_mode:
                            time_scale_factor = 3600 / self.test_hour_duration
                            interaction_lambda_per_second = user.get_hourly_interaction_lambda() * time_scale_factor / 3600
                        else:
                            interaction_lambda_per_second = user.get_hourly_interaction_lambda() / 3600
                        
                        interval = user.generate_exponential_interval(interaction_lambda_per_second)
                        next_interaction_times[user_id] = simulation_time + interval
                    
                    # 清理已完成的任务
                    completed_tasks = [key for key, fut in pending_futures.items() if fut.done()]
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