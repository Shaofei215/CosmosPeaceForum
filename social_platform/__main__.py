"""公开社交平台服务的命令行入口。

该模块负责解析启动参数、读取平台配置，并将最终配置交给 Uvicorn 启动
FastAPI 应用。通过 ``python -m social_platform`` 运行包时会进入此模块。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from io import TextIOWrapper

import uvicorn

from social_platform.app.core.config import get_settings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """解析公开平台的命令行启动参数。

    Args:
        argv: 待解析的参数序列；为 ``None`` 时由 argparse 读取进程参数。

    Returns:
        包含主机、端口、热重载和日志级别选项的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="Start the CosmosPeaceForum social platform.")
    parser.add_argument("--host", help="Host address to bind. Defaults to SERVER_HOST.")
    parser.add_argument("--port", type=int, help="Port to bind. Defaults to SERVER_PORT.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable Uvicorn auto-reload for local development.",
    )
    parser.add_argument(
        "--log-level",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
        help="Uvicorn log level. Defaults to info.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """根据命令行参数和应用配置启动 Uvicorn 服务。

    命令行参数优先于环境配置；未显式传入的选项使用 ``Settings`` 中的默认值。

    Args:
        argv: 可选的命令行参数序列，主要用于测试或由其他 Python 代码调用。
    """
    args = parse_args(argv)
    settings = get_settings()

    # 使用导入字符串可以让 Uvicorn 的 reload 模式在子进程中重新加载应用。
    uvicorn.run(
        "social_platform.app.main:app",
        host=args.host or settings.SERVER_HOST,
        port=args.port or settings.SERVER_PORT,
        reload=args.reload,
        log_level=args.log_level or "info",
    )


if __name__ == "__main__":
    # sys.stdout 的公开类型是 TextIO，但 reconfigure 仅由 TextIOWrapper 提供。
    # 测试框架可能将标准输出替换为其他文本流，因此先收窄类型再启用行缓冲。
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)
    main()
