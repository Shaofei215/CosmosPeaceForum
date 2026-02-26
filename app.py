import random
import json
import time
import threading
import math
import os
import sys
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 启用CORS，允许前端访问

# 日志存储
logs = []
logs_lock = threading.Lock()
max_logs = 500  # 最多保存500条日志

# 自定义输出流，用于捕获print输出
class LogCapture(StringIO):
    def write(self, text):
        if text.strip():
            timestamp = time.strftime('%H:%M:%S')
            with logs_lock:
                logs.append({
                    'timestamp': timestamp,
                    'content': text.rstrip('\n')
                })
                # 保持日志数量在限制内
                if len(logs) > max_logs:
                    logs.pop(0)
        # 同时输出到原stdout
        return original_stdout.write(text)

# 保存原始stdout并替换
original_stdout = sys.stdout
sys.stdout = LogCapture()

# 创建用户类
class User(object):

    def __init__(self, user_id, username, avatar, personal_signature, 
                 monthly_logins, posts_per_login_min, posts_per_login_max,
                 interaction_tendency, post_tendency,
                 personality_prompt, following=None):
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
        
        self.personality_prompt = personality_prompt  # 角色个性描述
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
            user["personality_prompt"],
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
    
    now = time.time()
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
            "timestamp": time.strftime("%H:%M"),
            "full_timestamp": now,
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
            "timestamp": time.strftime("%H:%M"),
            "full_timestamp": now - 60,
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
            "timestamp": time.strftime("%H:%M"),
            "full_timestamp": now - 120,
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
    test_hour_duration = 30  # 测试模式下每小时的持续时间（秒），可自由调节
    
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
        # 热度计算相关属性
        self.hot_posts = []  # 按热度排序的帖子列表（热度从高到低）
        self.hot_posts_lock = threading.Lock()  # 热度列表的线程锁
        self.hot_calculation_thread = None  # 热度计算线程
        self.hot_calculation_running = True
        self.hot_calculation_interval = 900  # 每15分钟计算一次（秒）
    
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
    
    def calculate_post_hotness(self, post, current_time):
        """计算单个帖子的热度值
        
        公式：热度值 = (点赞数 + 2*评论数 + 3*转发数) * 时间衰减系数
        
        Args:
            post: 帖子对象
            current_time: 当前时间戳
            
        Returns:
            float: 热度值
        """
        # 获取互动数据
        likes = len(post.get("interactions", {}).get("likes", []))
        comments = len(post.get("interactions", {}).get("comments", []))
        shares = post.get("stats", {}).get("shares", 0)
        
        # 基础热度分
        base_score = likes + 2 * comments + 3 * shares
        
        # 计算帖子年龄（小时）
        post_time_str = post.get("timestamp", "")
        try:
            # 尝试解析时间戳
            if ":" in post_time_str:
                # 格式可能是 "HH:MM" 或 "YYYY-MM-DD HH:MM:SS"
                if len(post_time_str) <= 5:  # "HH:MM"
                    # 假设是同一天
                    post_time = time.mktime(time.strptime(f"{time.strftime('%Y-%m-%d')} {post_time_str}", "%Y-%m-%d %H:%M"))
                else:
                    post_time = time.mktime(time.strptime(post_time_str, "%Y-%m-%d %H:%M:%S"))
            else:
                post_time = current_time
        except:
            post_time = current_time
        
        # 计算帖子年龄（小时）
        age_hours = max(0, (current_time - post_time) / 3600)
        
        # 时间衰减系数：使用指数衰减，半衰期24小时
        # 衰减公式：e^(-ln(2) * age / half_life)
        half_life = 24  # 半衰期24小时
        time_decay = math.exp(-math.log(2) * age_hours / half_life)
        
        # 最终热度值
        hotness = base_score * time_decay
        
        return hotness
    
    def update_hot_posts(self):
        """更新热度排序的帖子列表
        
        每15分钟调用一次，计算所有帖子的热度并排序
        """
        with posts_lock:
            if not posts:
                with self.hot_posts_lock:
                    self.hot_posts = []
                return
            
            current_time = time.time()
            posts_with_hotness = []
            
            for post in posts:
                hotness = self.calculate_post_hotness(post, current_time)
                posts_with_hotness.append({
                    "post": post,
                    "hotness": hotness
                })
                # 将热度值保存到帖子中
                post["hotness"] = hotness
            
            # 按热度从高到低排序
            posts_with_hotness.sort(key=lambda x: x["hotness"], reverse=True)
            
            with self.hot_posts_lock:
                self.hot_posts = posts_with_hotness
            
            # 打印热度最高的5条帖子
            print(f"\n🔥 热度排行榜（{time.strftime('%H:%M:%S')}）:")
            for i, item in enumerate(posts_with_hotness[:5], 1):
                post = item["post"]
                print(f"  {i}. {post['author']['name']}: {item['hotness']:.2f}分 - {post['content'][:30]}...")
            print()
    
    def start_hot_calculation_timer(self):
        """启动热度计算定时器"""
        def timer_task():
            while self.hot_calculation_running:
                # 计算热度
                self.update_hot_posts()
                
                # 等待15分钟
                time.sleep(self.hot_calculation_interval)
        
        # 在新线程中运行定时器
        self.hot_calculation_thread = threading.Thread(target=timer_task)
        self.hot_calculation_thread.daemon = True
        self.hot_calculation_thread.start()
        print(f"✅ 热度计算定时器已启动（每{self.hot_calculation_interval/60:.0f}分钟计算一次）")
    
    def stop_hot_calculation(self):
        """停止热度计算模块"""
        self.hot_calculation_running = False
        if self.hot_calculation_thread:
            self.hot_calculation_thread.join(timeout=1.0)
    
    def get_recommended_posts(self, count, exclude_user_id=None):
        """获取推荐帖子
        
        算法：70%高热度帖子 + 30%新帖子，打乱顺序
        
        Args:
            count: 需要的帖子数量
            exclude_user_id: 排除的用户ID（排除自己的帖子）
            
        Returns:
            list: 推荐的帖子列表
        """
        with posts_lock:
            if not posts:
                return []
            
            # 复制帖子列表
            all_posts = list(posts)
            
            # 排除自己的帖子
            if exclude_user_id:
                all_posts = [p for p in all_posts if p["author"]["id"] != exclude_user_id]
            
            if not all_posts:
                return []
            
            # 确保所有帖子都有热度值
            for post in all_posts:
                if "hotness" not in post:
                    post["hotness"] = 0
            
            # 按热度排序（从高到低）
            sorted_by_hot = sorted(all_posts, key=lambda x: x["hotness"], reverse=True)
            
            # 按时间排序（从新到旧）
            sorted_by_time = sorted(all_posts, key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # 计算需要的高热度和新帖子数量
            hot_count = max(1, int(count * 0.7))
            new_count = max(1, count - hot_count)
            
            # 去重选择
            selected_hot = []
            selected_new = []
            used_ids = set()
            
            # 选择高热度帖子
            for post in sorted_by_hot:
                if len(selected_hot) >= hot_count:
                    break
                if post["id"] not in used_ids:
                    selected_hot.append(post)
                    used_ids.add(post["id"])
            
            # 选择新帖子
            for post in sorted_by_time:
                if len(selected_new) >= new_count:
                    break
                if post["id"] not in used_ids:
                    selected_new.append(post)
                    used_ids.add(post["id"])
            
            # 合并并打乱顺序
            selected = selected_hot + selected_new
            random.shuffle(selected)
            
            # 截取需要的数量
            return selected[:count]
    
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
        
        # 启动热度计算定时器
        self.start_hot_calculation_timer()
        
        # 启动模拟
        try:
            self.run_simulation()
        except KeyboardInterrupt:
            print("\n测试已停止")
            # 停止统计模块
            self.stop_statistics()
            # 停止热度计算模块
            self.stop_hot_calculation()
    
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
            # 确保parent_comment_id是数字或None
            if parent_comment_id is not None:
                parent_comment_id = int(parent_comment_id)
            
            comment_id = len(target_post["interactions"]["comments"]) + 1
            comment_record = {
                "id": comment_id,
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

    def _add_repost(self, original_post, user, repost_content, interaction_time, original_comment=None):
        """转发帖子或评论（创建新帖子并引用）
        
        Args:
            original_post: 原帖对象
            user: 转发用户
            repost_content: 转发语（可以为空）
            interaction_time: 互动时间
            original_comment: 原评论对象（如果是转发评论）
        """
        with posts_lock:
            # 如果是转发评论，只更新评论的转发数
            if original_comment:
                if "shares" not in original_comment:
                    original_comment["shares"] = 0
                original_comment["shares"] += 1
            # 如果是转发帖子，更新原帖的转发数
            else:
                if "shares" not in original_post["stats"]:
                    original_post["stats"]["shares"] = 0
                original_post["stats"]["shares"] += 1
            
            # 构建转发链
            repost_chain = []
            
            # 如果原帖本身就是转发，先把之前的转发链加进来
            if original_post.get("is_repost") and original_post.get("repost_chain"):
                repost_chain.extend(original_post["repost_chain"])
            
            # 添加当前转发者到转发链
            repost_chain.append({
                "user_id": user.id,
                "username": user.username,
                "avatar": user.avatar,
                "content": repost_content,
                "timestamp": interaction_time
            })
            
            # 找到原始源（最原始的帖子）- 带循环检测
            def find_root_post(post, visited_ids=None):
                """递归查找最原始的帖子（带循环检测）"""
                if visited_ids is None:
                    visited_ids = set()
                post_id = int(post["id"])
                if post_id in visited_ids:
                    return post
                visited_ids.add(post_id)
                if post.get("is_repost") and post.get("repost"):
                    original_id = int(post["repost"]["original_post_id"])
                    for p in posts:
                        if int(p["id"]) == original_id:
                            return find_root_post(p, visited_ids)
                return post
            
            root_post = find_root_post(original_post)
            
            # 创建新的转发帖子
            new_post_obj = {
                "id": len(posts) + 1,
                "author": {
                    "id": user.id,
                    "name": user.username,
                    "avatar": user.avatar,
                    "personal_signature": user.personal_signature
                },
                "content": repost_content,
                "timestamp": interaction_time,
                "full_timestamp": time.time(),
                "interactions": {
                    "likes": [],
                    "comments": []
                },
                "stats": {
                    "likes": 0,
                    "comments": 0,
                    "shares": 0
                },
                "is_repost": True,
                "repost": {
                    "original_post_id": int(root_post["id"]),
                    "original_author": root_post["author"],
                    "original_content": root_post["content"],
                    "original_timestamp": root_post.get("timestamp", "")
                },
                "repost_chain": repost_chain
            }
            
            # 如果是转发评论，添加评论信息
            if original_comment:
                new_post_obj["repost_comment"] = {
                    "comment_id": int(original_comment["id"]),
                    "comment_user_id": int(original_comment["user_id"]),
                    "comment_username": original_comment["username"],
                    "comment_avatar": original_comment["avatar"],
                    "comment_content": original_comment["content"],
                    "comment_timestamp": original_comment.get("timestamp", "")
                }
            
            posts.append(new_post_obj)
            return new_post_obj

    def _get_delayed_time(self, base_time, delay_seconds):
        """根据基础时间和延迟秒数计算新的时间字符串（格式：hh:mm）
        
        Args:
            base_time: 基础时间字符串（格式：hh:mm 或 YYYY-MM-DD hh:mm:ss）
            delay_seconds: 延迟秒数
            
        Returns:
            str: 延迟后的时间字符串（格式：hh:mm）
        """
        import datetime
        
        # 解析基础时间
        if len(base_time) == 5 and ':' in base_time:  # hh:mm 格式
            today = datetime.datetime.now()
            base_dt = today.replace(hour=int(base_time[:2]), minute=int(base_time[3:5]), second=0, microsecond=0)
        elif len(base_time) > 10:  # YYYY-MM-DD hh:mm:ss 格式
            base_dt = datetime.datetime.strptime(base_time, "%Y-%m-%d %H:%M:%S")
        else:
            # 默认使用当前时间
            base_dt = datetime.datetime.now()
        
        # 添加延迟
        delayed_dt = base_dt + datetime.timedelta(seconds=delay_seconds)
        
        # 返回 hh:mm 格式
        return delayed_dt.strftime("%H:%M")

    def _execute_login_session(self, user, simulation_time):
        """执行一次登录会话（新架构核心方法）
        
        模拟用户登录 -> 浏览帖子 -> 决策互动/发帖 -> 登出
        
        Args:
            user: 用户对象
            simulation_time: 当前模拟时间
        """
        # 计算登录时间（格式：hh:mm）
        if self.test_mode:
            simulated_hours = int(simulation_time / self.test_hour_duration)
            remaining_seconds = simulation_time % self.test_hour_duration
            simulated_minutes = int((remaining_seconds / self.test_hour_duration) * 60)
            display_hour = simulated_hours % 24
            login_time = f"{display_hour:02d}:{simulated_minutes:02d}"
        else:
            login_time = time.strftime("%H:%M")
        
        # 1. 随机决定本次登录看多少条帖子
        posts_to_view = user.get_random_posts_per_login()
        
        # 2. 获取推荐帖子（70%高热度 + 30%新帖子，排除自己的）
        recent_posts = self.get_recommended_posts(posts_to_view, exclude_user_id=user.id)
        
        if not recent_posts:
            print(f"{user.avatar} {user.username} 在 {login_time} 登录了，但社区没有可浏览的帖子")
            return
        
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
        current_delay = 0  # 累计延迟（秒）
        
        # 5.1 执行帖子互动
        post_interactions = decision.get("post_interactions", [])
        for interaction in post_interactions:
            # 为每个操作添加随机延迟（10-300秒）
            delay = random.randint(10, 300)
            current_delay += delay
            interaction_time = self._get_delayed_time(login_time, current_delay)
            
            post_id = interaction.get("post_id")
            action = interaction.get("action", "none")
            content = interaction.get("content", "").strip()
            
            # 找到对应的帖子
            target_post = next((p for p in recent_posts if p["id"] == post_id), None)
            if not target_post:
                continue
            
            if action == "like":
                self._add_like_to_post(target_post, user, interaction_time)
                actions_performed.append(f"赞了 {target_post['author']['name']} 的帖子")
            elif action == "comment" and content:
                self._add_comment_to_post(target_post, user, content, interaction_time)
                actions_performed.append(f"评论了 {target_post['author']['name']} 的帖子: {content}")
            elif action == "like_and_comment" and content:
                self._add_like_to_post(target_post, user, interaction_time)
                self._add_comment_to_post(target_post, user, content, interaction_time)
                actions_performed.append(f"赞并评论了 {target_post['author']['name']} 的帖子: {content}")
            elif action == "repost":
                self._add_repost(target_post, user, "", interaction_time)
                actions_performed.append(f"转发了 {target_post['author']['name']} 的帖子")
            elif action == "repost_with_comment":
                self._add_repost(target_post, user, content, interaction_time)
                actions_performed.append(f"转发了 {target_post['author']['name']} 的帖子并说: {content}")
        
        # 5.2 执行评论互动
        comment_interactions = decision.get("comment_interactions", [])
        for interaction in comment_interactions:
            # 为每个操作添加随机延迟（10-300秒）
            delay = random.randint(10, 300)
            current_delay += delay
            interaction_time = self._get_delayed_time(login_time, current_delay)
            
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
                self._add_like_to_comment(post_data["post"], target_comment, user, interaction_time)
                actions_performed.append(f"赞了 {target_comment['username']} 的评论")
            elif action == "reply" and content:
                self._add_comment_to_post(
                    post_data["post"],
                    user,
                    content,
                    interaction_time,
                    parent_comment_id=int(target_comment["id"]),
                    reply_to_user=target_comment["username"]
                )
                actions_performed.append(f"回复了 {target_comment['username']} 的评论: {content}")
            elif action == "like_and_reply" and content:
                self._add_like_to_comment(post_data["post"], target_comment, user, interaction_time)
                self._add_comment_to_post(
                    post_data["post"],
                    user,
                    content,
                    interaction_time,
                    parent_comment_id=int(target_comment["id"]),
                    reply_to_user=target_comment["username"]
                )
                actions_performed.append(f"赞并回复了 {target_comment['username']} 的评论: {content}")
            elif action == "repost_comment":
                self._add_repost(post_data["post"], user, "", interaction_time, target_comment)
                actions_performed.append(f"转发了 {target_comment['username']} 的评论")
            elif action == "repost_comment_with_reply" and content:
                self._add_repost(post_data["post"], user, content, interaction_time, target_comment)
                actions_performed.append(f"转发了 {target_comment['username']} 的评论并说: {content}")
        
        # 5.3 执行发帖（如果有）
        new_post = decision.get("new_post", {})
        if new_post and new_post.get("should_post", False):
            post_content = new_post.get("content", "").strip()
            if post_content:
                # 发帖也添加延迟
                delay = random.randint(10, 300)
                current_delay += delay
                post_time = self._get_delayed_time(login_time, current_delay)
                
                self.record_post_statistics(user.id)
                
                # 创建新帖子
                with posts_lock:
                    new_post_obj = {
                        "id": len(posts) + 1,
                        "author": {
                            "id": user.id,
                            "name": user.username,
                            "avatar": user.avatar,
                            "personal_signature": user.personal_signature
                        },
                        "content": post_content,
                        "timestamp": post_time,
                        "full_timestamp": time.time(),
                        "interactions": {
                            "likes": [],
                            "comments": []
                        },
                        "stats": {
                            "likes": 0,
                            "comments": 0,
                            "shares": 0
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
            reposts = post.get("stats", {}).get("shares", 0)
            
            # 检查是否是关注的人
            is_following = post['author']['id'] in user.following
            following_tag = " 【你关注的】" if is_following else ""
            
            posts_text += f"\n\n【帖子{i}】ID:{post['id']}{following_tag}"
            posts_text += f"\n作者：{post['author']['name']}"
            posts_text += f"\n内容：{post['content']}"
            posts_text += f"\n点赞：{likes} · 评论：{comments_count} · 转发：{reposts}"
            
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
        
        system_prompt = "你是一个社交平台用户，正在浏览多个帖子。请根据你的个性、互动系数和发帖系数，批量决定如何互动。你会优先关注你关注的人的动态。**非常重要：严格使用提供的帖子ID和评论ID，不要混淆！**只输出JSON格式。"
        
        user_prompt = f"""你的个性设定：{user.personality_prompt}

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
- action: "like"(点赞) / "comment"(评论) / "like_and_comment"(点赞+评论) / "repost"(转发) / "repost_with_comment"(转发+评论) / "none"(跳过)
- content: 评论或转发语内容（如果action是comment/like_and_comment/repost_with_comment，50字以下为宜）

【对评论的互动】comment_interactions数组
每个元素包含：
- post_id: 所属帖子ID
- comment_id: 评论ID
- action: "like"(点赞) / "reply"(回复) / "like_and_reply"(点赞+回复) / "repost_comment"(转发评论) / "repost_comment_with_reply"(转发评论并附评论) / "none"(跳过)
- content: 回复或转发语内容（如果action是reply/like_and_reply/repost_comment_with_reply，50字以下字为宜）

【是否发帖】new_post对象
- should_post: true/false（基于你的发帖系数{user.post_tendency}决定）
- content: 帖子内容（如果should_post为true，100字以下为宜）

请以JSON格式回复：
{{
    "post_interactions": [
        {{"post_id": 帖子1的真实ID, "action": "like", "content": ""}},
        {{"post_id": 帖子2的真实ID, "action": "comment", "content": "说得好！"}}
    ],
    "comment_interactions": [
        {{"post_id": 对应帖子的真实ID, "comment_id": 评论的真实ID, "action": "reply", "content": "同意！"}}
    ],
    "new_post": {{
        "should_post": true/false,
        "content": "你的帖子内容"
    }}
}}

重要提示：
1. **ID准确性重要！** 请严格使用提供的帖子ID和评论ID，不要混淆
2. 根据你的互动系数{user.interaction_tendency}决定互动多少条帖子/评论
3. 根据你的发帖系数{user.post_tendency}决定是否发帖
4. 系数低的可以全部跳过，系数高的可以多互动几条
5. 标记为【你关注的】的帖子是你关注的人发的，你可能会更感兴趣，优先互动
6. 保持自然，符合你的个性设定
7. 注意字数限制：评论宜50字以下，回复宜50字以下，帖子宜100字以下
8. 互动行为优先级：点赞 > 评论/回复 > 转发。即：
   - 优先选择点赞，点赞是最常见的互动方式
   - 其次是评论或回复，频率低于点赞
   - 转发在想要扩散给他人时才使用"""
        
        payload = {
            "model": "Pro/MiniMaxAI/MiniMax-M2.5",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 1.0,
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
                print(f"JSON解析失败，尝试自动补全...")
                # 尝试自动补全JSON
                fixed_json = self._fix_truncated_json(ai_response)
                if fixed_json:
                    try:
                        decision = json.loads(fixed_json)
                        print(f"JSON自动补全成功")
                        return decision
                    except:
                        pass
                print(f"JSON解析失败: {e}, 响应: {ai_response[:200]}...")
                pass
            
            # 如果JSON解析失败，返回空决策
            return {
                "post_interactions": [],
                "comment_interactions": [],
                "new_post": {"should_post": False, "content": ""}
            }
            
        except Exception as e:
            print(f"API调用失败: {str(e)}")
            return {
                "post_interactions": [],
                "comment_interactions": [],
                "new_post": {"should_post": False, "content": ""}
            }

    def _fix_truncated_json(self, json_str):
        """尝试修复被截断的JSON字符串
        
        Args:
            json_str: 可能被截断的JSON字符串
            
        Returns:
            str: 修复后的JSON字符串，如果无法修复则返回None
        """
        # 找到JSON开始的位置
        start = json_str.find("{")
        if start == -1:
            return None
        
        # 提取JSON部分
        json_content = json_str[start:]
        
        # 统计各种括号的数量
        brace_count = 0  # {}
        bracket_count = 0  # []
        in_string = False
        escape_next = False
        
        for char in json_content:
            if escape_next:
                escape_next = False
                continue
            
            if char == "\\":
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if not in_string:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                elif char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1
        
        # 修复JSON
        fixed = json_content
        
        # 如果有未闭合的字符串（奇数个引号），添加闭合引号
        quote_count = json_content.count('"') - json_content.count('\\"')
        if quote_count % 2 == 1:
            fixed += '"'
        
        # 关闭所有未闭合的数组
        while bracket_count > 0:
            fixed += "]"
            bracket_count -= 1
        
        # 关闭所有未闭合的对象
        while brace_count > 0:
            fixed += "}"
            brace_count -= 1
        
        return fixed

    def run_simulation(self):
        """运行模拟
        
        每个角色按泊松分布触发登录，登录后批量浏览帖子并决策互动/发帖
        """
        # 初始化每个用户的下次登录时间
        next_login_times = {}
        simulation_time = 0  # 模拟时间（秒）
        real_start_time = time.time()  # 真实开始时间
        
        # 用于统计每个用户的登录次数
        login_count_per_user = {user.id: 0 for user in self.users}
        # 记录上次统计时间（用于计算每日登录次数）
        last_daily_reset = 0
        # 一天的模拟时间（测试模式下：24 * test_hour_duration 秒）
        day_duration = 24 * self.test_hour_duration if self.test_mode else 86400
        
        # 为每个用户计算初始下次登录时间
        for user in self.users:
            # 计算登录lambda（每秒的事件率）
            if self.test_mode:
                # 测试模式：test_hour_duration秒模拟1小时
                login_lambda_per_second = user.get_hourly_login_lambda() / self.test_hour_duration
            else:
                # 正常模式：直接计算每秒的事件率
                login_lambda_per_second = user.get_hourly_login_lambda() / 3600
            
            # 生成首次登录时间间隔（秒），并转换为绝对时间
            login_interval = user.generate_exponential_interval(login_lambda_per_second)
            next_login_times[user.id] = simulation_time + login_interval
            
            print(f"  {user.avatar} {user.username}: 每小时λ={user.get_hourly_login_lambda():.4f}, 每秒λ={login_lambda_per_second:.6f}, 首次登录间隔={login_interval:.1f}秒")
        
        print("\n=== 开始基于登录机制的AI社交模拟 ===\n")
        print("按Ctrl+C停止测试\n")
        
        # 使用线程池处理登录会话任务
        max_workers = min(len(self.users) * 2, 20)
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 存储正在执行的任务
                pending_futures = {}
                
                while self.running:
                    # 检查是否过了一天，重置每日统计
                    if simulation_time - last_daily_reset >= day_duration:
                        # 打印每日登录统计
                        print(f"\n{'='*60}")
                        print(f"每日登录统计 (模拟第 {int((simulation_time // day_duration) + 1)} 天)")
                        print(f"{'='*60}")
                        for user in self.users:
                            count = login_count_per_user[user.id]
                            print(f"  {user.avatar} {user.username}: {count} 次登录 (预期: {user.get_daily_login_frequency():.2f} 次/天)")
                        print(f"{'='*60}\n")
                        # 重置统计
                        login_count_per_user = {user.id: 0 for user in self.users}
                        last_daily_reset = simulation_time
                    
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
                    
                    # 记录登录次数
                    login_count_per_user[user_id] += 1
                    
                    # 执行登录会话（新架构核心）
                    future = executor.submit(self._execute_login_session, user, simulation_time)
                    pending_futures[f'login_{user_id}'] = future
                    
                    # 计算下一次登录时间
                    if self.test_mode:
                        login_lambda_per_second = user.get_hourly_login_lambda() / self.test_hour_duration
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
            # 停止热度计算模块
            self.stop_hot_calculation()


# HTML 页面路由 - 明确为每个页面创建路由
@app.route('/')
def index():
    """返回社区首页"""
    return send_from_directory('.', 'social-platform.html')

@app.route('/social-platform.html')
def social_platform():
    """返回社区首页"""
    return send_from_directory('.', 'social-platform.html')

@app.route('/dashboard.html')
def dashboard():
    """返回仪表盘页面"""
    return send_from_directory('.', 'dashboard.html')

@app.route('/graph.html')
def graph():
    """返回关系图谱页面"""
    return send_from_directory('.', 'graph.html')

@app.route('/user-profile.html')
def user_profile():
    """返回用户资料页面"""
    return send_from_directory('.', 'user-profile.html')

# 静态资源服务（图片、配置文件等）
@app.route('/<path:filename>')
def serve_static(filename):
    """提供静态资源服务"""
    return send_from_directory('.', filename)

# API路由
@app.route('/api/posts', methods=['GET'])
def get_posts():
    """获取所有帖子（按时间排序，从旧到新）"""
    return jsonify(posts)

@app.route('/api/posts/time', methods=['GET'])
def get_posts_by_time():
    """获取按时间排序的帖子（从新到旧）
    
    参数:
        count: 需要的帖子数量，默认50
    """
    count = request.args.get('count', 50, type=int)
    count = min(max(5, count), 100)
    
    with posts_lock:
        sorted_posts = sorted(posts, key=lambda x: x.get("full_timestamp", 0), reverse=True)
        return jsonify(sorted_posts[:count])

@app.route('/api/posts/hot', methods=['GET'])
def get_posts_by_hot():
    """获取按热度排序的帖子（从高到低）
    
    参数:
        count: 需要的帖子数量，默认50
    """
    count = request.args.get('count', 50, type=int)
    count = min(max(5, count), 100)
    
    with posts_lock:
        if posts:
            # 确保所有帖子都有热度值
            for post in posts:
                if "hotness" not in post:
                    post["hotness"] = 0
            
            sorted_posts = sorted(posts, key=lambda x: x["hotness"], reverse=True)
            return jsonify(sorted_posts[:count])
        return jsonify([])

@app.route('/api/posts/recommended', methods=['GET'])
def get_recommended_posts():
    """获取推荐帖子（70%高热度 + 30%新帖子）
    
    参数:
        count: 需要的帖子数量，默认20
    """
    count = request.args.get('count', 20, type=int)
    count = min(max(5, count), 50)  # 限制在5-50之间
    
    recommended = []
    with posts_lock:
        if posts:
            # 确保所有帖子都有热度值
            for post in posts:
                if "hotness" not in post:
                    post["hotness"] = 0
            
            # 按热度排序（从高到低）
            sorted_by_hot = sorted(posts, key=lambda x: x["hotness"], reverse=True)
            
            # 按时间排序（从新到旧）
            sorted_by_time = sorted(posts, key=lambda x: x.get("full_timestamp", 0), reverse=True)
            
            # 计算需要的高热度和新帖子数量
            hot_count = max(1, int(count * 0.7))
            new_count = max(1, count - hot_count)
            
            # 去重选择
            selected_hot = []
            selected_new = []
            used_ids = set()
            
            # 选择高热度帖子
            for post in sorted_by_hot:
                if len(selected_hot) >= hot_count:
                    break
                if post["id"] not in used_ids:
                    selected_hot.append(post)
                    used_ids.add(post["id"])
            
            # 选择新帖子
            for post in sorted_by_time:
                if len(selected_new) >= new_count:
                    break
                if post["id"] not in used_ids:
                    selected_new.append(post)
                    used_ids.add(post["id"])
            
            # 合并并打乱顺序
            recommended = selected_hot + selected_new
            random.shuffle(recommended)
            
            # 截取需要的数量
            recommended = recommended[:count]
    
    return jsonify(recommended)

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

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """获取系统日志
    
    参数:
        limit: 返回的日志数量，默认100
        offset: 从第几条开始，默认0
    """
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    with logs_lock:
        # 复制一份避免并发问题
        logs_copy = list(logs)
    
    # 直接取最新的limit条日志（按时间顺序，最新的在最后）
    result = logs_copy[-limit:] if limit > 0 else []
    
    return jsonify({
        'total': len(logs_copy),
        'logs': result
    })

@app.route('/api/graph', methods=['GET'])
def get_graph_data():
    """获取角色关系图谱数据"""
    # 统计真实的用户互动数据
    user_post_count = {}
    user_like_count = {}
    user_comment_count = {}
    user_interaction_map = {}
    
    # 初始化统计
    for user in users:
        user_post_count[user.id] = 0
        user_like_count[user.id] = 0
        user_comment_count[user.id] = 0
        user_interaction_map[user.id] = {}
    
    # 从帖子中统计真实数据
    with posts_lock:
        for post in posts:
            author_id = int(post["author"]["id"])
            
            # 统计发帖数
            if author_id in user_post_count:
                user_post_count[author_id] += 1
            
            # 统计点赞关系
            for like in post.get("interactions", {}).get("likes", []):
                liker_id = int(like["user_id"])
                if liker_id in user_like_count:
                    user_like_count[liker_id] += 1
                
                # 记录互动关系
                if liker_id in user_interaction_map and author_id != liker_id:
                    if author_id not in user_interaction_map[liker_id]:
                        user_interaction_map[liker_id][author_id] = 0
                    user_interaction_map[liker_id][author_id] += 1
            
            # 统计评论关系
            for comment in post.get("interactions", {}).get("comments", []):
                commenter_id = int(comment["user_id"])
                if commenter_id in user_comment_count:
                    user_comment_count[commenter_id] += 1
                
                # 记录互动关系
                if commenter_id in user_interaction_map and author_id != commenter_id:
                    if author_id not in user_interaction_map[commenter_id]:
                        user_interaction_map[commenter_id][author_id] = 0
                    user_interaction_map[commenter_id][author_id] += 1
    
    # 构建节点数据（使用真实数据）
    nodes = []
    for user in users:
        # 使用真实数据计算热力值
        post_count = user_post_count.get(user.id, 0)
        like_count = user_like_count.get(user.id, 0)
        comment_count = user_comment_count.get(user.id, 0)
        
        # 热力值 = 发帖*20 + 点赞*5 + 评论*10
        hotness = post_count * 20 + like_count * 5 + comment_count * 10
        posts_24h = post_count
        interactions_24h = like_count + comment_count
        
        nodes.append({
            "id": user.id,
            "name": user.username,
            "avatar": user.avatar,
            "hotness": hotness,
            "posts_24h": posts_24h,
            "interactions_24h": interactions_24h
        })
    
    # 构建边数据
    edges = []
    
    # 添加关注关系（真实数据，双向都要显示）
    for user in users:
        if user.following:
            for following_id in user.following:
                # 查找真实互动次数
                interactions = user_interaction_map.get(user.id, {}).get(following_id, 0)
                edges.append({
                    "source": user.id,
                    "target": following_id,
                    "type": "follow",
                    "interactions": max(1, interactions)
                })
    
    # 添加互动关系（真实数据）
    for source_id in user_interaction_map:
        for target_id, interactions in user_interaction_map[source_id].items():
            if interactions >= 2:  # 只显示有2次以上互动的
                # 检查是否已经有关注关系
                has_follow = False
                for edge in edges:
                    if (edge["source"] == source_id and edge["target"] == target_id and edge["type"] == "follow"):
                        has_follow = True
                        break
                if not has_follow:
                    edges.append({
                        "source": source_id,
                        "target": target_id,
                        "type": "interaction",
                        "interactions": interactions
                    })
    
    return jsonify({
        "nodes": nodes,
        "edges": edges
    })


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