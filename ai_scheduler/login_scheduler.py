"""
登录调度器模块
基于泊松过程计算 AI 用户的登录时间间隔
"""
import random
import math
from datetime import datetime, timedelta


class LoginScheduler:
    """
    基于泊松过程的登录调度器
    
    泊松过程原理：
    - 如果每月期望登录次数为 λ，则登录时间间隔服从指数分布
    - 指数分布的期望值为 1/λ
    - 使用逆变换采样法生成指数分布的随机样本
    """
    
    def __init__(self, monthly_logins: int):
        """
        初始化登录调度器
        
        Args:
            monthly_logins: 每月期望登录次数 (λ)
        """
        self.monthly_logins = monthly_logins
        # 计算平均每月的秒数 (假设每月 30 天)
        self.seconds_per_month = 30 * 24 * 60 * 60
        # 计算平均登录间隔 (秒)
        self.average_interval = self.seconds_per_month / monthly_logins
    
    def generate_next_interval(self) -> float:
        """
        生成下一次登录的时间间隔 (秒)
        
        使用逆变换采样法从指数分布中采样：
        X ~ Exp(λ) => X = -ln(U) / λ, 其中 U ~ Uniform(0, 1)
        
        Returns:
            下次登录的时间间隔 (秒)
        """
        # 生成 (0, 1) 区间的均匀分布随机数
        u = random.random()
        # 避免 ln(0) 的情况
        while u == 0:
            u = random.random()
        
        # 指数分布采样：-ln(U) * average_interval
        interval = -math.log(u) * self.average_interval
        
        return interval
    
    def get_next_login_time(self, current_time: datetime = None) -> datetime:
        """
        计算下次登录的具体时间
        
        Args:
            current_time: 当前时间，默认为现在
            
        Returns:
            下次登录的时间
        """
        if current_time is None:
            current_time = datetime.now()
        
        interval_seconds = self.generate_next_interval()
        next_login = current_time + timedelta(seconds=interval_seconds)
        
        return next_login
    
    def generate_login_schedule(self, start_time: datetime = None, 
                                 num_logins: int = 30) -> list[datetime]:
        """
        生成一系列登录时间
        
        Args:
            start_time: 开始时间，默认为现在
            num_logins: 生成的登录次数
            
        Returns:
            登录时间列表
        """
        if start_time is None:
            start_time = datetime.now()
        
        login_times = []
        current_time = start_time
        
        for _ in range(num_logins):
            next_login = self.get_next_login_time(current_time)
            login_times.append(next_login)
            current_time = next_login
        
        return login_times
