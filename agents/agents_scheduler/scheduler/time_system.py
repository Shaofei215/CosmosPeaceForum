# 外挂时间系统模块
# 提供可被倍率缩放的时间管理功能，支持时间加速和线程安全的时间操作
import time
import threading
from datetime import datetime, timedelta
from typing import Optional


TIME_SCALE: float = 100

TIME_OFFSET_SECONDS: int = 0


class TimeSystem:
    """
    外挂时间系统类

    提供可倍率缩放的时间管理功能，支持时间加速、减速和暂停。
    所有时间操作都是线程安全的。

    Attributes:
        _lock: 线程锁，用于保证时间操作的原子性
        _scale: 当前时间倍率
        _offset: 时间偏移量（秒）
        _start_time: 系统启动时的真实时间戳
        _elapsed_scaled: 已经过的缩放时间（秒）

    Example:
        >>> ts = TimeSystem()
        >>> ts.set_scale(60.0)  # 设置为 60 倍加速
        >>> current_time = ts.get_scaled_time()
        >>> print(f"当前缩放后时间: {current_time}")
    """

    _instance: Optional['TimeSystem'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'TimeSystem':
        """
        单例模式实现

        确保全局只有一个 TimeSystem 实例，避免多实例导致的时间不一致问题

        Returns:
            TimeSystem: 单例实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """
        初始化时间系统

        仅在首次创建时初始化，后续调用会被忽略
        """
        if self._initialized:
            return

        self._lock = threading.Lock()
        self._scale: float = TIME_SCALE
        self._offset: int = TIME_OFFSET_SECONDS
        self._start_time: float = time.time()
        self._elapsed_scaled: float = 0.0
        self._paused: bool = False
        self._last_update_time: float = time.time()
        self._initialized: bool = True

    def set_scale(self, scale: float) -> None:
        """
        设置时间倍率

        Args:
            scale: 新的时间倍率，必须大于 0
                   - 1.0: 真实时间流速
                   - 60.0: 1 秒 = 1 分钟（加速）
                   - 3600.0: 1 秒 = 1 小时（快速测试）
                   - 0.1: 1 秒 = 0.1 秒（减速）
        """
        if scale <= 0:
            raise ValueError("时间倍率必须大于 0")

        with self._lock:
            self._update_elapsed_scaled()
            self._scale = scale

    def get_scale(self) -> float:
        """
        获取当前时间倍率

        Returns:
            float: 当前时间倍率
        """
        with self._lock:
            return self._scale

    def set_offset(self, offset_seconds: int) -> None:
        """
        设置时间偏移量

        Args:
            offset_seconds: 时间偏移量（秒），正值为快进，负值为回退
        """
        with self._lock:
            self._offset = offset_seconds

    def get_offset(self) -> int:
        """
        获取当前时间偏移量

        Returns:
            int: 当前时间偏移量（秒）
        """
        with self._lock:
            return self._offset

    def pause(self) -> None:
        """
        暂停时间流逝

        暂停后，时间将停留在调用时刻，直到调用 resume() 恢复
        """
        with self._lock:
            self._update_elapsed_scaled()
            self._paused = True

    def resume(self) -> None:
        """
        恢复时间流逝

        从暂停时刻继续运行
        """
        with self._lock:
            if self._paused:
                self._last_update_time = time.time()
                self._paused = False

    def is_paused(self) -> bool:
        """
        检查时间是否处于暂停状态

        Returns:
            bool: True 表示已暂停，False 表示正常运行
        """
        with self._lock:
            return self._paused

    def _update_elapsed_scaled(self) -> None:
        """
        更新已流逝的缩放时间

        在倍率变化或暂停时调用，确保缩放时间的准确性
        """
        if not self._paused:
            current_time = time.time()
            real_elapsed = current_time - self._last_update_time
            self._elapsed_scaled += real_elapsed * self._scale
            self._last_update_time = current_time

    def get_scaled_time(self) -> datetime:
        """
        获取缩放后的当前时间

        基于真实时间的流逝和设置的倍率，计算并返回缩放后的时间

        Returns:
            datetime: 缩放后的当前时间
        """
        with self._lock:
            self._update_elapsed_scaled()
            base_time = datetime(1970, 1, 1, 0, 0, 0)
            scaled_datetime = base_time + timedelta(seconds=self._elapsed_scaled + self._offset)
            return scaled_datetime

    def get_scaled_timestamp(self) -> float:
        """
        获取缩放后的时间戳

        Returns:
            float: 缩放后的 Unix 时间戳
        """
        with self._lock:
            self._update_elapsed_scaled()
            return self._elapsed_scaled + self._offset

    def get_real_time(self) -> datetime:
        """
        获取真实当前时间

        不受倍率影响，返回系统真实时间

        Returns:
            datetime: 当前真实时间
        """
        return datetime.now()

    def reset(self) -> None:
        """
        重置时间系统

        将已流逝时间清零，重置启动时间，但保持倍率和偏移设置
        """
        with self._lock:
            self._start_time = time.time()
            self._elapsed_scaled = 0.0
            self._last_update_time = time.time()
            self._paused = False

    def advance_time(self, seconds: float) -> None:
        """
        手动推进时间

        用于测试场景，手动增加指定的时间量

        Args:
            seconds: 要推进的时间量（秒），可以是分数
        """
        if seconds < 0:
            raise ValueError("推进时间量不能为负数")

        with self._lock:
            self._elapsed_scaled += seconds

    def get_elapsed_scaled_seconds(self) -> float:
        """
        获取已流逝的缩放时间（秒）

        Returns:
            float: 从系统启动到现在经过的缩放时间（秒）
        """
        with self._lock:
            self._update_elapsed_scaled()
            return self._elapsed_scaled

    def format_scaled_time(self, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        格式化缩放后的时间

        Args:
            fmt: 时间格式字符串，默认为 "%Y-%m-%d %H:%M:%S"

        Returns:
            str: 格式化后的时间字符串
        """
        return self.get_scaled_time().strftime(fmt)

    def __repr__(self) -> str:
        """
        返回时间系统的字符串表示

        Returns:
            str: 包含当前倍率、偏移和状态的字符串
        """
        with self._lock:
            status = "暂停" if self._paused else "运行中"
            return (
                f"TimeSystem(scale={self._scale}, offset={self._offset}s, "
                f"elapsed={self._elapsed_scaled:.2f}s, status={status})"
            )


def get_time_system() -> TimeSystem:
    """
    获取全局时间系统实例

    这是获取 TimeSystem 实例的标准方式，保证全局只有一个实例

    Returns:
        TimeSystem: 时间系统单例实例
    """
    return TimeSystem()


global_time_system = get_time_system()


def get_scaled_time() -> datetime:
    """
    获取缩放后的当前时间（便捷函数）

    Returns:
        datetime: 缩放后的当前时间
    """
    return global_time_system.get_scaled_time()


def get_scaled_timestamp() -> float:
    """
    获取缩放后的时间戳（便捷函数）

    Returns:
        float: 缩放后的 Unix 时间戳
    """
    return global_time_system.get_scaled_timestamp()


def set_time_scale(scale: float) -> None:
    """
    设置全局时间倍率（便捷函数）

    Args:
        scale: 新的时间倍率，必须大于 0
    """
    global_time_system.set_scale(scale)


def get_time_scale() -> float:
    """
    获取全局时间倍率（便捷函数）

    Returns:
        float: 当前时间倍率
    """
    return global_time_system.get_scale()
