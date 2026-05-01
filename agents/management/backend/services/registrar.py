"""
Management Backend - Agent 注册服务
将管理系统中的 Agent 配置注册到 app_platform

职责：
1. 单个 Agent 注册（调用 app_platform API）
2. 批量 Agent 注册
3. 头像上传
4. 个人简介更新

流程：
管理面板 → 填写表单 + 上传头像（可选）
    ↓
POST /api/agents
    ↓
management 后端：保存 Agent 配置到数据库
    ↓
registrar.service.register_agent()：
    1. 调用 app_platform API 注册用户
    2. 上传头像（如有）
    3. 返回 app_platform_user_id
    ↓
management 后端更新数据库中的 app_platform_user_id
"""

import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

from agents.management.backend.core.config import (
    SCHEDULER_INTERNAL_PORT,
)
from agents.management.backend.services.system_service import get_config_value

logger = logging.getLogger(__name__)


def _get_admin_key(db) -> str:
    """获取管理员密钥"""
    return get_config_value(db, "ADMIN_KEY", "")


def _get_ai_user_password(db) -> str:
    """获取 AI 用户默认密码"""
    return get_config_value(db, "AI_USER_PASSWORD", "ai123456")


def _get_api_base_url(db) -> str:
    """获取 app_platform API 地址"""
    return get_config_value(db, "API_BASE_URL", "http://localhost:8000/api/v1")


def _get_scheduler_internal_url() -> str:
    """获取 scheduler 内部接口地址"""
    return f"http://localhost:{SCHEDULER_INTERNAL_PORT}"


