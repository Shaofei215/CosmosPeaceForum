import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from agents.agents_scheduler.scheduler.time_system import (
    TimeSystem,
    get_time_system,
    get_scaled_time,
    get_scaled_timestamp,
    set_time_scale,
    get_time_scale,
    load_time_scale_from_db,
    parse_time_scale,
    reload_time_scale,
)


class TestTimeSystemBasic:
    @pytest.fixture(autouse=True)
    def default_time_scale(self, monkeypatch):
        """让直接重建 TimeSystem 的单测不依赖本地 management 数据库状态。"""
        monkeypatch.setattr(
            "agents.agents_scheduler.scheduler.time_system.load_time_scale_from_db",
            lambda db_client=None: 1.0,
        )

    def test_singleton(self):
        ts1 = get_time_system()
        ts2 = get_time_system()
        assert ts1 is ts2

    def test_initial_scale(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        assert ts.get_scale() == 1.0

    def test_set_scale(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        ts.set_scale(60.0)
        assert ts.get_scale() == 60.0

    def test_set_scale_invalid(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        with pytest.raises(ValueError):
            ts.set_scale(0)
        with pytest.raises(ValueError):
            ts.set_scale(-1)

    def test_set_offset(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        ts.set_offset(3600)
        assert ts.get_offset() == 3600

    def test_get_scaled_time(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        result = ts.get_scaled_time()
        assert isinstance(result, datetime)

    def test_get_scaled_timestamp(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        result = ts.get_scaled_timestamp()
        assert isinstance(result, float)

    def test_get_real_time(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        result = ts.get_real_time()
        assert isinstance(result, datetime)

    def test_reset(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        ts.advance_time(100.0)
        elapsed_before = ts.get_elapsed_scaled_seconds()
        assert elapsed_before > 0
        ts.reset()
        elapsed_after = ts.get_elapsed_scaled_seconds()
        # Allow a tiny tolerance due to time elapsed during reset
        assert elapsed_after < 1.0

    def test_advance_time(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        ts.advance_time(60.0)
        assert ts.get_elapsed_scaled_seconds() >= 60.0

    def test_advance_time_negative(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        with pytest.raises(ValueError):
            ts.advance_time(-10.0)

    def test_pause_and_resume(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        ts.pause()
        assert ts.is_paused() is True
        ts.resume()
        assert ts.is_paused() is False

    def test_format_scaled_time(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        result = ts.format_scaled_time("%Y-%m-%d")
        assert isinstance(result, str)

    def test_repr(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        result = repr(ts)
        assert "TimeSystem" in result
        assert "scale" in result


class TestTimeSystemConvenienceFunctions:
    def test_get_scaled_time_function(self):
        result = get_scaled_time()
        assert isinstance(result, datetime)

    def test_get_scaled_timestamp_function(self):
        result = get_scaled_timestamp()
        assert isinstance(result, float)

    def test_get_time_scale_function(self):
        result = get_time_scale()
        assert isinstance(result, (int, float))

    def test_set_time_scale_function(self):
        old_scale = get_time_scale()
        try:
            set_time_scale(50.0)
            assert get_time_scale() == 50.0
        finally:
            set_time_scale(old_scale)

    def test_reload_time_scale_reads_management_config(self):
        old_scale = get_time_scale()
        db = MagicMock()
        db.get_system_config.return_value = "12.5"
        try:
            with patch(
                "agents.agents_scheduler.scheduler.time_system.get_db_client",
                return_value=db,
            ):
                result = reload_time_scale()

            assert result == 12.5
            assert get_time_scale() == 12.5
            db.get_system_config.assert_called_once_with("SCHEDULER_TIME_SCALE", "1.0")
        finally:
            set_time_scale(old_scale)

    def test_parse_time_scale_rejects_invalid_values(self):
        with pytest.raises(ValueError):
            parse_time_scale("0")
        with pytest.raises(ValueError):
            parse_time_scale("-2")
        with pytest.raises(ValueError):
            parse_time_scale("not-a-number")

    def test_load_time_scale_falls_back_on_invalid_db_value(self):
        db = MagicMock()
        db.get_system_config.return_value = "invalid"

        assert load_time_scale_from_db(db) == 1.0
