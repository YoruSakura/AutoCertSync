"""证书变动检测模块 - watchdog inotify 实时监听 + 防抖"""

import threading
from pathlib import Path
from typing import Callable, Dict

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from autocertsync.logger import get_logger


class _DebouncedHandler(FileSystemEventHandler):
    """防抖事件处理器：延迟触发，期间有新事件则重置计时"""

    def __init__(self, callback: Callable[[str], None], delay: int):
        super().__init__()
        self.callback = callback
        self.delay = delay
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return
        # 只关注内容变更事件，忽略 access/open/close 等读取事件
        if event.event_type not in ("created", "modified", "deleted", "moved"):
            return
        # 以监听目录为粒度做防抖
        src = str(Path(event.src_path).parent)
        with self._lock:
            if src in self._timers:
                self._timers[src].cancel()
            timer = threading.Timer(self.delay, self._fire, args=(src,))
            timer.daemon = True
            timer.start()
            self._timers[src] = timer

    def _fire(self, path: str):
        logger = get_logger()
        logger.info(f"检测到证书目录变动: {path}")
        with self._lock:
            self._timers.pop(path, None)
        try:
            self.callback(path)
        except Exception as e:
            logger.error(f"处理证书变动回调异常: {e}")


class CertWatcher:
    """证书目录监听器"""

    def __init__(self, delay: int = 5):
        self.delay = delay
        self._observer = Observer()
        self._callback: Callable[[str], None] = None
        self._watched_paths: dict[str, object] = {}

    def set_callback(self, callback: Callable[[str], None]):
        """设置变动回调函数，参数为变动的目录路径"""
        self._callback = callback

    def watch(self, path: str):
        """添加监听目录"""
        logger = get_logger()
        if not Path(path).is_dir():
            logger.warning(f"监听目录不存在，跳过: {path}")
            return
        if path in self._watched_paths:
            return
        handler = _DebouncedHandler(self._callback, self.delay)
        watch = self._observer.schedule(handler, path, recursive=False)
        self._watched_paths[path] = watch
        logger.info(f"已添加监听目录: {path}")

    def unwatch(self, path: str):
        """移除监听目录"""
        if path in self._watched_paths:
            self._observer.unschedule(self._watched_paths.pop(path))
            get_logger().info(f"已移除监听目录: {path}")

    def update_watches(self, paths: list[str]):
        """更新监听目录列表（增删改）"""
        current = set(self._watched_paths.keys())
        target = set(paths)
        for p in current - target:
            self.unwatch(p)
        for p in target - current:
            self.watch(p)

    def start(self):
        """启动监听"""
        get_logger().info("证书目录监听器已启动")
        self._observer.start()

    def stop(self):
        """停止监听"""
        self._observer.stop()
        self._observer.join()
        get_logger().info("证书目录监听器已停止")
