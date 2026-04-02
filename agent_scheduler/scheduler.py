# AI Agent 调度器核心模块
# 实现 AI 用户的注册、登录时间计算和会话调度功能
import json
import math
import os
import random
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from .time_system import (
    TimeSystem,
    get_scaled_time,
    get_scaled_timestamp,
    get_time_system,
    set_time_scale,
)


# ==================== 环境配置加载 ====================

def load_env_config(env_file_path: str = ".env") -> Dict[str, str]:
    """
    从 .env 文件加载环境配置

    Args:
        env_file_path: .env 文件路径

    Returns:
        Dict[str, str]: 配置字典
    """
    config = {}
    if not os.path.exists(env_file_path):
        return config

    with open(env_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config


def get_env_config() -> Dict[str, str]:
    """
    获取环境配置

    优先从 agent_scheduler/.env 文件读取配置

    Returns:
        Dict[str, str]: 配置字典
    """
    scheduler_dir = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(scheduler_dir, '.env')
    return load_env_config(env_file)


# ==================== 配置常量 ====================

_env_config = get_env_config()

_api_base = os.environ.get('VITE_API_BASE_URL') or _env_config.get('VITE_API_BASE_URL', 'http://localhost:8000/api/v1')
if _api_base.endswith('/api/v1'):
    API_BASE_URL = _api_base
elif _api_base.endswith('/api/v1/'):
    API_BASE_URL = _api_base[:-1]
else:
    API_BASE_URL = _api_base if _api_base.endswith('/') else f"{_api_base}/api/v1"

ADMIN_KEY = os.environ.get('ADMIN_KEY') or _env_config.get('ADMIN_KEY', '')

AI_USER_PASSWORD = os.environ.get('AI_USER_PASSWORD') or _env_config.get('AI_USER_PASSWORD', 'ai123456')

LOGIN_CHECK_INTERVAL_REAL = 0.1


def _get_config_file_path() -> str:
    scheduler_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.environ.get('AI_USERS_CONFIG_PATH') or _env_config.get('AI_USERS_CONFIG_PATH', 'ai_users_config.json')
    if config_path.startswith('./'):
        return os.path.join(scheduler_dir, config_path[2:])
    elif os.path.isabs(config_path):
        return config_path
    else:
        return os.path.join(scheduler_dir, config_path)


CONFIG_FILE_PATH = _get_config_file_path()


# ==================== 工具函数 ====================

def format_relative_time(seconds: float) -> str:
    """
    将秒数格式化为相对时间字符串

    Args:
        seconds: 秒数

    Returns:
        str: 格式化后的相对时间字符串，如 "2小时30分后"
    """
    if seconds < 0:
        seconds = 0

    if seconds < 60:
        return f"{seconds:.0f}秒后"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}分{secs}秒后" if secs > 0 else f"{minutes}分后"
    else:
        hours = int(seconds // 3600)
        remainder = seconds % 3600
        minutes = int(remainder // 60)
        if minutes > 0:
            return f"{hours}小时{minutes}分后"
        else:
            return f"{hours}小时后"


# ==================== 数据模型 ====================

@dataclass
class AIUserConfig:
    """
    AI 用户配置数据类

    Attributes:
        id: AI 配置 ID
        username: 用户名
        name: 角色名称
        avatar: 头像文件名
        monthly_logins: 每月理想登录次数
        personal_signature: 个性签名
        personality_prompt: 角色性格描述
    """
    id: int
    username: str
    name: str
    avatar: str
    monthly_logins: int
    personal_signature: str
    personality_prompt: str


# ==================== 配置加载模块 ====================

def load_ai_users_config(config_path: str = CONFIG_FILE_PATH) -> List[AIUserConfig]:
    """
    从 JSON 配置文件加载 AI 用户配置

    Args:
        config_path: 配置文件路径

    Returns:
        List[AIUserConfig]: AI 用户配置列表

    Raises:
        FileNotFoundError: 配置文件不存在
        json.JSONDecodeError: JSON 解析失败
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        print(f"[错误] 配置文件不存在: {config_path}")
        raise
    except json.JSONDecodeError as e:
        print(f"[错误] JSON 解析失败: {e}")
        raise

    ai_users = config_data.get('ai_users', [])
    users = []

    for user_data in ai_users:
        try:
            user = AIUserConfig(
                id=user_data.get('id', 0),
                username=user_data.get('username', ''),
                name=user_data.get('name', ''),
                avatar=user_data.get('avatar', ''),
                monthly_logins=user_data.get('monthly_logins', 1),
                personal_signature=user_data.get('personal_signature', ''),
                personality_prompt=user_data.get('personality_prompt', ''),
            )
            users.append(user)
        except Exception as e:
            print(f"[警告] 解析用户配置失败: {user_data.get('username', '未知')}, 错误: {e}")
            continue

    print(f"[信息] 成功加载 {len(users)} 个 AI 用户配置")
    return users


# ==================== API 通信模块 ====================

def register_ai_user(
    username: str,
    password: str,
    ai_config_id: int,
    admin_key: str
) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    通过 AdminKey 注册 AI 用户账号

    Args:
        username: 用户名
        password: 密码
        ai_config_id: AI 配置 ID
        admin_key: 管理员密钥

    Returns:
        Tuple[bool, Optional[Dict], Optional[str]]:
            - 成功标志
            - 响应数据（成功时）
            - 错误信息（失败时）
    """
    url = f"{API_BASE_URL}/auth/register"

    headers = {
        "X-Admin-Key": admin_key,
        "Content-Type": "application/json"
    }

    payload = {
        "username": username,
        "password": password,
        "is_ai_agent": True,
        "ai_config_id": ai_config_id
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 201:
            return True, response.json(), None
        elif response.status_code == 400:
            response_data = response.json()
            detail = response_data.get('detail', '参数错误')
            if '已存在' in str(detail) or 'exists' in str(detail).lower():
                return True, None, "用户已存在（跳过）"
            return False, None, f"参数错误: {detail}"
        elif response.status_code == 401:
            return False, None, "管理员密钥无效"
        else:
            return False, None, f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        return False, None, "无法连接到 API 服务器"
    except requests.exceptions.Timeout:
        return False, None, "API 请求超时"
    except Exception as e:
        return False, None, f"请求异常: {str(e)}"


def update_user_profile(
    user_id: int,
    bio: str,
    token: str
) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    更新用户资料

    Args:
        user_id: 用户 ID
        bio: 个人简介
        token: 访问令牌

    Returns:
        Tuple[bool, Optional[Dict], Optional[str]]:
            - 成功标志
            - 响应数据（成功时）
            - 错误信息（失败时）
    """
    url = f"{API_BASE_URL}/users/{user_id}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "bio": bio
    }

    try:
        response = requests.put(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            return True, response.json(), None
        elif response.status_code == 401:
            return False, None, "无权限修改此用户"
        elif response.status_code == 404:
            return False, None, "用户不存在"
        else:
            return False, None, f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        return False, None, "无法连接到 API 服务器"
    except requests.exceptions.Timeout:
        return False, None, "API 请求超时"
    except Exception as e:
        return False, None, f"请求异常: {str(e)}"


def login_user(
    username: str,
    password: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    AI 用户登录获取访问令牌

    Args:
        username: 用户名
        password: 密码

    Returns:
        Tuple[bool, Optional[str], Optional[str]]:
            - 成功标志
            - 访问令牌（成功时）
            - 错误信息（失败时）
    """
    url = f"{API_BASE_URL}/auth/ai-login"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "username": username,
        "password": password
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return True, data.get('access_token'), None
        elif response.status_code == 401:
            return False, None, "用户名或密码错误"
        else:
            return False, None, f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        return False, None, "无法连接到 API 服务器"
    except requests.exceptions.Timeout:
        return False, None, "API 请求超时"
    except Exception as e:
        return False, None, f"请求异常: {str(e)}"


# ==================== 泊松过程登录间隔计算模块 ====================

def calculate_poisson_interval(monthly_logins: int) -> float:
    """
    使用泊松过程模型计算登录时间间隔

    泊松过程假设事件在时间上随机发生，平均率为 lambda。
    相邻事件间隔服从指数分布：T = -ln(U) / lambda
    其中 U 是 [0,1] 区间的均匀随机数。

    Args:
        monthly_logins: 每月平均登录次数（lambda）

    Returns:
        float: 登录时间间隔（秒）
    """
    if monthly_logins <= 0:
        monthly_logins = 1

    lambda_rate = monthly_logins / (30 * 24 * 3600)

    u = random.uniform(0.0001, 0.9999)
    interval = -math.log(u) / lambda_rate

    return interval


# ==================== 登录会话处理模块 ====================

def trigger_login_event(username: str, time_system: TimeSystem) -> None:
    """
    触发登录事件（占位实现）

    当前阶段仅打印登录事件信息，后续可扩展为完整的会话逻辑。

    Args:
        username: 用户名
        time_system: 时间系统实例
    """
    current_scaled_time = time_system.get_scaled_time()
    print(f"[登录事件] 用户 {username} 于 {current_scaled_time} 触发登录")


# ==================== 单用户调度器 ====================

class AIUserScheduler:
    """
    单个 AI 用户的调度器

    每个 AI 用户拥有独立的线程，运行独立的调度循环：
    1. 注册用户（如需要）
    2. 更新用户简介（如需要）
    3. 循环：
       - 计算下次登录时间
       - 休眠至该时间
       - 触发登录事件
       - 计算下次登录时间（重复）

    Attributes:
        user_config: 用户配置
        time_system: 时间系统实例
        admin_key: 管理员密钥
        password: 用户密码
        running: 调度器运行状态
        _thread: 调度线程
        _registered_user_id: 注册后的用户 ID
        _bio_updated: 简介是否已更新
    """

    def __init__(
        self,
        user_config: AIUserConfig,
        time_system: TimeSystem,
        admin_key: str,
        password: str
    ):
        """
        初始化单用户调度器

        Args:
            user_config: 用户配置
            time_system: 时间系统实例
            admin_key: 管理员密钥
            password: 用户密码
        """
        self.user_config = user_config
        self.time_system = time_system
        self.admin_key = admin_key
        self.password = password
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._registered_user_id: Optional[int] = None
        self._bio_updated = False

    def _register_if_needed(self) -> None:
        """
        如需要，注册用户并更新简介
        """
        username = self.user_config.username if self.user_config.username else self.user_config.name

        if not username:
            print(f"[{username}] 用户名为空，跳过注册")
            return

        success, data, error = register_ai_user(
            username=username,
            password=self.password,
            ai_config_id=self.user_config.id,
            admin_key=self.admin_key
        )

        if success:
            if error == "用户已存在（跳过）":
                print(f"[{username}] 用户已存在，跳过注册")
            else:
                self._registered_user_id = data.get('id') if data else None
                print(f"[{username}] 注册成功 (ID: {self._registered_user_id})")
        else:
            print(f"[{username}] 注册失败: {error}")
            return

        if self._registered_user_id and self.user_config.personal_signature:
            self._update_bio()

    def _update_bio(self) -> None:
        """
        更新用户简介
        """
        username = self.user_config.username if self.user_config.username else self.user_config.name

        if not self._registered_user_id:
            print(f"[{username}] 未注册，无法更新简介")
            return

        print(f"[{username}] 正在更新用户简介...")
        login_success, token, login_error = login_user(username, self.password)

        if login_success and token:
            bio_success, _, bio_error = update_user_profile(
                self._registered_user_id,
                self.user_config.personal_signature,
                token
            )
            if bio_success:
                print(f"[{username}] 更新用户简介成功")
                self._bio_updated = True
            else:
                print(f"[{username}] 更新用户简介失败: {bio_error}")
        else:
            print(f"[{username}] 登录获取令牌失败: {login_error}")

    def _scheduling_loop(self) -> None:
        """
        调度循环

        持续运行：计算下次登录时间 -> 休眠 -> 触发登录 -> 重复
        """
        username = self.user_config.username if self.user_config.username else self.user_config.name

        print(f"[{username}] 调度循环已启动")

        while self.running:
            try:
                current_time = self.time_system.get_scaled_timestamp()

                interval = calculate_poisson_interval(self.user_config.monthly_logins)
                next_login_time = current_time + interval

                print(f"[{username}] 下次登录: {format_relative_time(interval)}")

                while self.running:
                    current_time = self.time_system.get_scaled_timestamp()
                    remaining = next_login_time - current_time

                    if remaining <= 0:
                        break

                    sleep_time = min(remaining, 0.5)
                    time.sleep(sleep_time)

                if not self.running:
                    break

                trigger_login_event(username, self.time_system)

            except Exception as e:
                print(f"[{username}] 调度循环异常: {e}")
                traceback.print_exc()
                time.sleep(1)

        print(f"[{username}] 调度循环已停止")

    def start(self) -> None:
        """
        启动调度器
        """
        if self.running:
            print(f"[{self.user_config.name}] 调度器已在运行中")
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[{self.user_config.name}] 调度器已启动")

    def _run(self) -> None:
        """
        运行流程：注册 -> 更新简介 -> 调度循环
        """
        self._register_if_needed()

        if self._registered_user_id is None and not self.user_config.username:
            return

        if not self._bio_updated and self.user_config.personal_signature:
            time.sleep(0.5)

        self._scheduling_loop()

    def stop(self) -> None:
        """
        停止调度器
        """
        if not self.running:
            print(f"[{self.user_config.name}] 调度器未在运行")
            return

        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print(f"[{self.user_config.name}] 调度器已停止")


# ==================== 全局调度器 ====================

class AgentSchedulerManager:
    """
    AI Agent 调度器管理器

    统一管理所有 AI 用户的调度器，为每个用户创建独立的调度线程。

    Attributes:
        time_system: 时间系统实例
        schedulers: 用户调度器字典
    """

    def __init__(self):
        """
        初始化调度器管理器
        """
        self.time_system = get_time_system()
        self.schedulers: Dict[int, AIUserScheduler] = {}

    def load_and_start(self, config_path: str = CONFIG_FILE_PATH) -> None:
        """
        加载配置并启动所有用户的调度器

        Args:
            config_path: AI 用户配置文件路径
        """
        try:
            users = load_ai_users_config(config_path)
        except Exception as e:
            print(f"[错误] 加载配置失败: {e}")
            return

        if not ADMIN_KEY:
            print("[警告] 未配置 ADMIN_KEY，无法注册用户")
            return

        for user in users:
            scheduler = AIUserScheduler(
                user_config=user,
                time_system=self.time_system,
                admin_key=ADMIN_KEY,
                password=AI_USER_PASSWORD
            )
            self.schedulers[user.id] = scheduler

        for scheduler in self.schedulers.values():
            scheduler.start()

        print(f"[信息] 已启动 {len(self.schedulers)} 个用户调度器")

    def stop_all(self) -> None:
        """
        停止所有用户的调度器
        """
        for scheduler in self.schedulers.values():
            scheduler.stop()

        self.schedulers.clear()
        print("[信息] 所有调度器已停止")

    def print_status(self) -> None:
        """
        打印调度状态
        """
        print("\n" + "=" * 50)
        print(f"调度器管理器状态")
        print(f"当前缩放时间: {self.time_system.format_scaled_time()}")
        print(f"时间倍率: {self.time_system.get_scale()}")
        print(f"总用户数: {len(self.schedulers)}")
        print("=" * 50)

        running_count = sum(1 for s in self.schedulers.values() if s.running)
        print(f"运行中的调度器: {running_count}/{len(self.schedulers)}")
        print()


# ==================== 主函数 ====================

def main():
    """
    主函数

    启动 AI Agent 调度器管理器，加载配置并为每个用户创建独立的调度线程。
    """
    print("=" * 60)
    print("Herta-Tree AI Agent 调度器")
    print("=" * 60)

    print("\n[配置信息]")
    print(f"  API 地址: {API_BASE_URL}")
    print(f"  配置文件: {CONFIG_FILE_PATH}")
    if ADMIN_KEY:
        print(f"  Admin Key: 已配置")
    else:
        print(f"  Admin Key: 未配置（无法注册用户）")

    if not ADMIN_KEY:
        print("\n[错误] 未配置 ADMIN_KEY，无法进行用户注册")
        return

    manager = AgentSchedulerManager()
    manager.load_and_start(CONFIG_FILE_PATH)

    print("\n调度器已启动，按 Ctrl+C 停止")

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n正在停止所有调度器...")
        manager.stop_all()
        print("调度器已全部停止")


if __name__ == "__main__":
    main()
