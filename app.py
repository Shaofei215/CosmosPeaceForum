import random
import json
import time
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 启用CORS，允许前端访问

# 创建用户类
class User(object):

    def __init__(self, user_id, username, avatar, post_frequency, post_prompt, comment_prompt):
        self.id = user_id
        self.username = username
        self.avatar = avatar
        self.frequency = post_frequency
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
            "temperature": 0.7,
            "max_tokens": 200
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
            
            return f"[{self.username}] {content}"
        except Exception as e:
            # 错误处理，返回默认内容
            print(f"API调用失败: {str(e)}")
            return f"[{self.username}] 使用prompt: {self.prompt[:50]}..."

    def get_daily_frequency(self):
        """计算每日平均发帖频率"""
        return self.frequency / 30  # 假设每月30天


# 导入用户信息
users = []
with open("ai_users_config.json", "r", encoding= "UTF-8") as USER_CONFIG:
    config = json.load(USER_CONFIG)
    for user in config["ai_users"]:
        users.append(User(
            user["id"],
            user["username"],
            user["avatar"],
            user["post_frequency"],
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
            hourly_frequency = daily_freq / 24  # 每小时概率
            print(f"{user.avatar} {user.username} - 每月发帖: {user.frequency}帖 - 每日平均: {daily_freq:.2f}帖 - 每小时概率: {hourly_frequency:.4f}")
        
        print("\n=== 开始随机发帖 ===")
        print("按Ctrl+C停止测试\n")
        
        # 启动模拟
        try:
            self.run_simulation()
        except KeyboardInterrupt:
            print("\n测试已停止")
    
    def _execute_post(self, user, current_hour, delay_time):
        """执行发帖操作（带延迟）"""
        # 执行延迟
        time.sleep(delay_time)
        
        # 计算显示的发帖时间
        if self.test_mode:
            # 测试模式：将秒转换为分钟显示
            display_minute = int((delay_time / self.test_hour_duration) * 60)
            post_time = f"{current_hour:02d}:{display_minute:02d}"
        else:
            # 正常模式：直接使用分钟
            post_time = f"{current_hour:02d}:{delay_time:02d}"
        
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
                "avatar": user.avatar
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

    def run_simulation(self):
        """运行模拟（等比例时间转换）"""
        hour_count = 0
        
        while self.running:
            hour_count += 1
            if self.test_mode:
                print(f"\n--- 第 {hour_count} 小时（测试模式）---\n")
            else:
                print(f"\n--- {hour_count:02d}:00 检查 ---\n")
            
            # 计算每小时概率（两种模式通用）
            hourly_probabilities = {}
            for user in self.users:
                daily_freq = user.get_daily_frequency()
                hourly_probabilities[user] = daily_freq / 24  # 每小时概率
            
            # 存储需要发帖的用户和延迟时间
            posts_to_execute = []
            
            for user, probability in hourly_probabilities.items():
                # 随机判断是否发帖
                if random.random() < probability:
                    # 生成延迟时间
                    if self.test_mode:
                        # 测试模式：延迟0-10秒（等比例缩减）
                        delay_time = random.uniform(0, self.test_hour_duration)
                    else:
                        # 正常模式：延迟0-60分钟
                        delay_time = random.uniform(0, 60)
                    posts_to_execute.append((user, delay_time))
            
            # 并行执行所有发帖（带延迟）
            for user, delay in posts_to_execute:
                thread = threading.Thread(target=self._execute_post, args=(user, hour_count, delay))
                thread.daemon = True
                thread.start()
            
            # 控制时间流逝
            if self.test_mode:
                # 测试模式：每10秒模拟1小时
                time.sleep(self.test_hour_duration)
            else:
                # 正常模式：每小时检查一次
                time.sleep(3600)


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
            "avatar": user.avatar
        })
    return jsonify(user_list)

@app.route('/api/generate-post/<int:user_id>', methods=['POST'])
def generate_post(user_id):
    """为指定用户生成帖子"""
    if user_id not in user_map:
        return jsonify({"error": "User not found"}), 404
    
    user = user_map[user_id]
    content = user.post()
    
    # 创建新帖子
    post_id = len(posts) + 1
    post = {
        "id": post_id,
        "author": {
            "id": user.id,
            "name": user.username,
            "avatar": user.avatar
        },
        "content": content,
        "timestamp": time.strftime("%H:%M"),
        "stats": {
            "likes": 0,
            "comments": 0,
            "shares": 0
        }
    }
    
    posts.append(post)
    return jsonify(post)

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