"""单实例文件锁 - 防止多个进程同时运行"""

import fcntl
import os
import sys
from pathlib import Path


class SingleInstanceLock:
    """通过文件锁确保只有一个进程实例在运行"""

    def __init__(self, lock_path: str = "/tmp/autocertsync.lock"):
        self.lock_path = lock_path
        self._lock_file = None

    def acquire(self) -> bool:
        """获取锁，成功返回 True，已有其他实例运行返回 False"""
        try:
            self._lock_file = open(self.lock_path, "w")
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
            return True
        except (IOError, OSError):
            if self._lock_file:
                self._lock_file.close()
                self._lock_file = None
            return False

    def release(self):
        """释放锁"""
        if self._lock_file:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
            except (IOError, OSError):
                pass
            self._lock_file = None
            try:
                Path(self.lock_path).unlink(missing_ok=True)
            except OSError:
                pass

    def __enter__(self):
        if not self.acquire():
            print("错误：已有另一个 AutoCertSync 实例正在运行", file=sys.stderr)
            sys.exit(1)
        return self

    def __exit__(self, *args):
        self.release()
