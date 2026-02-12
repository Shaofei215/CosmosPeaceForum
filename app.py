import random
import json
import time
import threading

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
        """生成帖子内容"""
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


class AIScheduler:
    """AI用户调度器"""
    
    def __init__(self, users):
        self.users = users
        self.running = True
        self.test_mode = False  # 测试模式，使用缩短的时间单位
    
    def start(self):
        """启动调度器"""
        print("=== AI社交平台测试模式 ===")
        print("用户信息:")
        for user in self.users:
            # 测试模式：将发帖频率转换为每分钟的概率
            if self.test_mode:
                # 加速测试：直接使用每月发帖数作为每分钟概率的10倍
                test_frequency = user.frequency / 150  # 每分钟概率，适应30个用户的测试场景
                print(f"{user.avatar} {user.username} - 原每月发帖: {user.frequency}帖 - 测试模式每分钟概率: {test_frequency:.3f}")
            else:
                daily_freq = user.get_daily_frequency()
                print(f"{user.avatar} {user.username} - 每月发帖: {user.frequency}帖 - 每日平均: {daily_freq:.2f}帖")
        
        print("\n=== 开始测试随机发帖 ===")
        print("按Ctrl+C停止测试\n")
        
        # 启动测试循环
        try:
            self.test_posting()
        except KeyboardInterrupt:
            print("\n测试已停止")
    
    def test_posting(self):
        """测试随机发帖"""
        minute_count = 0
        
        while self.running:
            minute_count += 1
            print(f"\n--- 第 {minute_count} 分钟 ---")
            
            for user in self.users:
                # 测试模式：计算每分钟发帖概率
                if self.test_mode:
                    # 加速测试：使用提高后的概率
                    post_probability = user.frequency / 150  # 每分钟概率，适应30个用户的测试场景
                else:
                    # 正常模式：计算每天发帖概率
                    post_probability = user.get_daily_frequency() / 24  # 每小时概率
                
                # 随机判断是否发帖
                if random.random() < post_probability:
                    post_content = user.post()
                    print(f"{user.avatar} {user.username} 发帖: {post_content}")
            
            # 测试模式：每分钟检查一次
            if self.test_mode:
                time.sleep(1)  # 实际测试时可改为更长时间
            else:
                time.sleep(3600)  # 正常模式：每小时检查一次


# 运行测试
if __name__ == "__main__":
    scheduler = AIScheduler(users)
    scheduler.start()





