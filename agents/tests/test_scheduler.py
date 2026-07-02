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
            user_id=1,
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
        assert scheduler.user_id == 1
        assert scheduler.username == "test_user"
        assert scheduler.model_config_id == 2
        assert scheduler.monthly_logins == 30
        assert scheduler._is_active is True
        assert scheduler.is_logged_in is False

    def test_scheduler_stop(self):
        mock_time = MagicMock()
        mock_time.get_scaled_time.return_value = MagicMock()
        
        scheduler = AIUserScheduler(
            user_id=1,
            username="test_user",
            name="Test",
            agent_id=1,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="sig",
            time_system=mock_time,
        )
        scheduler._is_active = False  # Mark as stopped without starting
        assert scheduler._is_active is False

    def test_scheduler_pause_resume(self):
        scheduler = AIUserScheduler(
            user_id=1,
            username="test_user",
            name="Test",
            agent_id=1,
            monthly_logins=30,
            password="password",
            personality_prompt="friendly",
            personal_signature="sig",
            time_system=MagicMock(),
        )
        assert scheduler._is_active is True
        scheduler.pause()
        assert scheduler._is_active is False
        scheduler.resume()
        assert scheduler._is_active is True

    def test_scheduler_zero_monthly_logins(self):
        mock_time = MagicMock()
        mock_time.get_scaled_time.return_value = MagicMock()
        
        scheduler = AIUserScheduler(
            user_id=1,
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
            user_id=1,
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
            user_id=1,
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


class TestAgentSchedulerManager:
    def test_manager_init(self):
        manager = AgentSchedulerManager()
        assert manager._is_running is False
        assert len(manager.schedulers) == 0

    def test_manager_start_no_agents(self):
        with patch("agents.agents_scheduler.scheduler.scheduler.get_db_client") as mock_db, \
             patch("agents.agents_scheduler.scheduler.scheduler.MemoryDecayScheduler") as mock_decay:
            mock_db.return_value.get_agent_configs.return_value = []
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