def register_agent(
    db,
    username: str,
    password: str = None,
    avatar_path: str = None,
    personal_signature: str = None,
    ai_config_id: int = None,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    注册单个 Agent 到 app_platform

    Args:
        db: 数据库会话
        username: Agent 用户名
        password: Agent 密码（可选，默认使用系统配置）
        avatar_path: 头像文件路径（可选）
        personal_signature: 个人简介（可选）
        ai_config_id: AI 配置 ID（app_platform 注册必需）

    Returns:
        (success, app_platform_user_id, error_message)
    """
    if password is None:
        password = _get_ai_user_password(db)

    api_base_url = _get_api_base_url(db)
    admin_key = _get_admin_key(db)

    if not admin_key:
        return False, None, "未配置 ADMIN_KEY，请先在系统配置中设置"

    url = f"{api_base_url}/auth/register"
    headers = {
        "X-Admin-Key": admin_key,
        "Content-Type": "application/json",
    }
    payload = {
        "username": username,
        "password": password,
        "is_ai_agent": True,
    }

    if ai_config_id is not None:
        payload["ai_config_id"] = ai_config_id

    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 201:
                data = response.json()
                user_id = data.get('id')

                if personal_signature:
                    _update_user_bio(api_base_url, username, password, personal_signature)

                if avatar_path and os.path.exists(avatar_path):
                    _upload_user_avatar(api_base_url, username, password, avatar_path)

                return True, user_id, None

            elif response.status_code == 400:
                detail = response.json().get('detail', '')
                if '已存在' in str(detail) or 'exists' in str(detail).lower():
                    return _get_existing_user_id(api_base_url, username, password, personal_signature, avatar_path)
                return False, None, f"参数错误: {detail}"

            elif response.status_code == 401:
                return False, None, "管理员密钥无效"

            else:
                logger.error("注册: HTTP %d: %s", response.status_code, response.text)

        except requests.exceptions.RequestException as e:
            logger.error("注册: 请求异常 (尝试 %d/3): %s", attempt + 1, e)

        if attempt < 2:
            wait_time = 2 ** attempt
            logger.info("注册: 等待 %d 秒后重试...", wait_time)
            time.sleep(wait_time)

    return False, None, "注册失败：达到最大重试次数"


def _get_existing_user_id(
    api_base_url: str,
    username: str,
    password: str,
    personal_signature: str = None,
    avatar_path: str = None,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """获取已存在用户的 ID 并更新信息"""
    try:
        token = _login_user(api_base_url, username, password)
        if not token:
            return False, None, "用户已存在但登录失败"

        user_id = _get_user_id(api_base_url, token)
        if user_id:
            if personal_signature:
                _update_user_bio(api_base_url, username, password, personal_signature)
            if avatar_path and os.path.exists(avatar_path):
                _upload_user_avatar(api_base_url, username, password, avatar_path)
            return True, user_id, None

        return False, None, "用户已存在但无法获取用户ID"

    except Exception as e:
        return False, None, f"获取已有用户ID失败: {e}"


def _login_user(api_base_url: str, username: str, password: str) -> Optional[str]:
    """登录获取 token"""
    login_url = f"{api_base_url}/auth/ai-login"
    try:
        response = requests.post(
            login_url,
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
    except requests.exceptions.RequestException:
        return None


def _get_user_id(api_base_url: str, token: str) -> Optional[int]:
    """获取当前用户 ID"""
    me_url = f"{api_base_url}/auth/me"
    try:
        response = requests.get(me_url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if response.status_code == 200:
            return response.json().get('id')
        return None
    except requests.exceptions.RequestException:
        return None


def _update_user_bio(api_base_url: str, username: str, password: str, bio: str) -> bool:
    """更新用户个人简介"""
    try:
        token = _login_user(api_base_url, username, password)
        if not token:
            return False

        me_url = f"{api_base_url}/auth/me"
        me_response = requests.get(me_url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if me_response.status_code != 200:
            return False

        user_id = me_response.json().get('id')
        if not user_id:
            return False

        bio_url = f"{api_base_url}/users/{user_id}"
        response = requests.put(
            bio_url,
            json={"bio": bio},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        return response.status_code == 200

    except requests.exceptions.RequestException:
        return False


def _upload_user_avatar(api_base_url: str, username: str, password: str, avatar_path: str) -> bool:
    """上传用户头像"""
    try:
        token = _login_user(api_base_url, username, password)
        if not token:
            return False

        avatar_url = f"{api_base_url}/users/avatar"
        mime_type, _ = mimetypes.guess_type(avatar_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        with open(avatar_path, 'rb') as f:
            files = {'file': (os.path.basename(avatar_path), f, mime_type)}
            response = requests.post(
                avatar_url,
                headers={"Authorization": f"Bearer {token}"},
                files=files,
                timeout=30,
            )

        return response.status_code == 200

    except requests.exceptions.RequestException:
        return False


def notify_scheduler_reload(reload_type: str, target_id: Optional[int] = None, action: str = "restart") -> bool:
    """
    通知 scheduler 重载配置

    Args:
        reload_type: system / model / agent / all
        target_id: 目标 ID（model 或 agent 类型时需要）
        action: restart / start / stop（仅 agent 类型时有效）

    Returns:
        bool: 通知是否成功
    """
    base_url = _get_scheduler_internal_url()

    if reload_type == "system":
        endpoint = "/internal/reload/system"
        payload = None
    elif reload_type == "all":
        endpoint = "/internal/reload/all"
        payload = None
    elif reload_type == "model":
        endpoint = "/internal/reload/model"
        payload = {"model_config_id": target_id} if target_id is not None else None
    elif reload_type == "agent":
        endpoint = "/internal/reload/agent"
        payload = {"agent_id": target_id, "action": action} if target_id is not None else None
    else:
        return False

    url = f"{base_url}{endpoint}"

    try:
        import json
        headers = {"Content-Type": "application/json"} if payload else {}
        body = json.dumps(payload) if payload else None
        response = requests.post(url, data=body, headers=headers, timeout=10)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.error("热更新: 通知 scheduler 失败: %s", e)
        return False


def find_avatar_file(avatar_dir: str, agent_name: str, agent_username: str) -> Optional[str]:
    """
    在头像目录中查找匹配的头像文件

    Args:
        avatar_dir: 头像目录路径
        agent_name: Agent 名称
        agent_username: Agent 用户名

    Returns:
        Optional[str]: 头像文件路径，未找到返回 None
    """
    if not os.path.exists(avatar_dir):
        return None

    for f in os.listdir(avatar_dir):
        lower_f = f.lower()
        if agent_name.lower() in lower_f or agent_username.lower() in lower_f:
            return os.path.join(avatar_dir, f)

    return None
