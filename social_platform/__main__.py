"""Public social platform service entrypoint."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import uvicorn

from social_platform.app.core.config import get_settings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
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
        help="Uvicorn log level. Defaults to debug when DEBUG=true, otherwise info.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    settings = get_settings()

    uvicorn.run(
        "social_platform.app.main:app",
        host=args.host or settings.SERVER_HOST,
        port=args.port or settings.SERVER_PORT,
        reload=args.reload,
        log_level=args.log_level or ("debug" if settings.DEBUG else "info"),
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
