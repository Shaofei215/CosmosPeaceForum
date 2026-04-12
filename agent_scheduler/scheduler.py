# AI Agent 调度器核心模块
# 实现 AI 用户的注册、登录时间计算和会话调度功能
import json
import math
import mimetypes
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

from agent_scheduler.time_system import (
    TimeSystem,
    get_scaled_time,
    get_scaled_timestamp,
    get_time_system,
    set_time_scale,
)
from agent_scheduler.context import (
    AgentContext,
    set_current_context,
    clear_current_context,
)
from agent_scheduler.langgraph.executor import run_session, ExecutionResult
from agent_scheduler.langgraph.config import AgentConfig


# ==================== 环境配置加载 ====================

def get_avatar_dir() -> str:
    """
    获取 AI 用户头像目录的绝对路径

    头像文件存储在 agent_scheduler/avatar/ 目录下

    Returns:
        str: 头像目录的绝对路径
    """
    scheduler_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(scheduler_dir, 'avatar')


def get_avatar_file_path(avatar_filename: str) -> Optional[str]:
    """
    获取头像文件的完整路径

    Args:
        avatar_filename: 头像文件名（来自 ai_users_config.json）

    Returns:
        Optional[str]: 完整的头像文件路径，如果文件不存在或文件名为空则返回 None
    """
    if not avatar_filename or not avatar_filename.strip():
        return None

    avatar_dir = get_avatar_dir()
    file_path = os.path.join(avatar_dir, avatar_filename)

    if os.path.exists(file_path) and os.path.isfile(file_path):
        return file_path

    return None


def is_valid_avatar_file(avatar_filename: str) -> bool:
    """
    检查头像文件是否为有效的图片格式

    支持的格式：JPEG, PNG, GIF, WebP

    Args:
        avatar_filename: 头像文件名

    Returns:
        bool: 文件是否为有效的图片格式
    """
    if not avatar_filename or not avatar_filename.strip():
        return False

    file_path = get_avatar_file_path(avatar_filename)
    if not file_path:
        return False

    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type.startswith('image/') and mime_type in [
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/webp'
        ]

    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    _, ext = os.path.splitext(avatar_filename)
    return ext.lower() in valid_extensions


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

_api_base = os.environ.get('AGENT_SCHEDULER_API_BASE_URL') or _env_config.get('AGENT_SCHEDULER_API_BASE_URL')
if not _api_base:
    _api_base = os.environ.get('API_BASE_URL') or _env_config.get('API_BASE_URL')
if not _api_base:
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


