"""
AI 用户线程管理模块
为每个 AI 用户创建独立的线程，管理登录调度
"""
import threading
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional

from .login_scheduler import LoginScheduler


class AIUserThread:
    """
    AI 用户线程类
    每个 AI 用户拥有独立的线程和登录调度器
    """
    
    def __init__(self, user_config: Dict[str, Any]):
        """
        初始化 AI 用户线程
        
        Args:
            user_config: 用户配置字典，包含 id, username, monthly_logins 等字段
        """
        self.user_id = user_config["id"]
        self.username = user_config["username"]
        self.avatar = user_config.get("avatar", "")
        self.monthly_logins = user_config["monthly_logins"]
        self.personality_prompt = user_config.get("personality_prompt", "")
        self.personal_signature = user_config.get("personal_signature", "")
        # 获取平台用户 ID（已初始化）或原始 ID（未初始化）
        self.platform_user_id = user_config.get("platform_user_id", user_config["id"])
        
        # 创建登录调度器
        self.scheduler = LoginScheduler(self.monthly_logins)
        
        # 线程控制
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False
        
        # 统计信息
        self.login_count = 0
        self.last_login_time: Optional[datetime] = None
        self.next_login_time: Optional[datetime] = None
    
    def _login_handler(self):
        """
        登录处理函数（当前仅打印日志）
        未来将在此处实现发帖、互动等功能
        """
        self.login_count += 1
        self.last_login_time = datetime.now()
        
        # 打印登录事件
        print(f"[{self.last_login_time.strftime('%Y-%m-%d %H:%M:%S')}] "
              f"🔑 {self.avatar} {self.username} (平台 ID: {self.platform_user_id}) 登录")
        print(f"   月度目标：{self.monthly_logins} 次 | "
              f"累计登录：{self.login_count} 次 | "
              f"个性签名：{self.personal_signature}")
        
        # TODO: 未来在此处调用社交平台 API 执行操作
        # 例如：读取时间线、发帖、评论、点赞、关注等
    
    def _run(self):
        """
        线程运行函数
        循环等待登录时间并执行登录
        """
        print(f"🚀 启动用户线程：{self.avatar} {self.username} (平台 ID: {self.platform_user_id})")
        print(f"   月度登录目标：{self.monthly_logins} 次")
        print(f"   平均登录间隔：{self.scheduler.average_interval / 3600:.2f} 小时")
        
        self.is_running = True
        self.next_login_time = self.scheduler.get_next_login_time()
        
        print(f"   首次登录时间：{self.next_login_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        while not self.stop_event.is_set():
            # 计算等待时间
            now = datetime.now()
            if self.next_login_time > now:
                wait_seconds = (self.next_login_time - now).total_seconds()
                
                # 等待登录时间，期间定期检查停止事件
                if wait_seconds > 0:
                    self.stop_event.wait(timeout=min(wait_seconds, 60))
                    if self.stop_event.is_set():
                        break
                    continue
            
            # 执行登录
            self._login_handler()
            
            # 计算下次登录时间
            self.next_login_time = self.scheduler.get_next_login_time()
            print(f"   下次登录：{self.next_login_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        self.is_running = False
        print(f"⏹️  停止用户线程：{self.avatar} {self.username} (平台 ID: {self.platform_user_id})")
    
    def start(self):
        """
        启动线程
        """
        if self.thread is not None and self.thread.is_alive():
            print(f"⚠️  用户 {self.username} (平台 ID: {self.platform_user_id}) 的线程已在运行")
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def stop(self):
        """
        停止线程
        """
        if not self.is_running:
            return
        
        print(f"\n⏸️  准备停止用户：{self.avatar} {self.username} (平台 ID: {self.platform_user_id})")
        self.stop_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取用户线程状态
        
        Returns:
            状态字典
        """
        return {
            "user_id": self.user_id,
            "platform_user_id": self.platform_user_id,
            "username": self.username,
            "is_running": self.is_running,
            "login_count": self.login_count,
            "last_login_time": self.last_login_time.isoformat() if self.last_login_time else None,
            "next_login_time": self.next_login_time.isoformat() if self.next_login_time else None,
            "monthly_logins": self.monthly_logins
        }


class ThreadManager:
    """
    线程管理器
    管理所有 AI 用户的线程
    """
    
    def __init__(self):
        """
        初始化线程管理器
        """
        self.user_threads: Dict[int, AIUserThread] = {}
        self.is_running = False
    
    def add_user(self, user_config: Dict[str, Any]) -> bool:
        """
        添加 AI 用户
        
        Args:
            user_config: 用户配置
            
        Returns:
            是否添加成功
        """
        user_id = user_config["id"]
        platform_user_id = user_config.get("platform_user_id", user_id)
        
        if user_id in self.user_threads:
            print(f"⚠️  用户 {user_config['username']} (平台 ID: {platform_user_id}) 已存在")
            return False
        
        user_thread = AIUserThread(user_config)
        self.user_threads[user_id] = user_thread
        print(f"✅ 添加用户：{user_config['username']} (平台 ID: {platform_user_id})")
        return True
    
    def remove_user(self, user_id: int) -> bool:
        """
        移除 AI 用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            是否移除成功
        """
        if user_id not in self.user_threads:
            print(f"⚠️  用户 ID: {user_id} 不存在")
            return False
        
        user_thread = self.user_threads[user_id]
        user_thread.stop()
        del self.user_threads[user_id]
        print(f"✅ 移除用户：{user_thread.username}")
        return True
    
    def start_all(self):
        """
        启动所有用户线程
        """
        print("\n" + "="*60)
        print("🎯 启动所有 AI 用户线程")
        print("="*60 + "\n")
        
        self.is_running = True
        for user_thread in self.user_threads.values():
            user_thread.start()
            time.sleep(0.1)  # 避免同时启动造成输出混乱
    
    def stop_all(self):
        """
        停止所有用户线程
        """
        print("\n" + "="*60)
        print("⏹️  停止所有 AI 用户线程")
        print("="*60 + "\n")
        
        self.is_running = False
        for user_thread in self.user_threads.values():
            user_thread.stop()
    
    def get_all_status(self) -> list[Dict[str, Any]]:
        """
        获取所有用户线程状态
        
        Returns:
            状态列表
        """
        return [thread.get_status() for thread in self.user_threads.values()]
    
    def get_user_count(self) -> int:
        """
        获取用户数量
        
        Returns:
            用户数量
        """
        return len(self.user_threads)
