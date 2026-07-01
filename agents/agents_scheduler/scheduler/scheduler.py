"""
AI Agent 调度模块

职责：
1. 从管理数据库加载启用的 Agent 列表
2. 为每个 Agent 创建独立调度线程（AIUserScheduler）
3. 基于泊松过程计算登录间隔
4. 触发 LangGraph 会话
5. 提供 Agent 线程的启停和重启功能

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
from typing import Dict, Optional, List, Iterable

from agents.agents_scheduler.scheduler.config import get_scheduler_config
from agents.agents_scheduler.langgraph.executor import SessionExecutor, run_session
from agents.agents_scheduler.langgraph.config import AgentConfig as SessionAgentConfig, SessionConfig
from agents.agents_scheduler.scheduler.context import (
    AgentContext,
    get_current_context,
    set_current_context,
    clear_current_context,
)
from agents.agents_scheduler.scheduler.session_injections import consume_prompt_injection_text
from agents.agents_scheduler.scheduler.time_system import get_time_system
from agents.agents_scheduler.memory.decay_scheduler import MemoryDecayScheduler
from agents.management.backend.db_client import get_db_client

logger = logging.getLogger(__name__)


def login_user(username: str, password: str) -> Optional[Dict]:
    """
    通过 social_platform API 登录用户

    Args:
        username: 用户名
        password: 密码

    Returns:
        Optional[Dict]: 用户信息，失败返回 None
    """
    try:
        config = get_scheduler_config()
        from agents.platform_access import PlatformAccessError, PlatformClient

        client = PlatformClient(
            base_url=config.api_base_url,
            admin_key=config.admin_key,
            timeout_seconds=10,
        )
        result = client.request(
            "POST",
            "/auth/internal-agent-login",
            access_token=None,
            json_data={"username": username, "password": password},
        )
        token = result.get("access_token")
        if token:
            user_info = client.request("GET", "/auth/me", access_token=token)
            result["id"] = user_info.get("id")
        return result
    except PlatformAccessError as exc:
        logger.error("用户 %s 登录失败: %s", username, exc)
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
        name: str,
        agent_id: int,
        monthly_logins: int,
        password: str,
        personality_prompt: str,
        personal_signature: str,
        time_system,
        relation_map=None,
        pre_registered_user_id: Optional[int] = None,
        model_config_id: Optional[int] = None,
    ):
        super().__init__(daemon=True, name=f"AIUser-{username}")
        self.user_id = user_id
        self.username = username
        self.name = name
        self.agent_id = agent_id
        self.monthly_logins = monthly_logins
        self.password = password
        self.personality_prompt = personality_prompt
        self.personal_signature = personal_signature
        self.time_system = time_system
        self.relation_map = relation_map
        self.pre_registered_user_id = pre_registered_user_id
        self.model_config_id = model_config_id

        self._stop_event = threading.Event()
        self._stop_requested_at: Optional[datetime] = None
        self._is_active = True

        self.next_login_time = None
        self.is_logged_in = False

    @property
    def is_stopping(self) -> bool:
        """是否已经请求停止但线程尚未退出。"""
        return self._stop_event.is_set() and self.is_alive()

    def stop(self, timeout: float = 5.0, wait: bool = True):
        """停止调度线程"""
        self._is_active = False
        self._stop_requested_at = datetime.now()
        self._stop_event.set()
        if wait and self.is_alive() and threading.current_thread() is not self:
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
                f"[{self.username}] 下次登录: {self.next_login_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if not self._wait_until_login_time():
                continue

            self._execute_login_and_session()

    def _calculate_next_login_time(self) -> datetime:
        """使用泊松过程计算下次登录时间"""
        avg_interval_hours = 720.0 / self.monthly_logins
        interval_hours = random.expovariate(1.0 / avg_interval_hours)
        interval_hours = max(0.1, interval_hours)

        return self.time_system.get_scaled_time() + timedelta(hours=interval_hours)

    def _wait_until_login_time(self) -> bool:
        """休眠直到登录时间，返回 True 表示正常唤醒，False 表示被中断"""
        while not self._stop_event.is_set():
            remaining = self.next_login_time - self.time_system.get_scaled_time()
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
        token = user_info.get('token') or user_info.get('access_token')
        if user_id:
            logger.info(f"[{self.username}] 登录成功 (用户ID: {user_id})")
        else:
            logger.info(f"[{self.username}] 登录成功")
        login_stats = get_db_client().record_agent_login(
            self.agent_id,
            scaled_timestamp=self.time_system.get_scaled_timestamp(),
        )

        try:
            self.is_logged_in = True
            agent_ctx = AgentContext(
                user_id=user_id,
                token=token,
                agent_id=self.agent_id,
                user_config=login_stats,
                stop_event=self._stop_event,
            )
            set_current_context(agent_ctx)

            session_prompt_injection = consume_prompt_injection_text(self.agent_id)
            if session_prompt_injection:
                logger.info(
                    "[%s] 已消费下一次会话提示词注入: %d 字符",
                    self.username,
                    len(session_prompt_injection),
                )

            session_cfg = SessionAgentConfig(
                user_id=user_id,
                username=self.username,
                name=self.name,
                agent_id=self.agent_id,
                personality_prompt=self.personality_prompt,
                personal_signature=self.personal_signature,
                token=token,
                session_prompt_injection=session_prompt_injection,
            )

            if self.model_config_id is None:
                raise RuntimeError(f"Agent {self.username} 未分配模型配置")
            logger.info("[%s] 使用模型配置 ID=%d", self.username, self.model_config_id)
            llm_config = SessionConfig.from_db(model_config_id=int(self.model_config_id))

            logger.info(f"[{self.username}] 开始 LangGraph 会话")
            result = run_session(session_cfg, self.relation_map, config=llm_config)
            logger.info(
                f"[{self.username}] 会话完成: "
                f"步骤={result.step_count}, "
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

    """

    def __init__(self, time_system=None):
        self.schedulers: Dict[int, AIUserScheduler] = {}
        self._thread_lock = threading.RLock()
        self._is_running = False
        self.time_system = time_system or get_time_system()
        self._relation_map = None
        self._memory_decay_scheduler: Optional[MemoryDecayScheduler] = None

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
        self._start_memory_decay_scheduler()

        agents = get_db_client().get_agent_configs()
        if not agents:
            logger.warning("数据库中未找到启用的 Agent")
            return

        logger.info(f"从数据库加载了 {len(agents)} 个 Agent")

        for agent_data in agents:
            self._create_scheduler(agent_data)

        logger.info(f"已启动 {len(self.schedulers)} 个 Agent 调度线程")

    def stop(self, wait: bool = True, timeout: float = 5.0):
        """停止所有 Agent 调度线程"""
        logger.info("停止所有 Agent 调度线程...")
        self._is_running = False

        if self._memory_decay_scheduler is not None:
            self._memory_decay_scheduler.stop(wait=wait, timeout=timeout)
            self._memory_decay_scheduler = None

        with self._thread_lock:
            schedulers = list(self.schedulers.values())

        for scheduler in schedulers:
            scheduler.stop(timeout=timeout, wait=wait)

        if wait:
            with self._thread_lock:
                self.schedulers.clear()
            logger.info("所有 Agent 调度线程已停止")
        else:
            logger.info("已向所有 Agent 调度线程发送停止请求")

    def restart_agent(self, agent_id: int) -> bool:
        """
        重启指定 Agent 的调度线程

        流程：
        1. 从数据库重新加载 Agent 配置
        2. 从 schedulers 字典中找到对应 scheduler
        3. 调用 scheduler.stop()（等待最多 5 秒）
        4. 创建新的 AIUserScheduler
        5. 替换 schedulers 字典中的旧实例
        6. 调用 scheduler.start() 启动新线程

        Args:
            agent_id: Agent ID

        Returns:
            bool: 重启是否成功
        """
        agent_config = get_db_client().get_agent_config(agent_id)
        if not agent_config:
            logger.error(f"[重启] 未找到 Agent ID={agent_id} 的配置")
            return False

        with self._thread_lock:
            scheduler = self.schedulers.get(agent_id)
            if scheduler:
                logger.info(f"[重启] 停止 Agent {agent_id} 的旧调度线程...")
                scheduler.stop(timeout=5, wait=True)
                self.schedulers.pop(agent_id, None)

        logger.info(f"[重启] 为 Agent {agent_config['username']} (ID:{agent_id}) 创建新调度线程...")
        self._create_scheduler(agent_config)
        logger.info(f"[重启] Agent {agent_config['username']} (ID:{agent_id}) 已重启")
        return True

    def restart_all(self):
        """
        重启所有 Agent 的调度线程

        流程：
        1. 停止所有现有调度线程
        2. 清空 schedulers 字典
        3. 从数据库重新加载所有启用的 Agent
        4. 为每个 Agent 创建新的调度线程
        """
        logger.info("[重启] 停止所有旧调度线程...")
        self._is_running = False
        with self._thread_lock:
            schedulers = list(self.schedulers.values())

        for scheduler in schedulers:
            scheduler.stop(timeout=5, wait=True)

        with self._thread_lock:
            self.schedulers.clear()

        self._is_running = True
        agents = get_db_client().get_agent_configs()
        if not agents:
            logger.warning("[重启] 数据库中未找到启用的 Agent")
            return

        logger.info(f"[重启] 从数据库加载了 {len(agents)} 个 Agent")
        for agent_data in agents:
            self._create_scheduler(agent_data)

        logger.info(f"[重启] 已重启 {len(self.schedulers)} 个 Agent 调度线程")

    def start_agent(self, agent_id: int) -> bool:
        """
        启动单个 Agent 线程

        Args:
            agent_id: Agent ID

        Returns:
            bool: 是否成功
        """
        with self._thread_lock:
            self._cleanup_finished_locked()
            if agent_id in self.schedulers:
                existing = self.schedulers[agent_id]
                if existing.is_stopping:
                    logger.warning(f"[启动] Agent ID={agent_id} 正在停止中，暂不重复启动")
                    return False
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
            self._cleanup_finished_locked()
            scheduler = self.schedulers.get(agent_id)
            if scheduler:
                scheduler.stop(timeout=0, wait=False)
                if not scheduler.is_alive():
                    del self.schedulers[agent_id]
                return True
        return False

    def start_agents(self, agent_ids: Iterable[int]) -> Dict[int, bool]:
        """批量启动 Agent 线程。"""
        return {agent_id: self.start_agent(agent_id) for agent_id in agent_ids}

    def stop_agents(self, agent_ids: Iterable[int]) -> Dict[int, bool]:
        """批量停止 Agent 线程。"""
        return {agent_id: self.stop_agent(agent_id) for agent_id in agent_ids}

    def get_agent_status(self, agent_id: int) -> Optional[Dict]:
        """获取单个 Agent 状态"""
        with self._thread_lock:
            self._cleanup_finished_locked()
            scheduler = self.schedulers.get(agent_id)

        if not scheduler:
            return None

        return {
            "agent_id": agent_id,
            "username": scheduler.username,
            "is_alive": scheduler.is_alive(),
            "is_active": scheduler._is_active,
            "is_logged_in": scheduler.is_logged_in,
            "is_stopping": scheduler.is_stopping,
            "status": self._get_scheduler_status_label(scheduler),
            "stop_requested_at": (
                scheduler._stop_requested_at.isoformat() if scheduler._stop_requested_at else None
            ),
            "next_login_time": scheduler.next_login_time.isoformat() if scheduler.next_login_time else None,
        }

    def get_all_statuses(self) -> List[Dict]:
        """获取所有 Agent 状态"""
        statuses = []
        with self._thread_lock:
            self._cleanup_finished_locked()
            schedulers = list(self.schedulers.items())

        for agent_id, scheduler in schedulers:
            statuses.append({
                "agent_id": agent_id,
                "username": scheduler.username,
                "is_alive": scheduler.is_alive(),
                "is_active": scheduler._is_active,
                "is_logged_in": scheduler.is_logged_in,
                "is_stopping": scheduler.is_stopping,
                "status": self._get_scheduler_status_label(scheduler),
                "stop_requested_at": (
                    scheduler._stop_requested_at.isoformat() if scheduler._stop_requested_at else None
                ),
                "next_login_time": (
                    scheduler.next_login_time.isoformat() if scheduler.next_login_time else None
                ),
            })
        return statuses

    def _cleanup_finished_locked(self):
        """清理已退出的线程；调用方需持有 _thread_lock。"""
        stopped_ids = [
            agent_id
            for agent_id, scheduler in self.schedulers.items()
            if not scheduler.is_alive()
        ]
        for agent_id in stopped_ids:
            del self.schedulers[agent_id]

    def _start_memory_decay_scheduler(self) -> None:
        """
        启动由管理器唯一持有的记忆衰减线程。

        Returns:
            None: 线程已运行或启动完成后直接返回。
        """
        if (
            self._memory_decay_scheduler is not None
            and self._memory_decay_scheduler.is_alive()
        ):
            return

        self._memory_decay_scheduler = MemoryDecayScheduler()
        self._memory_decay_scheduler.start()

    @staticmethod
    def _get_scheduler_status_label(scheduler: AIUserScheduler) -> str:
        if scheduler.is_stopping:
            return "stopping"
        if scheduler.is_logged_in:
            return "in_session"
        if scheduler.is_alive() and scheduler._is_active:
            return "running"
        if scheduler.is_alive():
            return "paused"
        return "stopped"

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
        name = agent_data.get('name', '')
        username = agent_data.get('username', '')
        monthly_logins = agent_data.get('monthly_logins', 30)
        password = config.ai_user_password
        personality_prompt = agent_data.get('personality_prompt', '')
        personal_signature = agent_data.get('personal_signature', '')
        social_platform_user_id = agent_data.get('social_platform_user_id')
        model_config_id = agent_data.get('model_config_id')

        scheduler = AIUserScheduler(
            user_id=agent_id,
            username=username,
            name=name,
            agent_id=agent_id,
            monthly_logins=monthly_logins,
            password=password,
            personality_prompt=personality_prompt,
            personal_signature=personal_signature,
            time_system=self.time_system,
            relation_map=self._relation_map,
            pre_registered_user_id=social_platform_user_id,
            model_config_id=model_config_id,
        )
        scheduler.start()

        with self._thread_lock:
            self.schedulers[agent_id] = scheduler

        return True
