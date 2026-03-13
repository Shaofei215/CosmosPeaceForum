"""
独立时间系统模块
提供正常模式和测试模式两种时间模式
测试模式下使用加速可调的模拟时间
"""
import time
from datetime import datetime, timedelta
from typing import Optional
import threading


# ==================== 配置区域 ====================
# 测试模式开关
TEST_MODE = True  # True: 测试模式 (模拟时间), False: 正常模式 (系统时间)

# 测试模式配置
SIMULATION_START_HOUR = 0  # 模拟时间起始点 (小时)
SIMULATION_START_MINUTE = 0  # 模拟时间起始点 (分钟)
TIME_SCALE = 10  # 时间流速倍率 (1 秒 = TIME_SCALE 秒真实时间，20 倍即 3秒=1分钟)
# =================================================


class TimeSystem:
    """独立时间系统类"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式，确保全局只有一个时间系统实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化时间系统"""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._mode = "test" if TEST_MODE else "normal"
        
        if self._mode == "test":
            # 测试模式：从配置的起始时间开始
            self._simulated_time = datetime.now().replace(
                hour=SIMULATION_START_HOUR,
                minute=SIMULATION_START_MINUTE,
                second=0,
                microsecond=0
            )
            self._real_start_time = time.time()
            self._time_scale = TIME_SCALE
            print(f"[时间系统] 测试模式已启动")
            print(f"[时间系统] 起始时间：{self._simulated_time.strftime('%H:%M:%S')}")
            print(f"[时间系统] 时间流速：1 秒 = {self._time_scale} 秒")
        else:
            print(f"[时间系统] 正常模式已启动")
    
    def now(self) -> datetime:
        """
        获取当前时间
        
        Returns:
            datetime: 当前时间对象
        """
        if self._mode == "test":
            # 测试模式：计算加速后的模拟时间
            elapsed_real = time.time() - self._real_start_time
            elapsed_simulated = elapsed_real * self._time_scale
            return self._simulated_time + timedelta(seconds=elapsed_simulated)
        else:
            # 正常模式：返回系统时间
            return datetime.now()
    
    def get_timestamp(self) -> float:
        """
        获取当前时间戳
        
        Returns:
            float: 当前时间戳
        """
        if self._mode == "test":
            return self.now().timestamp()
        else:
            return time.time()
    
    def sleep(self, seconds: float):
        """
        休眠指定秒数（考虑时间流速）
        
        Args:
            seconds: 休眠秒数
        """
        if self._mode == "test":
            # 测试模式：根据时间流速调整实际休眠时间
            real_sleep_time = seconds / self._time_scale
            time.sleep(max(0.001, real_sleep_time))
        else:
            # 正常模式：直接休眠
            time.sleep(seconds)
    
    def get_mode(self) -> str:
        """
        获取当前时间模式
        
        Returns:
            str: "test" 或 "normal"
        """
        return self._mode
    
    def set_time_scale(self, scale: float):
        """
        设置测试模式的时间流速（仅测试模式有效）
        
        Args:
            scale: 时间流速倍率
        """
        if self._mode == "test":
            # 更新起始时间以保持一致性
            current_sim = self._simulated_time
            elapsed_real = time.time() - self._real_start_time
            elapsed_sim = elapsed_real * self._time_scale
            new_base_sim = current_sim - timedelta(seconds=elapsed_sim)
            
            self._time_scale = scale
            self._simulated_time = new_base_sim
            print(f"[时间系统] 时间流速已更新：1 秒 = {scale} 秒")
        else:
            print("[时间系统] 正常模式下无法设置时间流速")
    
    def __str__(self) -> str:
        """字符串表示"""
        current_time = self.now()
        if self._mode == "test":
            return f"[测试模式] {current_time.strftime('%Y-%m-%d %H:%M:%S')} (流速：{self._time_scale}x)"
        else:
            return f"[正常模式] {current_time.strftime('%Y-%m-%d %H:%M:%S')}"


# 全局时间系统实例
time_system = TimeSystem()


if __name__ == "__main__":
    # 简单测试
    print("=== 时间系统测试 ===")
    print(f"当前模式：{time_system.get_mode()}")
    print(f"当前时间：{time_system}")
    
    if time_system.get_mode() == "test":
        print("\n测试时间流速...")
        for i in range(5):
            print(f"第{i+1}次：{time_system.now().strftime('%H:%M:%S')}")
            time_system.sleep(1)
        
        print(f"\n最终时间：{time_system}")
