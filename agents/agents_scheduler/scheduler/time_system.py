# 外挂时间系统模块
# 提供可被倍率缩放的时间管理功能，支持时间加速和线程安全的时间操作
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Optional

from agents.management.backend.db_client import ManagementDBClient, get_db_client


logger = logging.getLogger(__name__)

TIME_SCALE_CONFIG_KEY: str = "SCHEDULER_TIME_SCALE"

TIME_SCALE: float = 1.0

TIME_OFFSET_SECONDS: int = 0


def parse_time_scale(value: str | None, default: float = TIME_SCALE) -> float:
    """
    解析系统配置表中的时间倍率。

    Args:
        value: system_configs 中保存的倍率字符串。
        default: 配置缺失或非法时使用的默认倍率。

    Returns:
        float: 大于 0 的时间倍率。

    Raises:
        ValueError: 当 value 无法转换为正数时抛出。
    """
    if value is None or value.strip() == "":
        return default

    scale = float(value)
    if scale <= 0:
        raise ValueError("时间倍率必须大于 0")
    return scale


def load_time_scale_from_db(db_client: ManagementDBClient | None = None) -> float:
    """
    从 management 系统配置表加载 scheduler 时间倍率。

    Args:
        db_client: 可选的 management 数据库客户端，测试时可注入。

    Returns:
        float: 从系统配置表解析出的时间倍率，配置缺失或读取失败时返回现实时间倍率。
    """
    client = db_client or get_db_client()
    raw_value = client.get_system_config(TIME_SCALE_CONFIG_KEY, str(TIME_SCALE))
    try:
        return parse_time_scale(raw_value, TIME_SCALE)
    except (TypeError, ValueError) as exc:
        logger.warning(
            "系统配置 %s=%r 非法，已回退到默认时间倍率 %.1f: %s",
            TIME_SCALE_CONFIG_KEY,
            raw_value,
            TIME_SCALE,
            exc,
        )
        return TIME_SCALE


def load_scheduler_time_state(
    db_client: ManagementDBClient | None = None,
) -> dict | None:
    """
    从 management 数据库读取缩放时间持久化锚点。

    Args:
        db_client: 可选的 management 数据库客户端，测试时可注入。

    Returns:
        dict | None: 持久化锚点；尚未建立锚点时返回 ``None``。
    """
    client = db_client or get_db_client()
    return client.get_scheduler_time_state()


def save_scheduler_time_state(
    scaled_timestamp: float,
    real_timestamp: float,
    scale: float,
    offset_seconds: int,
    paused: bool,
    db_client: ManagementDBClient | None = None,
) -> bool:
    """
    将当前缩放时间锚点写入 management 数据库。

    Args:
        scaled_timestamp: 当前缩放时间戳。
        real_timestamp: 当前真实 Unix 时间戳。
        scale: 当前时间倍率。
        offset_seconds: 当前显式偏移秒数。
        paused: 时间轴是否暂停。
        db_client: 可选的 management 数据库客户端，测试时可注入。

    Returns:
        bool: 写入成功时返回 ``True``。
    """
    client = db_client or get_db_client()
    return client.save_scheduler_time_state(
        scaled_timestamp=scaled_timestamp,
        real_timestamp=real_timestamp,
        scale=scale,
        offset_seconds=offset_seconds,
        paused=paused,
    )


