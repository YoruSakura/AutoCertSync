"""日志模块 - 文件日志 + WebSocket 实时推送"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Set

from starlette.websockets import WebSocket


class WebSocketLogHandler(logging.Handler):
    """将日志推送到所有已连接的 WebSocket 客户端"""

    def __init__(self):
        super().__init__()
        self._connections: Set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop = None

    def register(self, ws: WebSocket):
        self._connections.add(ws)

    def unregister(self, ws: WebSocket):
        self._connections.discard(ws)

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        dead = set()
        for ws in self._connections:
            try:
                loop = self._loop or asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(ws.send_text(msg), loop)
            except Exception:
                dead.add(ws)
        self._connections -= dead

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop


# 全局 WebSocket handler 实例
ws_handler = WebSocketLogHandler()


def setup_logger(log_file: str, log_level: str = "INFO",
                 max_size_mb: int = 10, backup_count: int = 5) -> logging.Logger:
    """配置并返回应用日志器"""
    logger = logging.getLogger("autocertsync")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件日志（可配置轮转大小和备份数）
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # WebSocket 推送
    ws_handler.setFormatter(formatter)
    logger.addHandler(ws_handler)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("autocertsync")
