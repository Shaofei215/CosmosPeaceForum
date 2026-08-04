import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import threading

from agents.agents_scheduler.scheduler.scheduler import (
    AIUserScheduler,
    AgentSchedulerManager,
    login_user,
)
from agents.agents_scheduler.memory.decay_scheduler import MemoryDecayScheduler


class TestLoginUser:
    def test_login_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test_token"}

        mock_me_response = MagicMock()
        mock_me_response.status_code = 200
        mock_me_response.json.return_value = {"id": 1}

        with patch("requests.request", side_effect=[mock_response, mock_me_response]):
            with patch("agents.agents_scheduler.scheduler.scheduler.get_scheduler_config") as mock_config:
                mock_config.return_value.api_base_url = "http://localhost:8000/api/v1"
                mock_config.return_value.admin_key = "admin-secret"
                result = login_user("test_user", "password")
                assert result is not None
                assert "access_token" in result

    def test_login_failure(self):
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("requests.request", return_value=mock_response):
            with patch("agents.agents_scheduler.scheduler.scheduler.get_scheduler_config") as mock_config:
                mock_config.return_value.api_base_url = "http://localhost:8000/api/v1"
                mock_config.return_value.admin_key = "admin-secret"
                result = login_user("test_user", "wrong_password")
                assert result is None

    def test_login_network_error(self):
        import requests as req
        with patch("requests.request", side_effect=req.exceptions.RequestException("Network error")):
            with patch("agents.agents_scheduler.scheduler.scheduler.get_scheduler_config") as mock_config:
                mock_config.return_value.api_base_url = "http://localhost:8000/api/v1"
                mock_config.return_value.admin_key = "admin-secret"
                result = login_user("test_user", "password")
                assert result is None


