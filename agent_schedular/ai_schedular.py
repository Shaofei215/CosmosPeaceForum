"""
AI 用户线程调度器模块
使用泊松过程计算登录间隔，调度 AI 用户线程
"""
import os
import threading
import math
import random
from typing import Dict, List, Any, Optional
from datetime import datetime

from .time_system import time_system
from .ai_initial import AIUserInitializer
from .ai_behavior import AIBehaviorEngine


class AIUserThread(threading.Thread):
    """AI 用户线程类"""
    
    def __init__(self, user_config: Dict[str, Any], scheduler: 'AIScheduler', 
                 behavior_engine: Optional[AIBehaviorEngine] = None):
        """
        初始化 AI 用户线程
        
        Args:
            user_config: 用户配置信息
            scheduler: 调度器实例
            behavior_engine: 行为引擎实例，可选
        """
        super().__init__(name=f"AIUser-{user_config.get('username', 'Unknown')}")
        self.user_config = user_config
        self.scheduler = scheduler
        self.username = user_config.get("username", "Unknown")
        self.user_id = user_config.get("id", 0)
        self.platform_user_id = user_config.get("platform_user_id")
        self.monthly_logins = user_config.get("monthly_logins", 30)
        
        # 计算泊松分布的参数 lambda (每小时平均登录次数)
        # 假设一个月 30 天，每天 24 小时
        self.login_rate_per_hour = self.monthly_logins / (30 * 24)
        
        self._stop_event = threading.Event()
        
        # 行为引擎（用于登录后的活动）
        self.behavior_engine = behavior_engine
        
        print(f"[{self.username}] 线程已创建，每月理想登录次数：{self.monthly_logins}")
    
    def run(self):
        """线程运行方法"""
        print(f"[{self.username}] 线程启动")
        
        try:
            # 首次登录使用泊松分布计算延迟，避免所有用户同时登录
            # 使用相同的 lambda 参数，但只计算一次（不是循环）
            initial_delay_hours = self._calculate_next_login_delay()
            initial_delay_seconds = initial_delay_hours * 3600
            print(f"[{self.username}] 首次登录将在 {initial_delay_hours:.2f} 小时后（泊松分布）")
            
            if time_system.get_mode() == "test":
                self._stop_event.wait(initial_delay_seconds / time_system._time_scale)
            else:
                self._stop_event.wait(initial_delay_seconds)
            
            while not self._stop_event.is_set():
                # 执行登录操作
                self._login()
                
                # 计算下次登录的时间间隔（泊松过程）
                next_login_delay = self._calculate_next_login_delay()
                
                print(f"[{self.username}] 下次登录将在 {next_login_delay:.2f} 小时后")
                
                # 等待到下次登录时间
                # 转换为秒（考虑时间流速）
                delay_seconds = next_login_delay * 3600
                if time_system.get_mode() == "test":
                    self._stop_event.wait(delay_seconds / time_system._time_scale)
                else:
                    self._stop_event.wait(delay_seconds)
            
            print(f"[{self.username}] 线程停止")
            
        except Exception as e:
            print(f"[{self.username}] 线程异常：{e}")
    
    def _calculate_next_login_delay(self) -> float:
        """
        使用泊松过程计算下次登录的时间间隔（小时）
        
        泊松过程中，事件间隔服从指数分布：
        P(T > t) = e^(-λt)
        
        生成指数分布随机数的公式：
        t = -ln(U) / λ, 其中 U 是 (0,1) 均匀分布的随机数
        
        Returns:
            float: 下次登录的时间间隔（小时）
        """
        # 生成 (0,1) 区间的均匀随机数
        u = random.random()
        
        # 避免 ln(0)
        if u < 1e-10:
            u = 1e-10
        
        # 计算指数分布的时间间隔
        delay_hours = -math.log(u) / self.login_rate_per_hour
        
        return delay_hours
    
    def _login(self):
        """执行登录操作"""
        current_time = time_system.now()
        time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n[{time_str}] [{self.username}] 登录成功")
        
        # 如果配置了行为引擎，执行完整的登录会话
        if self.behavior_engine and self.platform_user_id:
            self.behavior_engine.execute_login_session(self.user_config)
        else:
            # Demo 模式提示
            print(f"[{self.username}] 未配置行为引擎，仅记录登录")
    
    def stop(self):
        """停止线程"""
        print(f"[{self.username}] 收到停止信号")
        self._stop_event.set()


