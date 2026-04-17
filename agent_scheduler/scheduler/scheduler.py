"""
AI Agent 调度模块

职责：
1. 从管理数据库加载启用的 Agent 列表
2. 为每个 Agent 创建独立调度线程（AIUserScheduler）
3. 基于泊松过程计算登录间隔
4. 触发 LangGraph 会话
5. 提供 Agent 线程的启停和重启功能

不再包含：注册流程、配置管理（已迁移至 management）
"""

import json
import logging
import math
import os
import random
import time
import threading
import traceback
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from agent_scheduler.scheduler.config import get_scheduler_config
from agent_scheduler.langgraph.executor import SessionExecutor, run_session
from agent_scheduler.langgraph.config import AgentConfig as SessionAgentConfig
from agent_scheduler.scheduler.context import (
    AgentContext,
    get_current_context,
    clear_current_context,
)
from agent_scheduler.scheduler.time_system import get_time_system
from agent_scheduler.management.backend.db_client import get_db_client

logger = logging.getLogger(__name__)


def login_user(username: str, password: str) -> Optional[Dict]:
    """
    通过 app_platform API 登录用户

    Args:
        username: 用户名
        password: 密码

    Returns:
        Optional[Dict]: 用户信息，失败返回 None
    """
    try:
        from agent_scheduler.app_platform.user.user_api import login_user as platform_login
        return platform_login(username, password)
    except ImportError:
        import requests
        config = get_scheduler_config()
        url = f"{config.api_base_url}/auth/ai-login"
        response = requests.post(
            url,
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if response.status_code == 200:
            return response.json()
        logger.error(f"用户 {username} 登录失败: HTTP {response.status_code}")
        return None


class AIUserScheduler(threading.Thread):
    """
    AI 用户调度线程

    每个 Agent 独立运行在自己的线程中，循环执行：
    计算登录间隔 → 休眠 → 登录 → 触发会话 → 清理上下文

    支持运行时启停和重启。
    """

    def __init__(
        self,
        user_id: int,
        username: str,
        ai_config_id: int,
        monthly_logins: int,
        password: str,
        personality_prompt: str,
        personal_signature: str,
        time_system,
        relation_map=None,
        pre_registered_user_id: Optional[int] = None,
    ):
        super().__init__(daemon=True, name=f"AIUser-{username}")
        self.user_id = user_id
        self.username = username
        self.ai_config_id = ai_config_id
        self.monthly_logins = monthly_logins
        self.password = password
        self.personality_prompt = personality_prompt
        self.personal_signature = personal_signature
        self.time_system = time_system
        self.relation_map = relation_map
        self.pre_registered_user_id = pre_registered_user_id

        self._stop_event = threading.Event()
        self._is_active = True

        self.next_login_time = None
        self.is_logged_in = False

    def stop(self, timeout: float = 5.0):
        """停止调度线程"""
        self._is_active = False
        self._stop_event.set()
        self.join(timeout=timeout)

    def pause(self):
        """暂停调度（不退出线程）"""
        self._is_active = False

    def resume(self):
        """恢复调度"""
        self._is_active = True

    def run(self):
        """线程主循环"""
        thread_id = threading.get_ident()
        logger.info(f"[{self.username}] 调度线程启动 (ID:{thread_id})")

        try:
            self._scheduling_loop()
        except Exception as e:
            logger.error(f"[{self.username}] 调度线程异常: {e}\n{traceback.format_exc()}")
        finally:
            clear_current_context()
            logger.info(f"[{self.username}] 调度线程退出")

    def _scheduling_loop(self):
        """调度循环"""
        if self.monthly_logins <= 0:
            logger.warning(f"[{self.username}] monthly_logins={self.monthly_logins}，跳过调度")
            return

        logger.info(f"[{self.username}] 开始调度循环 (月登录次数: {self.monthly_logins})")

        while not self._stop_event.is_set():
            if not self._is_active:
                time.sleep(5)
                continue

            self.next_login_time = self._calculate_next_login_time()

            logger.info(
                f"[{self.username}] 下次登录: {self.next_login_time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"({self.time_system.to_human_readable_duration(self.next_login_time - self.time_system.now())})"
            )

            if not self._wait_until_login_time():
                continue

            self._execute_login_and_session()

    def _calculate_next_login_time(self) -> datetime:
        """使用泊松过程计算下次登录时间"""
        avg_interval_hours = 720.0 / self.monthly_logins
        interval_hours = random.expovariate(1.0 / avg_interval_hours)
        interval_hours = max(0.1, interval_hours)

        return self.time_system.now() + timedelta(hours=interval_hours)

    def _wait_until_login_time(self) -> bool:
        """休眠直到登录时间，返回 True 表示正常唤醒，False 表示被中断"""
        while not self._stop_event.is_set():
            remaining = self.next_login_time - self.time_system.now()
            if remaining.total_seconds() <= 0:
                return True

            sleep_seconds = min(30, remaining.total_seconds())
            slept = 0
            while slept < sleep_seconds and not self._stop_event.is_set():
                time.sleep(min(1, sleep_seconds - slept))
                slept += 1

            if self._stop_event.is_set():
                return False

        return not self._stop_event.is_set()

    def _execute_login_and_session(self):
        """执行登录和会话"""
        logger.info(f"[{self.username}] 开始登录")

        user_info = login_user(self.username, self.password)
        if not user_info:
            logger.error(f"[{self.username}] 登录失败，跳过本次会话")
            return

        user_id = user_info.get('id')
        token = user_info.get('token')
        logger.info(f"[{self.username}] 登录成功 (用户ID: {user_id})")

        try:
            self.is_logged_in = True
            agent_ctx = AgentContext(
                user_id=user_id,
                token=token,
                ai_config_id=self.ai_config_id,
            )
            agent_ctx.set_thread_context()

            session_cfg = SessionAgentConfig(
                user_id=user_id,
                username=self.username,
                ai_config_id=self.ai_config_id,
                personality_prompt=self.personality_prompt,
                personal_signature=self.personal_signature,
                token=token,
            )

            logger.info(f"[{self.username}] 开始 LangGraph 会话")
            result = run_session(session_cfg, self.relation_map)
            logger.info(
                f"[{self.username}] 会话完成: "
                f"步骤={result.total_steps}, "
                f"工具调用={result.total_tool_calls}, "
                f"退出原因={result.exit_reason}"
            )
        except Exception as e:
            logger.error(f"[{self.username}] 会话执行失败: {e}\n{traceback.format_exc()}")
        finally:
            self.is_logged_in = False
            clear_current_context()


class AgentSchedulerManager:
    """
    Agent 调度管理器

    职责：
    1. 从数据库加载启用的 Agent
    2. 创建和管理 AIUserScheduler 线程
    3. 提供线程的启停、重启功能
    4. 提供调度状态查询

    不再负责：注册、配置管理
    """

    def __init__(self, time_system=None):
        self.schedulers: Dict[int, AIUserScheduler] = {}
        self._thread_lock = threading.Lock()
        self._is_running = False
        self.time_system = time_system or get_time_system()
        self._relation_map = None

    def start(self, relation_map=None):
        """
        启动所有 Agent 调度线程

        流程：
        1. 从数据库加载启用的 Agent
        2. 为每个 Agent 创建 AIUserScheduler
        3. 启动调度线程

        Args:
            relation_map: 关系映射服务（可选）
        """
        if self._is_running:
            logger.warning("调度管理器已在运行中")
            return

        self._relation_map = relation_map
        self._is_running = True

        agents = get_db_client().get_agent_configs()
        if not agents:
            logger.warning("数据库中未找到启用的 Agent")
            return

        logger.info(f"从数据库加载了 {len(agents)} 个 Agent")

        for agent_data in agents:
            self._create_scheduler(agent_data)

        logger.info(f"已启动 {len(self.schedulers)} 个 Agent 调度线程")

    def stop(self):
        """停止所有 Agent 调度线程"""
        logger.info("停止所有 Agent 调度线程...")
        self._is_running = False

        with self._thread_lock:
            for scheduler in self.schedulers.values():
                scheduler.stop(timeout=5)

        self.schedulers.clear()
        logger.info("所有 Agent 调度线程已停止")

    def restart_agent(self, agent_id: int):
        """
        重启指定 Agent 的调度线程

        流程：
        1. 从 schedulers 字典中找到对应 scheduler
        2. 调用 scheduler.stop()（等待最多 5 秒）
        3. 从数据库重新加载 Agent 配置
        4. 创建新的 AIUserScheduler
        5. 替换 schedulers 字典中的旧实例
        6. 调用 scheduler.start() 启动新线程

        Args:
            agent_id: Agent ID
        """
        scheduler = self.schedulers.get(agent_id)
        if scheduler:
            logger.info(f"[重启] 停止 Agent {agent_id} 的旧调度线程...")
            scheduler.stop(timeout=5)

        agent_config = get_db_client().get_agent_config(agent_id)
        if not agent_config:
            logger.error(f"[重启] 未找到 Agent ID={agent_id} 的配置")
            return

        logger.info(f"[重启] 为 Agent {agent_config['username']} (ID:{agent_id}) 创建新调度线程...")
        self._create_scheduler(agent_config)
        logger.info(f"[重启] Agent {agent_config['username']} (ID:{agent_id}) 已重启")

    def start_agent(self, agent_id: int) -> bool:
        """
        启动单个 Agent 线程

        Args:
            agent_id: Agent ID

        Returns:
            bool: 是否成功
        """
        with self._thread_lock:
            if agent_id in self.schedulers:
                existing = self.schedulers[agent_id]
                existing.resume()
                return True

        agent_data = get_db_client().get_agent_config(agent_id)
        if not agent_data:
            return False

        return self._create_scheduler(agent_data)

    def stop_agent(self, agent_id: int) -> bool:
        """
        停止单个 Agent 线程

        Args:
            agent_id: Agent ID

        Returns:
            bool: 是否成功
        """
        with self._thread_lock:
            scheduler = self.schedulers.get(agent_id)
            if scheduler:
                scheduler.stop(timeout=5)
                del self.schedulers[agent_id]
                return True
        return False

    def get_agent_status(self, agent_id: int) -> Optional[Dict]:
        """获取单个 Agent 状态"""
        with self._thread_lock:
            scheduler = self.schedulers.get(agent_id)

        if not scheduler:
            return None

        return {
            "agent_id": agent_id,
            "username": scheduler.username,
            "is_alive": scheduler.is_alive(),
            "is_active": scheduler._is_active,
            "is_logged_in": scheduler.is_logged_in,
            "next_login_time": scheduler.next_login_time.isoformat() if scheduler.next_login_time else None,
        }

    def get_all_statuses(self) -> List[Dict]:
        """获取所有 Agent 状态"""
        statuses = []
        with self._thread_lock:
            for agent_id in list(self.schedulers.keys()):
                status = self.get_agent_status(agent_id)
                if status:
                    statuses.append(status)
        return statuses

    def _create_scheduler(self, agent_data: Dict) -> bool:
        """
        创建 AIUserScheduler 并启动

        Args:
            agent_data: Agent 配置数据

        Returns:
            bool: 是否成功
        """
        config = get_scheduler_config()

        agent_id = agent_data.get('id')
        username = agent_data.get('username', '')
        monthly_logins = agent_data.get('monthly_logins', 30)
        password = config.ai_user_password
        personality_prompt = agent_data.get('personality_prompt', '')
        personal_signature = agent_data.get('personal_signature', '')
        app_platform_user_id = agent_data.get('app_platform_user_id')

        scheduler = AIUserScheduler(
            user_id=agent_id,
            username=username,
            ai_config_id=agent_id,
            monthly_logins=monthly_logins,
            password=password,
            personality_prompt=personality_prompt,
            personal_signature=personal_signature,
            time_system=self.time_system,
            relation_map=self._relation_map,
            pre_registered_user_id=app_platform_user_id,
        )
        scheduler.start()

        with self._thread_lock:
            self.schedulers[agent_id] = scheduler

        return True