def load_legacy_scheduler_time_baseline(
    db_client: ManagementDBClient | None = None,
) -> float:
    """
    读取首次升级时可用于承接旧排程的最大 Agent 登录时间戳。

    Args:
        db_client: 可选的 management 数据库客户端，测试时可注入。

    Returns:
        float: 历史缩放时间基线；无历史数据时返回 ``0.0``。
    """
    client = db_client or get_db_client()
    return client.get_latest_agent_login_timestamp()


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
        configured_scale = load_time_scale_from_db()
        current_real_time = time.time()
        persisted_state = load_scheduler_time_state()

        self._scale: float = configured_scale
        self._offset: int = TIME_OFFSET_SECONDS
        self._start_time: float = current_real_time
        self._elapsed_scaled: float = 0.0
        self._paused: bool = False
        self._last_update_time: float = current_real_time

        if persisted_state is not None:
            saved_offset = int(persisted_state.get("offset_seconds", 0))
            saved_scaled_timestamp = float(persisted_state["scaled_timestamp"])
            saved_real_timestamp = float(persisted_state["real_timestamp"])
            saved_scale = float(persisted_state["scale"])
            saved_paused = bool(persisted_state.get("paused", False))
            real_delta = max(0.0, current_real_time - saved_real_timestamp)
            resumed_scaled_timestamp = saved_scaled_timestamp
            if not saved_paused:
                resumed_scaled_timestamp += real_delta * saved_scale

            self._offset = saved_offset
            self._elapsed_scaled = resumed_scaled_timestamp - saved_offset
            self._paused = saved_paused
        else:
            legacy_baseline = load_legacy_scheduler_time_baseline()
            if legacy_baseline > 0:
                self._elapsed_scaled = legacy_baseline - self._offset

        self._initialized: bool = True
        self._persist_state_locked()

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
            self._persist_state_locked()

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
            self._update_elapsed_scaled()
            self._offset = offset_seconds
            self._persist_state_locked()

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
            self._persist_state_locked()

    def resume(self) -> None:
        """
        恢复时间流逝

        从暂停时刻继续运行
        """
        with self._lock:
            if self._paused:
                self._last_update_time = time.time()
                self._paused = False
                self._persist_state_locked()

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
            real_elapsed = max(0.0, current_time - self._last_update_time)
            self._elapsed_scaled += real_elapsed * self._scale
            if current_time >= self._last_update_time:
                self._last_update_time = current_time

    def _persist_state_locked(self) -> None:
        """
        持久化当前时间锚点；调用方必须持有实例锁或处于初始化阶段。

        Returns:
            None: 写入成功或记录警告后直接返回。
        """
        real_timestamp = self._last_update_time
        if not save_scheduler_time_state(
            scaled_timestamp=self._elapsed_scaled + self._offset,
            real_timestamp=real_timestamp,
            scale=self._scale,
            offset_seconds=self._offset,
            paused=self._paused,
        ):
            logger.warning("Scheduler 缩放时间锚点持久化失败")

    def ensure_minimum_timestamp(self, minimum_timestamp: float) -> float:
        """
        确保当前缩放时间不小于已有持久化业务时间。

        该方法用于首次升级持久化时间锚点时承接历史记忆时间，避免旧记录在升级后的
        第一次启动中被视为来自未来。

        Args:
            minimum_timestamp: 业务数据中已存在的最大缩放时间戳。

        Returns:
            float: 对齐后的当前缩放时间戳。
        """
        with self._lock:
            self._update_elapsed_scaled()
            current_timestamp = self._elapsed_scaled + self._offset
            if current_timestamp < minimum_timestamp:
                self._elapsed_scaled += minimum_timestamp - current_timestamp
                current_timestamp = minimum_timestamp
                self._persist_state_locked()
            return current_timestamp

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
            self._persist_state_locked()

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
            self._update_elapsed_scaled()
            self._elapsed_scaled += seconds
            self._persist_state_locked()

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


def get_scaled_time() -> datetime:
    """
    获取缩放后的当前时间（便捷函数）

    Returns:
        datetime: 缩放后的当前时间
    """
    return get_time_system().get_scaled_time()


def get_scaled_timestamp() -> float:
    """
    获取缩放后的时间戳（便捷函数）

    Returns:
        float: 缩放后的 Unix 时间戳
    """
    return get_time_system().get_scaled_timestamp()


def set_time_scale(scale: float) -> None:
    """
    设置全局时间倍率（便捷函数）

    Args:
        scale: 新的时间倍率，必须大于 0
    """
    get_time_system().set_scale(scale)


def get_time_scale() -> float:
    """
    获取全局时间倍率（便捷函数）

    Returns:
        float: 当前时间倍率
    """
    return get_time_system().get_scale()


def reload_time_scale() -> float:
    """
    从 management 系统配置表重载全局时间倍率。

    Returns:
        float: 重载后生效的时间倍率。
    """
    scale = load_time_scale_from_db()
    get_time_system().set_scale(scale)
    return scale
