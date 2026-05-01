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
)


class TestTimeSystemBasic:
    def test_singleton(self):
        ts1 = get_time_system()
        ts2 = get_time_system()
        assert ts1 is ts2

    def test_initial_scale(self):
        ts = TimeSystem.__new__(TimeSystem)
        ts._initialized = False
        ts.__init__()
        assert ts.get_scale() == 100

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