class AIScheduler:
    """AI 调度器类"""
    
    def __init__(self, initializer: Optional[AIUserInitializer] = None,
                 enable_behavior: bool = True):
        """
        初始化 AI 调度器
        
        Args:
            initializer: AI 用户初始化器实例，可选
            enable_behavior: 是否启用行为引擎，默认 True
        """
        self.initializer = initializer or AIUserInitializer()
        self.user_threads: Dict[int, AIUserThread] = {}
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        
        # 行为引擎
        self.enable_behavior = enable_behavior
        self.behavior_engine: Optional[AIBehaviorEngine] = None
        if enable_behavior:
            # 启用 LLM
            current_dir = os.path.dirname(os.path.abspath(__file__))
            llm_config_path = os.path.join(current_dir, "llm_config.json")
            self.behavior_engine = AIBehaviorEngine(
                use_llm=True,
                llm_config_path=llm_config_path
            )
        
        print("[调度器] 调度器已创建")
    
    def start(self, auto_init: bool = True):
        """
        启动调度器
        
        Args:
            auto_init: 是否自动初始化用户
        """
        print("\n[调度器] 启动调度器...")
        print("=" * 60)
        
        # 加载配置并初始化用户
        if auto_init:
            if not self.initializer.load_config():
                print("[调度器] [错误] 加载配置失败，无法启动")
                return
            
            initialized_users = self.initializer.initialize_all_users()
            self.initializer.print_user_summary()
            
            if not initialized_users:
                print("[调度器] [错误] 没有成功初始化的用户，无法启动")
                return
            
            # 创建初始帖子（冷启动保护）
            # 使用绝对路径
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            posts_config_path = os.path.join(project_root, "initial_posts.json")
            self.initializer.initialize_initial_posts(posts_config_path)
        
        # 为每个用户创建线程
        for user_config in self.initializer.get_all_users():
            user_id = user_config.get("id")
            
            if user_id not in self.user_threads:
                user_thread = AIUserThread(user_config, self, self.behavior_engine)
                self.user_threads[user_id] = user_thread
        
        # 启动所有用户线程
        self._running = True
        for user_id, thread in self.user_threads.items():
            thread.start()
            print(f"[调度器] 已启动用户线程：{thread.username}")
        
        print("=" * 60)
        print(f"[调度器] 调度器已启动，共 {len(self.user_threads)} 个 AI 用户")
        print(f"[调度器] 时间模式：{time_system.get_mode()}")
        print(f"[调度器] 行为引擎：{'已启用' if self.enable_behavior else '已禁用'}")
        
        if time_system.get_mode() == "test":
            print(f"[调度器] 时间流速：1 秒 = {time_system._time_scale} 秒")
            print("[调度器] 按 Ctrl+C 停止调度器")
    
    def stop(self):
        """停止调度器"""
        print("\n[调度器] 停止调度器...")
        
        self._running = False
        
        # 停止所有用户线程
        for user_id, thread in self.user_threads.items():
            thread.stop()
        
        # 等待所有线程结束
        for thread in self.user_threads.values():
            thread.join(timeout=5)
        
        print("[调度器] 调度器已停止")
        
        # 打印行为统计
        if self.behavior_engine:
            self.behavior_engine.print_stats()
    
    def get_user_thread(self, user_id: int) -> Optional[AIUserThread]:
        """
        获取指定用户的线程
        
        Args:
            user_id: 用户 ID
            
        Returns:
            Optional[AIUserThread]: 用户线程或 None
        """
        return self.user_threads.get(user_id)
    
    def get_all_threads(self) -> List[AIUserThread]:
        """
        获取所有用户线程
        
        Returns:
            List[AIUserThread]: 线程列表
        """
        return list(self.user_threads.values())
    
    def print_status(self):
        """打印调度器状态"""
        print("\n[调度器] 当前状态:")
        print(f"运行状态：{'运行中' if self._running else '已停止'}")
        print(f"用户线程数：{len(self.user_threads)}")
        print(f"时间模式：{time_system.get_mode()}")
        
        if time_system.get_mode() == "test":
            print(f"当前模拟时间：{time_system.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    # 测试代码
    print("=== AI 调度器测试 ===\n")
    
    scheduler = AIScheduler()
    
    try:
        scheduler.start(auto_init=True)
        
        # 让调度器运行一段时间
        while True:
            time_system.sleep(10)
            scheduler.print_status()
            
    except KeyboardInterrupt:
        print("\n收到中断信号，停止调度器...")
        scheduler.stop()
