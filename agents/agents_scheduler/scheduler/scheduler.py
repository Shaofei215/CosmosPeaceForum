"""
角色调度模块

职责：
1. 从管理数据库加载启用的角色列表
2. 为每个角色创建独立调度线程（AIUserScheduler）
3. 基于泊松过程计算登录间隔
4. 触发 LangGraph 会话
5. 提供角色线程的启停和重启功能

"""

import logging
import random
import time
import threading
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
from agents.platform_access import PlatformAccessError, PlatformClient
from agents.logging_config import logging_context

logger = logging.getLogger(__name__)


def login_user(username: str, password: str, name: Optional[str] = None) -> Optional[Dict]:
    """
    通过 social_platform API 登录用户

    Args:
        username: 用户名
        password: 密码
        name: 用于日志展示的角色名

    Returns:
        Optional[Dict]: 用户信息，失败返回 None
    """
    try:
        config = get_scheduler_config()

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
        logger.error("%s 登录失败: %s", name or "Agent", exc)
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

        self.next_login_time = None
        self.is_logged_in = False

    @property
    def is_stopping(self) -> bool:
        """是否已经请求停止但线程尚未退出。"""
        return self._stop_event.is_set() and self.is_alive()

    def stop(self, timeout: float = 5.0, wait: bool = True) -> bool:
        """请求停止调度线程并返回线程是否已经退出。

        Args:
            timeout: 等待线程退出的最长现实秒数。
            wait: 是否等待线程退出。

        Returns:
            bool: 返回时线程已经退出则为 ``True``，否则为 ``False``。
        """
        self._stop_requested_at = datetime.now()
        self._stop_event.set()
        if wait and self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=timeout)
        return not self.is_alive()

    def run(self):
        """线程主循环"""
        with logging_context(agent_id=self.agent_id):
            logger.info("%s 调度线程启动", self.name, extra={"event": "agent.thread.start"})
            try:
                self._scheduling_loop()
            except Exception:
                logger.exception("%s 调度线程异常", self.name, extra={"event": "agent.thread.error"})
            finally:
                clear_current_context()
                logger.info("%s 调度线程退出", self.name, extra={"event": "agent.thread.stop"})

    def _scheduling_loop(self):
        """调度循环"""
        if self.monthly_logins <= 0:
            logger.warning(f"{self.name} monthly_logins={self.monthly_logins}，跳过调度")
            return

        logger.debug("%s 开始调度循环，月预期登录次数=%d", self.name, self.monthly_logins)

        while not self._stop_event.is_set():
            self.next_login_time = self._calculate_next_login_time()

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
        user_info = login_user(self.username, self.password, self.name)
        if not user_info:
            return

        user_id = user_info.get('id')
        token = user_info.get('token') or user_info.get('access_token')
        if (
            not isinstance(user_id, int)
            or isinstance(user_id, bool)
            or not isinstance(token, str)
            or not token
        ):
            logger.error("%s 登录响应缺少有效的用户 ID 或访问令牌", self.name)
            return
        logger.info("%s 登录成功", self.name)
        db_client = get_db_client()
        login_stats = db_client.record_agent_login(
            self.agent_id,
            scaled_timestamp=self.time_system.get_scaled_timestamp(),
        )
        short_term_memory = db_client.get_short_term_memory(self.agent_id)

        try:
            self.is_logged_in = True
            agent_ctx = AgentContext(
                user_id=user_id,
                username=self.username,
                token=token,
                agent_id=self.agent_id,
                user_config=login_stats,
                stop_event=self._stop_event,
                personal_signature=self.personal_signature,
                profile_sync=self._sync_profile,
                coin_balance=int(user_info.get("coin_balance", 0) or 0),
            )
            set_current_context(agent_ctx)

            session_prompt_injection = consume_prompt_injection_text(self.agent_id)
            if session_prompt_injection:
                logger.debug(
                    "%s 已消费下一次会话提示词注入: %d 字符",
                    self.name,
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
                short_term_memory=str(short_term_memory.get("content", "")),
                short_term_memory_revision=int(short_term_memory.get("revision", 0) or 0),
                short_term_memory_updated_at=short_term_memory.get("updated_at"),
                short_term_memory_updated_login_count=int(
                    short_term_memory.get("updated_login_count", 0) or 0
                ),
            )

            if self.model_config_id is None:
                raise RuntimeError(f"{self.name} 未分配模型配置")
            logger.debug("%s 使用模型配置 ID=%d", self.name, self.model_config_id)
            llm_config = SessionConfig.from_db(model_config_id=int(self.model_config_id))

            run_session(session_cfg, self.relation_map, config=llm_config)
        except Exception:
            logger.exception("%s 会话执行失败", self.name, extra={"event": "agent.session.error"})
        finally:
            self.is_logged_in = False
            clear_current_context()

    def _sync_profile(self, profile: Dict[str, object]) -> bool:
        """同步 Agent 自助修改后的公开资料到运行配置。

        Args:
            profile: social_platform 返回的最新用户资料。

        Returns:
            bool: management 数据库与当前 Scheduler 实例均同步成功时返回 ``True``。
        """

        platform_user_id = profile.get("id")
        username = profile.get("username")
        if (
            not isinstance(platform_user_id, int)
            or isinstance(platform_user_id, bool)
            or not isinstance(username, str)
            or not username
        ):
            return False
        personal_signature = profile.get("bio") or ""
        synchronized = get_db_client().update_agent_profile(
            agent_id=self.agent_id,
            social_platform_user_id=platform_user_id,
            username=username,
            personal_signature=str(personal_signature),
        )
        if not synchronized:
            return False

        self.username = str(username)
        self.personal_signature = str(personal_signature)
        current_context = get_current_context()
        if current_context is not None:
            current_context.username = self.username
            current_context.personal_signature = self.personal_signature

        if self.relation_map is not None and hasattr(self.relation_map, "build_from_db"):
            try:
                self.relation_map.build_from_db()
            except Exception:
                # 资料主链路已经提交成功；关系展示缓存可在后续热更新时恢复，
                # 不能因此触发公开平台的补偿回滚并造成 management 再次失配。
                logger.exception("%s 重建关系名称映射失败", self.name)
        return True


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
        self._lifecycle_lock = threading.RLock()
        self._thread_lock = threading.RLock()
        self._deferred_restarts: Dict[int, threading.Thread] = {}
        self._deferred_restart_targets: set[int] = set()
        self._restart_all_lock = threading.Lock()
        self._restart_all_pending = False
        self._restart_all_worker: Optional[threading.Thread] = None
        self._is_running = False
        self.time_system = time_system or get_time_system()
        self._relation_map = None
        self._memory_decay_scheduler: Optional[MemoryDecayScheduler] = None

    def start(self, relation_map=None) -> None:
        """
        启动所有 Agent 调度线程

        流程：
        1. 从数据库加载启用的 Agent
        2. 为每个 Agent 创建 AIUserScheduler
        3. 启动调度线程

        Args:
            relation_map: 关系映射服务（可选）
        """
        with self._lifecycle_lock:
            if self._is_running:
                logger.warning("调度管理器已在运行中")
                return

            self._relation_map = relation_map
            self._is_running = True
            self._start_memory_decay_scheduler()

            agents = [
                agent
                for agent in get_db_client().get_agent_configs()
                if agent.get('is_active')
            ]
            if not agents:
                logger.warning("数据库中未找到启用的角色")
                return

            logger.info("从数据库加载了 %d 个角色", len(agents))
            for agent_data in agents:
                self._start_agent_from_config_locked(agent_data)

            logger.info("已启动 %d 个角色线程", len(self.schedulers))

    def stop(self, wait: bool = True, timeout: float = 5.0) -> None:
        """停止所有角色调度线程"""
        with self._lifecycle_lock:
            logger.info("停止所有角色调度线程...")
            self._is_running = False
            self._deferred_restart_targets.clear()
            with self._restart_all_lock:
                self._restart_all_pending = False

            if self._memory_decay_scheduler is not None:
                self._memory_decay_scheduler.stop(wait=wait, timeout=timeout)
                self._memory_decay_scheduler = None

            with self._thread_lock:
                schedulers = list(self.schedulers.items())

            for agent_id, scheduler in schedulers:
                stopped = scheduler.stop(timeout=timeout, wait=wait)
                if stopped:
                    self._remove_scheduler_if_current_locked(agent_id, scheduler)

            with self._thread_lock:
                remaining = sum(scheduler.is_alive() for scheduler in self.schedulers.values())
            if remaining:
                logger.info("已发送停止请求，仍有 %d 个角色线程正在退出", remaining)
            else:
                logger.info("所有 Agent 调度线程已停止")

    def restart_agent(self, agent_id: int) -> bool:
        """
        重启指定角色的调度线程

        流程：
        1. 从数据库重新加载角色配置
        2. 安全停止已登记的旧线程
        3. 停止超时时安排唯一的延迟替换任务
        4. 未启用角色收敛到停止状态
        5. 旧线程退出后使用最新配置创建唯一的新线程

        Args:
            agent_id: Agent ID

        Returns:
            bool: 重启是否成功
        """
        with self._lifecycle_lock:
            agent_config = get_db_client().get_agent_config(agent_id)
            if not agent_config:
                logger.error("[重启] 未找到角色 ID=%d 的配置", agent_id)
                return False

            with self._thread_lock:
                self._cleanup_finished_locked()
                scheduler = self.schedulers.get(agent_id)

            if scheduler:
                if scheduler.is_stopping and agent_id in self._deferred_restarts:
                    if agent_config.get('is_active') and self._is_running:
                        self._deferred_restart_targets.add(agent_id)
                    else:
                        self._deferred_restart_targets.discard(agent_id)
                    return True

                logger.info("[重启] 停止角色 %d 的调度线程...", agent_id)
                if not scheduler.stop(timeout=5, wait=True):
                    if agent_config.get('is_active') and self._is_running:
                        self._schedule_deferred_restart_locked(agent_id, scheduler)
                    else:
                        self._deferred_restart_targets.discard(agent_id)
                    return True
                self._remove_scheduler_if_current_locked(agent_id, scheduler)

            if not self._is_running or not agent_config.get('is_active'):
                self._deferred_restart_targets.discard(agent_id)
                return True

            logger.info(
                "[重启] 为角色 %s (ID:%d) 创建新调度线程...",
                agent_config['name'],
                agent_id,
            )
            created = self._create_scheduler_locked(agent_config)
            if created:
                logger.info("[重启] 角色 %s (ID:%d) 已重启", agent_config['name'], agent_id)
            return created

    def restart_all(self) -> None:
        """
        重启所有角色的调度线程

        流程：
        1. 从数据库重新加载所有角色状态
        2. 安全停止所有现有调度线程
        3. 保留尚未退出的实例并安排延迟替换
        4. 为没有存活实例的启用角色创建唯一线程
        """
        with self._lifecycle_lock:
            if not self._is_running:
                logger.warning("[重启] 调度管理器已停止，忽略全量重启")
                return

            logger.info("[重启] 停止所有旧调度线程...")
            configs = {
                agent['id']: agent
                for agent in get_db_client().get_agent_configs()
                if isinstance(agent.get('id'), int)
                and not isinstance(agent.get('id'), bool)
            }
            active_configs = {
                agent_id: agent
                for agent_id, agent in configs.items()
                if agent.get('is_active')
            }
            with self._thread_lock:
                self._cleanup_finished_locked()
                schedulers = list(self.schedulers.items())

            for agent_id, scheduler in schedulers:
                if scheduler.stop(timeout=5, wait=True):
                    self._remove_scheduler_if_current_locked(agent_id, scheduler)
                elif agent_id in active_configs:
                    self._schedule_deferred_restart_locked(agent_id, scheduler)
                else:
                    self._deferred_restart_targets.discard(agent_id)

            if not active_configs:
                logger.warning("[重启] 数据库中未找到启用的角色")
                return

            logger.info("[重启] 从数据库加载了 %d 个角色", len(active_configs))
            for agent_data in active_configs.values():
                self._start_agent_from_config_locked(agent_data)

            logger.info("[重启] 当前登记 %d 个角色调度线程", len(self.schedulers))

    def request_restart_all(self) -> bool:
        """合并提交全量角色重启请求。

        Returns:
            bool: 管理器运行中且请求已接受时返回 ``True``。
        """
        with self._lifecycle_lock:
            if not self._is_running:
                return False
            with self._restart_all_lock:
                self._restart_all_pending = True
                if self._restart_all_worker and self._restart_all_worker.is_alive():
                    return True
                worker = threading.Thread(
                    target=self._drain_restart_all_requests,
                    name="scheduler-reload-all",
                    daemon=True,
                )
                self._restart_all_worker = worker
                worker.start()
                return True

    def _drain_restart_all_requests(self) -> None:
        """串行消费全量重启请求，并将执行期间的请求合并为一次尾部重启。"""
        current_thread = threading.current_thread()
        try:
            while True:
                with self._restart_all_lock:
                    if not self._restart_all_pending:
                        if self._restart_all_worker is current_thread:
                            self._restart_all_worker = None
                        return
                    self._restart_all_pending = False
                self.restart_all()
        except Exception:
            logger.exception("[重启] 全量角色重启工作线程异常")
        finally:
            with self._restart_all_lock:
                if self._restart_all_worker is current_thread:
                    self._restart_all_worker = None

    def start_agent(self, agent_id: int) -> bool:
        """
        启动单个角色线程

        Args:
            agent_id: 角色 ID

        Returns:
            bool: 是否成功
        """
        with self._lifecycle_lock:
            if not self._is_running:
                return False
            agent_data = get_db_client().get_agent_config(agent_id)
            if not agent_data or not agent_data.get('is_active'):
                return False
            return self._start_agent_from_config_locked(agent_data)

    def stop_agent(self, agent_id: int) -> bool:
        """
        停止单个角色线程

        Args:
            agent_id: 角色 ID

        Returns:
            bool: 是否成功
        """
        with self._lifecycle_lock:
            agent_data = get_db_client().get_agent_config(agent_id)
            with self._thread_lock:
                self._cleanup_finished_locked()
                scheduler = self.schedulers.get(agent_id)
            if not agent_data and scheduler is None:
                return False

            self._deferred_restart_targets.discard(agent_id)
            if scheduler and scheduler.stop(timeout=0, wait=False):
                self._remove_scheduler_if_current_locked(agent_id, scheduler)
            return True

    def start_agents(self, agent_ids: Iterable[int]) -> Dict[int, bool]:
        """批量启动角色线程。"""
        return {agent_id: self.start_agent(agent_id) for agent_id in agent_ids}

    def stop_agents(self, agent_ids: Iterable[int]) -> Dict[int, bool]:
        """批量停止角色线程。"""
        return {agent_id: self.stop_agent(agent_id) for agent_id in agent_ids}

    def get_agent_status(self, agent_id: int) -> Optional[Dict]:
        """获取单个角色状态"""
        with self._thread_lock:
            self._cleanup_finished_locked()
            scheduler = self.schedulers.get(agent_id)

        if not scheduler:
            return None

        return {
            "agent_id": agent_id,
            "username": scheduler.username,
            "is_alive": scheduler.is_alive(),
            "is_active": not scheduler._stop_event.is_set(),
            "is_logged_in": scheduler.is_logged_in,
            "is_stopping": scheduler.is_stopping,
            "status": self._get_scheduler_status_label(scheduler),
            "stop_requested_at": (
                scheduler._stop_requested_at.isoformat() if scheduler._stop_requested_at else None
            ),
            "next_login_time": scheduler.next_login_time.isoformat() if scheduler.next_login_time else None,
        }

    def get_all_statuses(self) -> List[Dict]:
        """获取所有角色状态"""
        statuses = []
        with self._thread_lock:
            self._cleanup_finished_locked()
            schedulers = list(self.schedulers.items())

        for agent_id, scheduler in schedulers:
            statuses.append({
                "agent_id": agent_id,
                "username": scheduler.username,
                "is_alive": scheduler.is_alive(),
                "is_active": not scheduler._stop_event.is_set(),
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

    def _cleanup_finished_locked(self) -> None:
        """清理已退出的线程；调用方需持有 _thread_lock。"""
        stopped_ids = [
            agent_id
            for agent_id, scheduler in self.schedulers.items()
            if not scheduler.is_alive()
        ]
        for agent_id in stopped_ids:
            del self.schedulers[agent_id]

    def _remove_scheduler_if_current_locked(
        self,
        agent_id: int,
        scheduler: AIUserScheduler,
    ) -> None:
        """仅当登记实例仍是目标线程时移除它。

        Args:
            agent_id: 角色内部 ID。
            scheduler: 预期移除的调度线程实例。
        """
        with self._thread_lock:
            if self.schedulers.get(agent_id) is scheduler:
                del self.schedulers[agent_id]

    def _start_agent_from_config_locked(self, agent_data: Dict) -> bool:
        """在生命周期锁内依据配置幂等启动角色。

        Args:
            agent_data: 最新角色配置。

        Returns:
            bool: 已运行、已安排延迟启动或成功创建时返回 ``True``。
        """
        raw_agent_id = agent_data.get('id')
        if not isinstance(raw_agent_id, int) or isinstance(raw_agent_id, bool):
            return False
        agent_id = raw_agent_id
        if not self._is_running or not agent_data.get('is_active'):
            return False

        with self._thread_lock:
            self._cleanup_finished_locked()
            scheduler = self.schedulers.get(agent_id)
        if scheduler:
            if scheduler.is_stopping:
                self._schedule_deferred_restart_locked(agent_id, scheduler)
            return True
        return self._create_scheduler_locked(agent_data)

    def _schedule_deferred_restart_locked(
        self,
        agent_id: int,
        scheduler: AIUserScheduler,
    ) -> None:
        """为停止中的角色安排唯一的延迟替换任务。

        Args:
            agent_id: 角色内部 ID。
            scheduler: 必须先退出的旧调度线程。
        """
        self._deferred_restart_targets.add(agent_id)
        existing = self._deferred_restarts.get(agent_id)
        if existing and existing.is_alive():
            return

        worker = threading.Thread(
            target=self._restart_after_exit,
            args=(agent_id, scheduler),
            name=f"scheduler-restart-{agent_id}",
            daemon=True,
        )
        self._deferred_restarts[agent_id] = worker
        worker.start()
        logger.info("[重启] 角色 ID=%d 将在旧线程退出后应用最新配置", agent_id)

    def _restart_after_exit(self, agent_id: int, scheduler: AIUserScheduler) -> None:
        """等待旧线程退出后按最新数据库状态完成延迟替换。

        Args:
            agent_id: 角色内部 ID。
            scheduler: 等待退出的旧调度线程。
        """
        scheduler.join()
        current_thread = threading.current_thread()
        with self._lifecycle_lock:
            should_restart = agent_id in self._deferred_restart_targets
            self._deferred_restart_targets.discard(agent_id)
            if self._deferred_restarts.get(agent_id) is current_thread:
                del self._deferred_restarts[agent_id]

            self._remove_scheduler_if_current_locked(agent_id, scheduler)
            with self._thread_lock:
                current_scheduler = self.schedulers.get(agent_id)
            if current_scheduler is not None or not should_restart or not self._is_running:
                return

            agent_data = get_db_client().get_agent_config(agent_id)
            if not agent_data or not agent_data.get('is_active'):
                return
            if self._create_scheduler_locked(agent_data):
                logger.info("[重启] 角色 ID=%d 已在旧线程退出后完成重启", agent_id)

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
        if scheduler.is_alive():
            return "running"
        return "stopped"

    def _create_scheduler(self, agent_data: Dict) -> bool:
        """
        创建 AIUserScheduler 并启动

        Args:
            agent_data: 角色配置数据

        Returns:
            bool: 是否成功
        """
        with self._lifecycle_lock:
            return self._create_scheduler_locked(agent_data)

    def _create_scheduler_locked(self, agent_data: Dict) -> bool:
        """在生命周期锁内原子登记并启动角色调度线程。

        Args:
            agent_data: 角色配置数据。

        Returns:
            bool: 成功启动并登记时返回 ``True``。
        """
        config = get_scheduler_config()

        raw_agent_id = agent_data.get('id')
        if not isinstance(raw_agent_id, int) or isinstance(raw_agent_id, bool):
            logger.error("无法创建 Agent 调度器：缺少有效的整数 ID")
            return False
        agent_id = raw_agent_id
        name = agent_data.get('name', '')
        username = agent_data.get('username', '')
        monthly_logins = agent_data.get('monthly_logins', 30)
        password = config.ai_user_password
        personality_prompt = agent_data.get('personality_prompt', '')
        personal_signature = agent_data.get('personal_signature', '')
        social_platform_user_id = agent_data.get('social_platform_user_id')
        model_config_id = agent_data.get('model_config_id')

        scheduler = AIUserScheduler(
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
        with self._thread_lock:
            self._cleanup_finished_locked()
            if agent_id in self.schedulers:
                logger.warning("无法创建 Agent 调度器：角色 ID=%d 已有线程", agent_id)
                return False
            self.schedulers[agent_id] = scheduler
            try:
                scheduler.start()
            except Exception:
                if self.schedulers.get(agent_id) is scheduler:
                    del self.schedulers[agent_id]
                logger.exception("角色 ID=%d 调度线程启动失败", agent_id)
                return False

        return True
