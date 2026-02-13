import random
import json
import time
import threading
import math
from flask import Flask, jsonify, request
from flask_cors import CORS

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 启用CORS，允许前端访问

# 创建用户类
class User(object):

    def __init__(self, user_id, username, avatar, personal_signature, post_frequency, interaction_frequency, post_prompt, comment_prompt):
        self.id = user_id
        self.username = username
        self.avatar = avatar
        self.personal_signature = personal_signature
        self.frequency = post_frequency
        self.interaction_frequency = interaction_frequency
        self.prompt = post_prompt
        self.comment_prompt = comment_prompt

    def post(self):
        """生成帖子内容（调用硅基流动API）"""
        import requests
        
        # 硅基流动API配置
        api_url = "https://api.siliconflow.cn/v1/chat/completions"
        api_key = "sk-kookgpxohtivpdxotdnhgdgrjqidpsnhfptsmwrspjwiiukj"  # 需要替换为实际的API密钥
        
        # API请求参数
        payload = {
            "model": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "messages": [
                {"role": "system", "content": "你是一个社交平台用户，根据给定的prompt生成自然的帖子内容。"},
                {"role": "user", "content": self.prompt}
            ],
            "temperature": 1.0,
            "max_tokens": 50
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
            user["comment_prompt"])
        )

# 存储帖子数据
posts = []

# 存储用户对象映射（用于快速查找）
user_map = {user.id: user for user in users}