class TestAIUserScheduler:
    def test_scheduler_init(self):
        scheduler = AIUserScheduler(
            username="test_user",
            name="Test",
            agent_id=1,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="sig",
            time_system=MagicMock(),
            model_config_id=2,
        )
        assert scheduler.username == "test_user"
        assert scheduler.model_config_id == 2
        assert scheduler.monthly_logins == 30
        assert scheduler._stop_event.is_set() is False
        assert scheduler.is_logged_in is False

    def test_scheduler_stop(self):
        mock_time = MagicMock()
        mock_time.get_scaled_time.return_value = MagicMock()
        
        scheduler = AIUserScheduler(
            username="test_user",
            name="Test",
            agent_id=1,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="sig",
            time_system=mock_time,
        )
        scheduler.stop(wait=False)
        assert scheduler._stop_event.is_set() is True
        assert scheduler._stop_requested_at is not None

    def test_scheduler_stop_reports_timeout_when_thread_remains_alive(self):
        """等待结束后线程仍存活时应显式返回 ``False``。"""
        scheduler = AIUserScheduler(
            username="test_user",
            name="Test",
            agent_id=1,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="sig",
            time_system=MagicMock(),
        )
        with (
            patch.object(scheduler, "is_alive", side_effect=[True, True]),
            patch.object(scheduler, "join") as join,
        ):
            stopped = scheduler.stop(timeout=0.01, wait=True)

        assert stopped is False
        join.assert_called_once_with(timeout=0.01)

    def test_scheduler_zero_monthly_logins(self):
        mock_time = MagicMock()
        mock_time.get_scaled_time.return_value = MagicMock()
        
        scheduler = AIUserScheduler(
            username="test_user",
            name="Test",
            agent_id=1,
            monthly_logins=0,
            password="password",
            personality_prompt="friendly",
            personal_signature="sig",
            time_system=mock_time,
        )
        with patch.object(scheduler, '_scheduling_loop', side_effect=Exception("should not call")):
            pass

    def test_scheduler_calculate_next_login(self):
        from datetime import datetime, timedelta
        mock_time = MagicMock()
        mock_time.get_scaled_time.return_value = datetime.now()
        
        scheduler = AIUserScheduler(
            username="test_user",
            name="Test",
            agent_id=1,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="sig",
            time_system=mock_time,
        )
        next_time = scheduler._calculate_next_login_time()
        assert isinstance(next_time, datetime)
        assert next_time > datetime.now() - timedelta(hours=1)

    def test_sync_profile_updates_database_runtime_and_relation_map(self) -> None:
        """自助修改资料成功后应更新同一 Scheduler 后续会话使用的字段。"""

        relation_map = MagicMock()
        scheduler = AIUserScheduler(
            username="old_name",
            name="Test",
            agent_id=1,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="old signature",
            time_system=MagicMock(),
            relation_map=relation_map,
        )

        with patch("agents.agents_scheduler.scheduler.scheduler.get_db_client") as mock_db:
            mock_db.return_value.update_agent_profile.return_value = True
            synchronized = scheduler._sync_profile(
                {"id": 42, "username": "new_name", "bio": "new signature"}
            )

        assert synchronized is True
        assert scheduler.username == "new_name"
        assert scheduler.personal_signature == "new signature"
        mock_db.return_value.update_agent_profile.assert_called_once_with(
            agent_id=1,
            social_platform_user_id=42,
            username="new_name",
            personal_signature="new signature",
        )
        relation_map.build_from_db.assert_called_once_with()

    @pytest.mark.parametrize(
        "user_info",
        [
            {"access_token": "test-token"},
            {"id": 42},
            {"id": "42", "access_token": "test-token"},
            {"id": 42, "access_token": ""},
        ],
    )
    def test_execute_session_rejects_invalid_login_response(self, user_info: dict) -> None:
        """登录响应缺少有效 ID 或令牌时不应记录登录或启动会话。"""

        scheduler = AIUserScheduler(
            username="test_user",
            name="Test",
            agent_id=1,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="sig",
            time_system=MagicMock(),
            model_config_id=2,
        )

        with (
            patch(
                "agents.agents_scheduler.scheduler.scheduler.login_user",
                return_value=user_info,
            ),
            patch("agents.agents_scheduler.scheduler.scheduler.get_db_client") as mock_db,
            patch("agents.agents_scheduler.scheduler.scheduler.run_session") as mock_run_session,
        ):
            scheduler._execute_login_and_session()

        mock_db.return_value.record_agent_login.assert_not_called()
        mock_run_session.assert_not_called()
        assert scheduler.is_logged_in is False

    def test_execute_session_loads_short_term_memory_into_session_config(self) -> None:
        """每次成功登录都必须按内部角色 ID 读取当前短期记忆。"""

        time_system = MagicMock()
        time_system.get_scaled_timestamp.return_value = 900.0
        scheduler = AIUserScheduler(
            username="test_user",
            name="Test",
            agent_id=7,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="sig",
            time_system=time_system,
            model_config_id=2,
        )
        db = MagicMock()
        db.record_agent_login.return_value = {"total_login_count": 5}
        db.get_short_term_memory.return_value = {
            "content": "# 当前目标\n\n继续连载",
            "revision": 4,
            "updated_at": 800.0,
            "updated_login_count": 4,
        }

        with (
            patch(
                "agents.agents_scheduler.scheduler.scheduler.login_user",
                return_value={"id": 42, "access_token": "token"},
            ),
            patch(
                "agents.agents_scheduler.scheduler.scheduler.get_db_client",
                return_value=db,
            ),
            patch(
                "agents.agents_scheduler.scheduler.scheduler.SessionConfig.from_db",
                return_value=MagicMock(),
            ),
            patch(
                "agents.agents_scheduler.scheduler.scheduler.run_session"
            ) as run_session,
        ):
            scheduler._execute_login_and_session()

        db.get_short_term_memory.assert_called_once_with(7)
        session_config = run_session.call_args.args[0]
        assert session_config.short_term_memory == "# 当前目标\n\n继续连载"
        assert session_config.short_term_memory_revision == 4
        assert session_config.short_term_memory_updated_at == 800.0
        assert session_config.short_term_memory_updated_login_count == 4

    def test_sync_profile_rejects_non_integer_user_id(self) -> None:
        """资料同步应拒绝无法满足公开平台用户 ID 契约的数据。"""

        scheduler = AIUserScheduler(
            username="old_name",
            name="Test",
            agent_id=1,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="old signature",
            time_system=MagicMock(),
        )

        with patch("agents.agents_scheduler.scheduler.scheduler.get_db_client") as mock_db:
            synchronized = scheduler._sync_profile(
                {"id": "42", "username": "new_name", "bio": "new signature"}
            )

        assert synchronized is False
        mock_db.return_value.update_agent_profile.assert_not_called()