def upload_avatar(
    user_id: int,
    avatar_filename: str,
    token: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    上传用户头像到服务器

    Args:
        user_id: 用户 ID
        avatar_filename: 头像文件名（来自 ai_users_config.json）
        token: 访问令牌

    Returns:
        Tuple[bool, Optional[str], Optional[str]]:
            - 成功标志
            - 头像 URL（成功时）
            - 错误信息（失败时）
    """
    file_path = get_avatar_file_path(avatar_filename)
    if not file_path:
        return False, None, f"头像文件不存在或无效: {avatar_filename}"

    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'

    url = f"{API_BASE_URL}/users/avatar"

    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        with open(file_path, 'rb') as f:
            files = {
                'file': (avatar_filename, f, mime_type)
            }
            response = requests.post(url, headers=headers, files=files, timeout=30)

        if response.status_code == 200:
            data = response.json()
            avatar_url = data.get('avatar_url', '')
            return True, avatar_url, None
        elif response.status_code == 400:
            response_data = response.json()
            detail = response_data.get('detail', '文件格式不支持')
            return False, None, f"头像上传失败: {detail}"
        elif response.status_code == 401:
            return False, None, "无权限上传头像"
        else:
            return False, None, f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        return False, None, "无法连接到 API 服务器"
    except requests.exceptions.Timeout:
        return False, None, "头像上传超时"
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

def trigger_login_event(
    username: str,
    time_system: TimeSystem,
    user_id: int,
    ai_config_id: int,
    personality_prompt: str,
    personal_signature: str,
    token: str,
) -> ExecutionResult:
    """
    触发登录事件并执行 LangGraph 会话

    当调度器决定让 AI 用户登录时，调用此函数执行完整的 LangGraph 会话。
    会话流程：环境感知 -> LLM 决策 -> 工具执行 -> ... -> 登出 -> 生成总结

    注意：此函数只负责在登录时机触发会话执行，配置和工具由 executor 内部处理。

    Args:
        username: 用户名
        time_system: 时间系统实例
        user_id: 用户 ID
        ai_config_id: AI 配置 ID
        personality_prompt: 角色性格描述
        personal_signature: 个性签名
        token: 访问令牌

    Returns:
        ExecutionResult: 包含执行结果的 ExecutionResult 对象
    """
    current_scaled_time = time_system.get_scaled_time()
    print(f"[登录事件] 用户 {username} 于 {current_scaled_time} 开始会话")

    if user_id is None:
        raise ValueError(f"[登录事件] 用户 {username} 的 user_id 为 None，无法执行会话")

    agent_config = AgentConfig(
        user_id=user_id,
        username=username,
        ai_config_id=ai_config_id,
        personality_prompt=personality_prompt,
        personal_signature=personal_signature,
        token=token,
    )

    result = run_session(agent_config)

    if result.success:
        print(f"[登录事件] 用户 {username} 会话结束: {result.step_count} 步, 退出原因: {result.exit_reason}")
        if result.summary:
            narrative = result.summary.get('narrative', '') if isinstance(result.summary, dict) else result.summary.narrative
            print(f"[登录事件] 用户 {username} 总结: {narrative[:100]}...")
    else:
        print(f"[登录事件] 用户 {username} 会话异常: {result.error_message}")

    return result


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
    """

    def __init__(
        self,
        user_config: AIUserConfig,
        time_system: TimeSystem,
        admin_key: str,
        password: str,
        pre_registered_user_id: Optional[int] = None
    ):
        """
        初始化单用户调度器

        Args:
            user_config: 用户配置
            time_system: 时间系统实例
            admin_key: 管理员密钥
            password: 用户密码
            pre_registered_user_id: 预注册的用户 ID（由 RegistrationManager 注册后传入）
        """
        self.user_config = user_config
        self.time_system = time_system
        self.admin_key = admin_key
        self.password = password
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._registered_user_id: Optional[int] = pre_registered_user_id

    def _scheduling_loop(self) -> None:
        """
        调度循环

        持续运行：计算下次登录时间 -> 休眠 -> 登录 -> 设置上下文 -> 触发登录事件 -> 清理上下文 -> 重复
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

                login_success, token, login_error = login_user(username, self.password)

                if login_success and token:
                    set_current_context(AgentContext(
                        user_id=self._registered_user_id,
                        username=username,
                        ai_config_id=self.user_config.id,
                        token=token,
                        user_config={
                            "name": self.user_config.name,
                            "avatar": self.user_config.avatar,
                            "personal_signature": self.user_config.personal_signature,
                            "personality_prompt": self.user_config.personality_prompt,
                        }
                    ))

                    trigger_login_event(
                        username=username,
                        time_system=self.time_system,
                        user_id=self._registered_user_id,
                        ai_config_id=self.user_config.id,
                        personality_prompt=self.user_config.personality_prompt,
                        personal_signature=self.user_config.personal_signature,
                        token=token,
                    )

                    clear_current_context()
                else:
                    print(f"[{username}] 登录失败: {login_error}")

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
        运行流程：调度时间计算循环
        """
        if self._registered_user_id is None:
            print(f"[{self.user_config.name}] 错误：未获取到注册用户ID，跳过调度")
            return

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

class RegistrationManager:
    """
    AI 用户注册管理器

    专门负责在主线程中按顺序完成所有 AI 用户的注册流程，
    避免多线程同时注册导致 API 接口拥塞和超时问题。

    Attributes:
        time_system: 时间系统实例
        admin_key: 管理员密钥
        password: 用户密码
        registration_interval: 两次注册之间的间隔秒数
        registered_users: 已成功注册的用户字典 {user_id: registered_user_id}
        failed_users: 注册失败的用户列表
    """

    def __init__(
        self,
        time_system: TimeSystem,
        admin_key: str,
        password: str,
        registration_interval: float = 0.5
    ):
        """
        初始化注册管理器

        Args:
            time_system: 时间系统实例
            admin_key: 管理员密钥
            password: 用户密码
            registration_interval: 两次注册之间的间隔秒数，默认 0.5 秒
        """
        self.time_system = time_system
        self.admin_key = admin_key
        self.password = password
        self.registration_interval = registration_interval
        self.registered_users: Dict[int, int] = {}
        self.failed_users: List[Tuple[AIUserConfig, str]] = []
        self.newly_registered_users: set = set()

    def register_all_users(self, users: List[AIUserConfig]) -> None:
        """
        按顺序注册所有 AI 用户

        在主线程中顺序执行注册请求，每个请求之间有固定间隔，
        避免同时发送大量请求导致 API 超时。

        Args:
            users: AI 用户配置列表
        """
        total_users = len(users)
        print(f"\n[注册管理器] 开始注册 {total_users} 个 AI 用户...")
        print(f"[注册管理器] 注册间隔: {self.registration_interval} 秒")

        for index, user in enumerate(users, 1):
            username = user.username if user.username else user.name

            if not username:
                print(f"[注册管理器] 用户名为空，跳过 (配置ID: {user.id})")
                self.failed_users.append((user, "用户名为空"))
                continue

            print(f"[注册管理器] [{index}/{total_users}] 正在注册: {username}")

            success, data, error = register_ai_user(
                username=username,
                password=self.password,
                ai_config_id=user.id,
                admin_key=self.admin_key
            )

            if success:
                if error == "用户已存在（跳过）":
                    print(f"[注册管理器] [{index}/{total_users}] {username} - 用户已存在，尝试获取用户ID...")
                    existing_user_id = self._get_existing_user_id(username)
                    if existing_user_id is not None:
                        self.registered_users[user.id] = existing_user_id
                        print(f"[注册管理器] [{index}/{total_users}] {username} - 已存在用户ID: {existing_user_id}")
                    else:
                        self.failed_users.append((user, "用户已存在但无法获取用户ID"))
                        print(f"[注册管理器] [{index}/{total_users}] {username} - 用户已存在但无法获取用户ID")
                else:
                    registered_id = data.get('id') if data else None
                    self.registered_users[user.id] = registered_id
                    self.newly_registered_users.add(user.id)
                    print(f"[注册管理器] [{index}/{total_users}] {username} - 注册成功 (ID: {registered_id})")
            else:
                print(f"[注册管理器] [{index}/{total_users}] {username} - 注册失败: {error}")
                self.failed_users.append((user, error))

            if index < total_users and self.registration_interval > 0:
                time.sleep(self.registration_interval)

        success_count = len(self.registered_users)
        fail_count = len(self.failed_users)
        print(f"[注册管理器] 注册完成: 成功 {success_count}, 失败 {fail_count}")

    def update_bio_for_user(self, user: AIUserConfig, registered_user_id: int) -> bool:
        """
        为已注册用户更新简介

        Args:
            user: 用户配置
            registered_user_id: 注册后的用户 ID

        Returns:
            bool: 更新是否成功
        """
        if not user.personal_signature:
            return True

        username = user.username if user.username else user.name

        print(f"[注册管理器] 正在更新 {username} 的用户简介...")

        login_success, token, login_error = login_user(username, self.password)

        if not login_success or not token:
            print(f"[注册管理器] {username} 登录获取令牌失败: {login_error}")
            return False

        bio_success, _, bio_error = update_user_profile(
            registered_user_id,
            user.personal_signature,
            token
        )

        if bio_success:
            print(f"[注册管理器] {username} 更新用户简介成功")
            return True
        else:
            print(f"[注册管理器] {username} 更新用户简介失败: {bio_error}")
            return False

    def update_avatar_for_user(
        self,
        user: AIUserConfig,
        registered_user_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        为已注册用户上传并更新头像

        Args:
            user: 用户配置
            registered_user_id: 注册后的用户 ID

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息或头像URL)
        """
        avatar_filename = user.avatar

        if not avatar_filename or not avatar_filename.strip():
            return True, None

        if not is_valid_avatar_file(avatar_filename):
            print(f"[注册管理器] 跳过无效的头像文件: {avatar_filename}")
            return True, None

        file_path = get_avatar_file_path(avatar_filename)
        if not file_path:
            print(f"[注册管理器] 头像文件不存在: {avatar_filename}")
            return True, None

        username = user.username if user.username else user.name

        print(f"[注册管理器] 正在上传 {username} 的用户头像: {avatar_filename}")

        login_success, token, login_error = login_user(username, self.password)

        if not login_success or not token:
            print(f"[注册管理器] {username} 登录获取令牌失败: {login_error}")
            return False, login_error

        upload_success, avatar_url, upload_error = upload_avatar(
            registered_user_id,
            avatar_filename,
            token
        )

        if upload_success:
            print(f"[注册管理器] {username} 上传头像成功: {avatar_url}")
            return True, avatar_url
        else:
            print(f"[注册管理器] {username} 上传头像失败: {upload_error}")
            return False, upload_error

    def _get_existing_user_id(self, username: str) -> Optional[int]:
        """
        通过用户名登录获取已存在用户的 ID

        当用户已存在时，调用此方法通过登录流程获取用户的真实 ID。
        使用直接 API 调用，不依赖 tools 模块（tools 是 Agent 专用工具集）。

        Args:
            username: 用户名

        Returns:
            Optional[int]: 用户 ID，获取失败返回 None
        """
        login_success, token, login_error = login_user(username, self.password)

        if login_success and token:
            try:
                url = f"{API_BASE_URL}/auth/me"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    user_id = data.get("id")
                    return user_id
                else:
                    print(f"[注册管理器] 获取用户信息失败: HTTP {response.status_code}")
                    return None
            except Exception as e:
                print(f"[注册管理器] 获取用户信息异常: {e}")
                return None
        else:
            print(f"[注册管理器] 登录获取已存在用户ID失败: {login_error}")
            return None

    def update_all_bios(self, users: List[AIUserConfig]) -> None:
        """
        按顺序为新注册用户更新简介

        只有新注册的用户需要更新简介，已存在用户跳过此步骤。

        Args:
            users: AI 用户配置列表
        """
        users_to_update = [
            (user, self.registered_users.get(user.id))
            for user in users
            if user.personal_signature 
            and user.id in self.registered_users
            and user.id in self.newly_registered_users
        ]

        if not users_to_update:
            skipped_count = sum(1 for u in users if u.personal_signature and u.id in self.registered_users and u.id not in self.newly_registered_users)
            if skipped_count > 0:
                print(f"[注册管理器] 跳过 {skipped_count} 个已存在用户的简介更新")
            return

        total = len(users_to_update)
        print(f"\n[注册管理器] 开始更新 {total} 个新用户的简介...")

        for index, (user, registered_id) in enumerate(users_to_update, 1):
            if registered_id:
                username = user.username if user.username else user.name
                print(f"[注册管理器] [{index}/{total}] 更新简介: {username}")
                self.update_bio_for_user(user, registered_id)

                if index < total and self.registration_interval > 0:
                    time.sleep(self.registration_interval)

        print(f"[注册管理器] 简介更新完成")

    def update_all_avatars(self, users: List[AIUserConfig]) -> None:
        """
        按顺序为新注册用户上传头像

        只有新注册的用户需要上传头像，已存在用户跳过此步骤。

        Args:
            users: AI 用户配置列表
        """
        users_to_update = [
            (user, self.registered_users.get(user.id))
            for user in users
            if user.avatar and user.avatar.strip()
            and user.id in self.registered_users
            and user.id in self.newly_registered_users
        ]

        skipped_count = sum(
            1 for u in users
            if u.avatar and u.avatar.strip()
            and u.id in self.registered_users
            and u.id not in self.newly_registered_users
        )

        if not users_to_update:
            if skipped_count > 0:
                print(f"[注册管理器] 跳过 {skipped_count} 个已存在用户的头像上传")
            else:
                print(f"[注册管理器] 没有需要上传头像的用户")
            return

        total = len(users_to_update)
        print(f"\n[注册管理器] 开始上传 {total} 个新用户的头像...")
        if skipped_count > 0:
            print(f"[注册管理器] 跳过 {skipped_count} 个已存在用户的头像上传")

        for index, (user, registered_id) in enumerate(users_to_update, 1):
            if registered_id:
                username = user.username if user.username else user.name
                print(f"[注册管理器] [{index}/{total}] 上传头像: {username} ({user.avatar})")
                self.update_avatar_for_user(user, registered_id)

                if index < total and self.registration_interval > 0:
                    time.sleep(self.registration_interval)

        print(f"[注册管理器] 头像上传完成")

    def get_registered_user_id(self, config_id: int) -> Optional[int]:
        """
        获取配置 ID 对应的注册用户 ID

        Args:
            config_id: AI 用户配置 ID

        Returns:
            Optional[int]: 注册后的用户 ID，未注册返回 None
        """
        return self.registered_users.get(config_id)


class AgentSchedulerManager:
    """
    AI Agent 调度器管理器

    统一管理所有 AI 用户的调度器，为每个用户创建独立的调度线程。
    用户注册流程由 RegistrationManager 在主线程中顺序完成，
    调度器线程仅负责登录时间计算和事件触发。

    Attributes:
        time_system: 时间系统实例
        schedulers: 用户调度器字典
        registration_manager: 注册管理器实例
    """

    def __init__(self):
        """
        初始化调度器管理器
        """
        self.time_system = get_time_system()
        self.schedulers: Dict[int, AIUserScheduler] = {}
        self.registration_manager: Optional[RegistrationManager] = None

    def load_and_start(
        self,
        config_path: str = CONFIG_FILE_PATH,
        registration_interval: float = 0.5,
        skip_registration: bool = False
    ) -> None:
        """
        加载配置并启动所有用户的调度器

        注册流程在主线程中顺序执行，完成后再启动调度器线程。
        调度器线程会跳过已完成的注册流程，直接进入调度循环。

        注册流程包括：
        1. 用户注册
        2. 更新用户简介（personal_signature）
        3. 上传用户头像（avatar）

        Args:
            config_path: AI 用户配置文件路径
            registration_interval: 两次注册之间的间隔秒数，默认 0.5 秒
            skip_registration: 是否跳过注册流程（当用户已注册时使用）
        """
        try:
            users = load_ai_users_config(config_path)
        except Exception as e:
            print(f"[错误] 加载配置失败: {e}")
            return

        if not ADMIN_KEY:
            print("[警告] 未配置 ADMIN_KEY，将跳过用户注册")
            skip_registration = True

        if not skip_registration and ADMIN_KEY:
            self.registration_manager = RegistrationManager(
                time_system=self.time_system,
                admin_key=ADMIN_KEY,
                password=AI_USER_PASSWORD,
                registration_interval=registration_interval
            )
            self.registration_manager.register_all_users(users)
            self.registration_manager.update_all_bios(users)
            self.registration_manager.update_all_avatars(users)

        for user in users:
            registered_user_id = None
            if self.registration_manager:
                registered_user_id = self.registration_manager.get_registered_user_id(user.id)

            scheduler = AIUserScheduler(
                user_config=user,
                time_system=self.time_system,
                admin_key=ADMIN_KEY,
                password=AI_USER_PASSWORD,
                pre_registered_user_id=registered_user_id
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
    用户注册流程由 RegistrationManager 在主线程中顺序完成，
    调度器线程仅负责登录时间计算和事件触发。
    """
    print("=" * 60)
    print("Herta-Tree AI Agent 调度器")
    print("=" * 60)

    print("\n[配置信息]")
    print(f"  API 地址: {API_BASE_URL}")
    print(f"  配置文件: {CONFIG_FILE_PATH}")
    print(f"  头像目录: {get_avatar_dir()}")
    if ADMIN_KEY:
        print(f"  Admin Key: 已配置")
    else:
        print(f"  Admin Key: 未配置（将跳过用户注册，如需注册请配置 ADMIN_KEY）")

    try:
        users = load_ai_users_config(CONFIG_FILE_PATH)
        users_with_avatar = [u for u in users if u.avatar and u.avatar.strip()]
        print(f"\n[头像配置]")
        print(f"  AI 用户总数: {len(users)}")
        print(f"  有头像配置的用户数: {len(users_with_avatar)}")
    except Exception as e:
        print(f"\n[警告] 无法加载用户配置: {e}")

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