class AIScheduler:
    """AI用户调度器"""
    
    def __init__(self, users):
        self.users = users
        self.running = True
        self.test_mode = True  # 测试模式，使用缩短的时间单位
        self.test_hour_duration = 10  # 测试模式下每小时的持续时间（秒）
        # 统计相关属性
        self.statistics_start_time = time.time()  # 统计开始时间
        self.statistics_posts = []  # 存储统计周期内的帖子
        self.statistics_thread = None  # 统计线程
        self.statistics_running = True
    
    def add_post_to_statistics(self, post):
        """添加新帖子到统计
        
        Args:
            post: 帖子对象
        """
        # 为帖子添加时间戳，用于统计
        post['stat_time'] = time.time()
        self.statistics_posts.append(post)
    
    def reset_statistics(self):
        """重置统计数据"""
        self.statistics_start_time = time.time()
        # 只保留当前统计周期内的帖子
        current_time = time.time()
        if self.test_mode:
            # 测试模式：24个测试小时 = 24 * test_hour_duration 秒
            window = 24 * self.test_hour_duration
        else:
            # 正常模式：24小时 = 86400秒
            window = 86400
        
        self.statistics_posts = [p for p in self.statistics_posts if current_time - p.get('stat_time', 0) <= window]
    
    def calculate_statistics(self):
        """计算统计数据
        
        Returns:
            tuple: (发帖人数, 发帖总数量)
        """
        current_time = time.time()
        
        # 确定时间窗口
        if self.test_mode:
            # 测试模式：24个测试小时 = 24 * test_hour_duration 秒
            window = 24 * self.test_hour_duration
        else:
            # 正常模式：24小时 = 86400秒
            window = 86400
        
        # 过滤出时间窗口内的帖子
        recent_posts = [p for p in self.statistics_posts if current_time - p.get('stat_time', 0) <= window]
        
        # 统计发帖人数（去重）
        poster_ids = set()
        for post in recent_posts:
            author_id = post.get('author', {}).get('id')
            if author_id:
                poster_ids.add(author_id)
        
        # 统计发帖总数量
        post_count = len(recent_posts)
        
        return len(poster_ids), post_count
    
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
    
    def _execute_post(self, user, current_hour, delay_time):
        """执行发帖操作（带延迟）"""
        # 执行延迟
        if self.test_mode:
            # 测试模式：延迟时间是秒
            time.sleep(delay_time)
        else:
            # 正常模式：延迟时间是分钟，需要转换为秒
            time.sleep(delay_time * 60)
        
        # 计算显示的发帖时间
        if self.test_mode:
            # 测试模式：将秒转换为分钟显示，小时部分模24以保持正常时间格式
            display_minute = int((delay_time / self.test_hour_duration) * 60)
            display_hour = current_hour % 24  # 小时部分模24，超过23时归零
            post_time = f"{display_hour:02d}:{display_minute:02d}"
        else:
            # 正常模式：使用完整的当前时间
            post_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 生成帖子内容
        content = user.post()
        # 输出发帖信息
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
            }
        }
        posts.append(post)
        
        # 添加帖子到统计模块
        self.add_post_to_statistics(post)
    
    def _execute_post_poisson(self, user, simulation_time):
        """执行基于泊松过程的发帖操作"""
        # 计算显示的发帖时间
        if self.test_mode:
            # 测试模式：10秒模拟1小时
            # 计算模拟的小时数和分钟数
            simulated_hours = int(simulation_time / self.test_hour_duration)
            remaining_seconds = simulation_time % self.test_hour_duration
            simulated_minutes = int((remaining_seconds / self.test_hour_duration) * 60)
            display_hour = simulated_hours % 24  # 小时部分模24，超过23时归零
            post_time = f"{display_hour:02d}:{simulated_minutes:02d}"
        else:
            # 正常模式：使用完整的当前时间
            post_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 生成帖子内容
        content = user.post()
        # 输出发帖信息
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
            }
        }
        posts.append(post)
        
        # 添加帖子到统计模块
        self.add_post_to_statistics(post)

    def run_simulation(self):
        """运行模拟（基于泊松过程）"""
        # 初始化每个用户的下次发帖时间
        next_post_times = {}
        simulation_time = 0  # 模拟时间（秒）
        real_start_time = time.time()  # 真实开始时间
        
        # 为每个用户计算初始下次发帖时间
        for user in self.users:
            # 计算每秒钟的lambda值
            if self.test_mode:
                # 测试模式：10秒模拟1小时，时间加速360倍
                # 为了保持相同的发帖频率，lambda值需要相应调整
                # 正常模式：1小时 = 3600秒，测试模式：1小时 = 10秒
                # 所以测试模式下每秒的lambda = 正常模式下360秒的lambda
                lambda_per_second = user.get_hourly_lambda() * 360 / 3600
            else:
                # 正常模式：每小时lambda -> 每秒lambda: lambda_hourly / 3600
                lambda_per_second = user.get_hourly_lambda() / 3600
            
            # 生成首次发帖的时间间隔（秒）
            interval = user.generate_exponential_interval(lambda_per_second)
            next_post_times[user.id] = interval
        
        print("\n=== 开始基于泊松过程的随机发帖 ===\n")
        print("按Ctrl+C停止测试\n")
        
        try:
            while self.running:
                # 找到最早的下次发帖时间
                if not next_post_times:
                    break
                
                # 找出所有用户中的最小下次发帖时间
                min_user_id = min(next_post_times, key=next_post_times.get)
                min_time = next_post_times[min_user_id]
                
                # 计算需要等待的真实时间
                if self.test_mode:
                    # 测试模式：时间加速，直接使用模拟时间
                    wait_time = min_time - simulation_time
                    if wait_time > 0:
                        time.sleep(wait_time)
                    simulation_time = min_time
                else:
                    # 正常模式：使用真实时间
                    current_real_time = time.time()
                    elapsed_real_time = current_real_time - real_start_time
                    wait_time = min_time - elapsed_real_time
                    if wait_time > 0:
                        time.sleep(wait_time)
                    simulation_time = min_time
                
                # 获取对应的用户
                user = user_map[min_user_id]
                
                # 执行发帖操作
                self._execute_post_poisson(user, simulation_time)
                
                # 计算下一次发帖的时间间隔
                if self.test_mode:
                    # 测试模式：10秒模拟1小时，时间加速360倍
                    lambda_per_second = user.get_hourly_lambda() * 360 / 3600
                else:
                    # 正常模式：每小时lambda -> 每秒lambda: lambda_hourly / 3600
                    lambda_per_second = user.get_hourly_lambda() / 3600
                
                interval = user.generate_exponential_interval(lambda_per_second)
                next_post_times[min_user_id] = simulation_time + interval
                
        except KeyboardInterrupt:
            print("\n测试已停止")
            # 停止统计模块
            self.stop_statistics()


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
    app.run(debug=False, port=5000)