class TestAgentSchedulerManager:
    def test_manager_init(self):
        manager = AgentSchedulerManager()
        assert manager._is_running is False
        assert len(manager.schedulers) == 0

    def test_manager_start_no_active_agents(self):
        with patch("agents.agents_scheduler.scheduler.scheduler.get_db_client") as mock_db, \
             patch("agents.agents_scheduler.scheduler.scheduler.MemoryDecayScheduler") as mock_decay:
            mock_db.return_value.get_agent_configs.return_value = [
                {"id": 1, "username": "inactive_user", "is_active": False},
            ]
            manager = AgentSchedulerManager()
            manager.start()
            assert len(manager.schedulers) == 0
            mock_decay.return_value.start.assert_called_once_with()
            manager.stop()

    def test_manager_stop(self):
        manager = AgentSchedulerManager()
        manager._is_running = True
        manager.stop()
        assert manager._is_running is False
        assert len(manager.schedulers) == 0

    def test_get_agent_status_not_found(self):
        manager = AgentSchedulerManager()
        result = manager.get_agent_status(999)
        assert result is None

    def test_stop_agent_not_found(self):
        manager = AgentSchedulerManager()
        result = manager.stop_agent(999)
        assert result is False

    def test_start_agent_not_found(self):
        with patch("agents.agents_scheduler.scheduler.scheduler.get_db_client") as mock_db:
            mock_db.return_value.get_agent_config.return_value = None
            manager = AgentSchedulerManager()
            result = manager.start_agent(999)
            assert result is False

    def test_restart_agent_not_found(self):
        with patch("agents.agents_scheduler.scheduler.scheduler.get_db_client") as mock_db:
            mock_db.return_value.get_agent_config.return_value = None
            manager = AgentSchedulerManager()
            result = manager.restart_agent(999)
            assert result is False

    def test_get_all_statuses_empty(self):
        manager = AgentSchedulerManager()
        result = manager.get_all_statuses()
        assert result == []

    def test_create_scheduler_rejects_invalid_agent_id(self) -> None:
        """数据库配置缺少整数 Agent ID 时不应创建或登记线程。"""

        manager = AgentSchedulerManager()

        with patch("agents.agents_scheduler.scheduler.scheduler.get_scheduler_config"):
            created = manager._create_scheduler(
                {
                    "id": None,
                    "username": "test_user",
                    "name": "Test",
                }
            )

        assert created is False
        assert manager.schedulers == {}

    def test_concurrent_restart_agent_never_keeps_two_live_schedulers(self) -> None:
        """并发重启可以顺序执行，但任意时刻只能存在一个存活调度线程。"""
        live_count = 0
        max_live_count = 0
        live_lock = threading.Lock()

        class FakeScheduler:
            def __init__(self, **kwargs):
                self.agent_id = kwargs["agent_id"]
                self.alive = False
                self.stopping = False

            @property
            def is_stopping(self):
                return self.stopping and self.alive

            def start(self):
                nonlocal live_count, max_live_count
                with live_lock:
                    self.alive = True
                    live_count += 1
                    max_live_count = max(max_live_count, live_count)

            def stop(self, timeout=5, wait=True):
                nonlocal live_count
                with live_lock:
                    if self.alive:
                        self.alive = False
                        live_count -= 1
                self.stopping = True
                return True

            def is_alive(self):
                return self.alive

        agent = {
            "id": 1,
            "name": "测试角色",
            "username": "test_user",
            "is_active": True,
        }
        db = MagicMock()
        db.get_agent_config.return_value = agent

        with (
            patch("agents.agents_scheduler.scheduler.scheduler.get_db_client", return_value=db),
            patch("agents.agents_scheduler.scheduler.scheduler.get_scheduler_config") as config,
            patch("agents.agents_scheduler.scheduler.scheduler.AIUserScheduler", FakeScheduler),
        ):
            config.return_value.ai_user_password = "password"
            manager = AgentSchedulerManager(time_system=MagicMock())
            manager._is_running = True
            original = FakeScheduler(agent_id=1)
            original.start()
            manager.schedulers[1] = original

            workers = [threading.Thread(target=manager.restart_agent, args=(1,)) for _ in range(2)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=2)

            assert all(not worker.is_alive() for worker in workers)
            assert max_live_count == 1
            assert len(manager.schedulers) == 1
            assert sum(scheduler.is_alive() for scheduler in manager.schedulers.values()) == 1
            manager.stop(wait=False)

    def test_restart_timeout_defers_single_replacement_until_old_thread_exits(self) -> None:
        """停止超时后保留旧实例，待其退出后按最新配置替换一次。"""
        release_old = threading.Event()
        created = []

        class SlowScheduler:
            def __init__(self):
                self.alive = True
                self.stopping = False

            @property
            def is_stopping(self):
                return self.stopping and self.alive

            def stop(self, timeout=5, wait=True):
                self.stopping = True
                return False

            def join(self, timeout=None):
                release_old.wait(timeout)
                if release_old.is_set():
                    self.alive = False

            def is_alive(self):
                return self.alive

        class ReplacementScheduler:
            def __init__(self, **kwargs):
                self.alive = False
                self.stopping = False
                created.append(self)

            @property
            def is_stopping(self):
                return self.stopping and self.alive

            def start(self):
                self.alive = True

            def stop(self, timeout=5, wait=True):
                self.stopping = True
                self.alive = False
                return True

            def is_alive(self):
                return self.alive

        agent = {
            "id": 1,
            "name": "测试角色",
            "username": "latest_user",
            "is_active": True,
        }
        db = MagicMock()
        db.get_agent_config.return_value = agent

        with (
            patch("agents.agents_scheduler.scheduler.scheduler.get_db_client", return_value=db),
            patch("agents.agents_scheduler.scheduler.scheduler.get_scheduler_config") as config,
            patch(
                "agents.agents_scheduler.scheduler.scheduler.AIUserScheduler",
                ReplacementScheduler,
            ),
        ):
            config.return_value.ai_user_password = "password"
            manager = AgentSchedulerManager(time_system=MagicMock())
            manager._is_running = True
            old_scheduler = SlowScheduler()
            manager.schedulers[1] = old_scheduler

            assert manager.restart_agent(1) is True
            deferred_worker = manager._deferred_restarts[1]
            assert manager.schedulers[1] is old_scheduler
            assert created == []

            assert manager.restart_agent(1) is True
            assert manager._deferred_restarts[1] is deferred_worker
            release_old.set()
            deferred_worker.join(timeout=2)

            assert not deferred_worker.is_alive()
            assert len(created) == 1
            assert manager.schedulers[1] is created[0]
            assert created[0].is_alive()
            manager.stop(wait=False)

    def test_restart_inactive_agent_does_not_create_scheduler(self) -> None:
        """未启用角色的重启只收敛到停止状态。"""
        agent = {"id": 1, "name": "停用角色", "username": "inactive", "is_active": False}
        db = MagicMock()
        db.get_agent_config.return_value = agent
        manager = AgentSchedulerManager(time_system=MagicMock())
        manager._is_running = True

        with (
            patch("agents.agents_scheduler.scheduler.scheduler.get_db_client", return_value=db),
            patch.object(manager, "_create_scheduler_locked") as create_scheduler,
        ):
            assert manager.restart_agent(1) is True

        create_scheduler.assert_not_called()
        assert manager.schedulers == {}

    def test_scheduler_start_failure_rolls_back_registration(self) -> None:
        """线程启动异常后不能在管理字典中留下未启动实例。"""
        class FailingScheduler:
            def __init__(self, **kwargs):
                pass

            def is_alive(self):
                return False

            def start(self):
                raise RuntimeError("start failed")

        manager = AgentSchedulerManager(time_system=MagicMock())
        with (
            patch("agents.agents_scheduler.scheduler.scheduler.get_scheduler_config") as config,
            patch("agents.agents_scheduler.scheduler.scheduler.AIUserScheduler", FailingScheduler),
        ):
            config.return_value.ai_user_password = "password"
            created = manager._create_scheduler({"id": 1, "name": "角色", "username": "agent"})

        assert created is False
        assert manager.schedulers == {}

    def test_restart_all_requests_keep_one_worker_and_one_trailing_run(self) -> None:
        """执行中的全量重启把请求合并成至多一次尾部重启。"""
        first_started = threading.Event()
        release_first = threading.Event()
        call_count = 0
        manager = AgentSchedulerManager(time_system=MagicMock())
        manager._is_running = True

        def fake_restart_all():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                first_started.set()
                release_first.wait(timeout=2)

        with patch.object(manager, "restart_all", side_effect=fake_restart_all):
            assert manager.request_restart_all() is True
            assert first_started.wait(timeout=1)
            worker = manager._restart_all_worker
            assert worker is not None
            assert manager.request_restart_all() is True
            assert manager.request_restart_all() is True
            assert manager._restart_all_worker is worker

            release_first.set()
            worker.join(timeout=2)

        assert not worker.is_alive()
        assert call_count == 2
        assert manager._restart_all_worker is None


class TestMemoryDecayScheduler:
    """验证记忆衰减调度器与 MemoryService 的调用边界。"""

    def test_run_decay_once_calls_memory_service(self):
        """单次调度应完整等待异步衰减逻辑结束。"""
        service = MagicMock()
        service.decay_memories = AsyncMock(return_value=["deleted-memory"])
        scheduler = MemoryDecayScheduler()

        with patch(
            "agents.agents_scheduler.memory.decay_scheduler.get_memory_service",
            return_value=service,
        ):
            scheduler._run_decay_once()

        service.decay_memories.assert_awaited_once_with()
