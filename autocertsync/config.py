"""程序本体配置模块 - 管理 config.ini 的读写和首次运行初始化"""

import configparser
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": "8443",
    },
    "database": {
        "path": "./data/autocertsync.db",
    },
    "log": {
        "level": "INFO",
        "file": "./data/autocertsync.log",
        "max_size_mb": "10",
        "backup_count": "5",
    },
    "auth": {
        "username": "admin",
        "password": "admin123",
    },
    "sync": {
        "delay_seconds": "5",
        "retry_count": "3",
        "retry_interval": "10",
    },
    "ssl": {
        "cert_dir": "./ssl",
        "cert_file": "server.crt",
        "key_file": "server.key",
    },
}


class AppConfig:
    """程序配置管理器"""

    def __init__(self, config_path: str = "config.ini"):
        self.config_path = Path(config_path)
        self._config = configparser.ConfigParser()
        self._load()

    def _load(self):
        """加载配置文件，不存在则生成默认配置"""
        if not self.config_path.exists():
            self._create_default()
        self._config.read(self.config_path, encoding="utf-8")

    def _create_default(self):
        """生成默认配置文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        for section, values in DEFAULT_CONFIG.items():
            self._config[section] = values
        with open(self.config_path, "w", encoding="utf-8") as f:
            self._config.write(f)

    @property
    def server_host(self) -> str:
        return self._config.get("server", "host", fallback="0.0.0.0")

    @property
    def server_port(self) -> int:
        return self._config.getint("server", "port", fallback=8443)

    @property
    def db_path(self) -> str:
        return self._config.get("database", "path", fallback="./data/autocertsync.db")

    @property
    def log_level(self) -> str:
        return self._config.get("log", "level", fallback="INFO")

    @property
    def log_file(self) -> str:
        return self._config.get("log", "file", fallback="./data/autocertsync.log")

    @property
    def log_max_size_mb(self) -> int:
        return self._config.getint("log", "max_size_mb", fallback=10)

    @property
    def log_backup_count(self) -> int:
        return self._config.getint("log", "backup_count", fallback=5)

    @property
    def auth_username(self) -> str:
        return self._config.get("auth", "username", fallback="admin")

    @property
    def auth_password(self) -> str:
        return self._config.get("auth", "password", fallback="admin123")

    @property
    def sync_delay(self) -> int:
        return self._config.getint("sync", "delay_seconds", fallback=5)

    @property
    def retry_count(self) -> int:
        return self._config.getint("sync", "retry_count", fallback=3)

    @property
    def retry_interval(self) -> int:
        return self._config.getint("sync", "retry_interval", fallback=10)

    @property
    def ssl_cert_dir(self) -> str:
        return self._config.get("ssl", "cert_dir", fallback="./ssl")

    @property
    def ssl_cert_file(self) -> str:
        return self._config.get("ssl", "cert_file", fallback="server.crt")

    @property
    def ssl_key_file(self) -> str:
        return self._config.get("ssl", "key_file", fallback="server.key")

    def get_ssl_paths(self) -> tuple:
        """返回 (cert_path, key_path)，文件不存在则返回 (None, None)"""
        cert_dir = Path(self.ssl_cert_dir)
        cert_path = cert_dir / self.ssl_cert_file
        key_path = cert_dir / self.ssl_key_file
        if cert_path.is_file() and key_path.is_file():
            return (str(cert_path), str(key_path))
        return (None, None)

    def ensure_data_dir(self):
        """确保数据目录和 SSL 目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        log_dir = Path(self.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        ssl_dir = Path(self.ssl_cert_dir)
        ssl_dir.mkdir(parents=True, exist_ok=True)
