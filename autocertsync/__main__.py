"""AutoCertSync 主程序入口"""

import asyncio
import os
import signal
import sys
import threading

import uvicorn

from autocertsync.config import AppConfig
from autocertsync.database import Database
from autocertsync.lock import SingleInstanceLock
from autocertsync.logger import setup_logger, ws_handler
from autocertsync.sync_engine import SyncEngine
from autocertsync.watcher import CertWatcher
from autocertsync.app import create_app


def main():
    # 支持子命令
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "install":
            _install_service()
            return
        elif cmd == "uninstall":
            _uninstall_service()
            return

    # 加载配置
    config = AppConfig()
    config.ensure_data_dir()

    # 单实例锁
    lock = SingleInstanceLock()
    if not lock.acquire():
        print("错误：已有另一个 AutoCertSync 实例正在运行", file=sys.stderr)
        sys.exit(1)

    # 初始化日志
    logger = setup_logger(config.log_file, config.log_level,
                          config.log_max_size_mb, config.log_backup_count)
    logger.info("AutoCertSync 启动中...")

    # 初始化数据库
    db = Database(config.db_path)
    logger.info(f"数据库已加载: {config.db_path}")

    # 初始化同步引擎
    engine = SyncEngine(db, config.retry_count, config.retry_interval)

    # 初始化文件监听
    watcher = CertWatcher(delay=config.sync_delay)

    def on_cert_change(path: str):
        """证书目录变动回调"""
        cert_dirs = db.list_cert_dirs(enabled_only=True)
        for cd in cert_dirs:
            if os.path.normpath(cd["local_path"]) == os.path.normpath(path):
                logger.info(f"触发同步: {path}")
                engine.sync_cert_dir(cd["id"])
                break

    watcher.set_callback(on_cert_change)

    # 启动监听目录
    cert_dirs = db.list_cert_dirs(enabled_only=True)
    for cd in cert_dirs:
        watcher.watch(cd["local_path"])
    watcher.start()
    logger.info(f"已监听 {len(cert_dirs)} 个证书目录")

    # 创建 FastAPI 应用
    app = create_app(config, db, engine)

    # 优雅退出
    shutdown_event = threading.Event()

    def graceful_shutdown(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"收到信号 {sig_name}，开始优雅退出...")
        shutdown_event.set()
        watcher.stop()
        engine.shutdown()
        lock.release()
        logger.info("AutoCertSync 已停止")
        sys.exit(0)

    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    # 设置 WebSocket handler 的事件循环
    def _on_startup():
        try:
            loop = asyncio.get_event_loop()
            ws_handler.set_loop(loop)
        except RuntimeError:
            pass

    @app.on_event("startup")
    async def startup_event():
        ws_handler.set_loop(asyncio.get_event_loop())

    # 启动 uvicorn（根据 SSL 证书决定 HTTP/HTTPS）
    ssl_cert, ssl_key = config.get_ssl_paths()
    if ssl_cert and ssl_key:
        logger.info(f"WebUI 启动: https://{config.server_host}:{config.server_port}")
        uvicorn.run(
            app,
            host=config.server_host,
            port=config.server_port,
            log_level="warning",
            ssl_certfile=ssl_cert,
            ssl_keyfile=ssl_key,
        )
    else:
        logger.info(f"SSL 证书未找到({config.ssl_cert_dir}/), WebUI 以 HTTP 模式启动")
        logger.info(f"WebUI 启动: http://{config.server_host}:{config.server_port}")
        uvicorn.run(
            app,
            host=config.server_host,
            port=config.server_port,
            log_level="warning",
        )


def _install_service():
    """安装为 systemd 服务"""
    exe_path = os.path.abspath(sys.argv[0])
    python_path = sys.executable
    work_dir = os.path.dirname(exe_path) or os.getcwd()

    # 判断运行方式
    if exe_path.endswith(".pyz"):
        exec_start = f"{python_path} {exe_path}"
    else:
        exec_start = f"{python_path} -m autocertsync"

    unit = f"""[Unit]
Description=AutoCertSync - SSL/TLS Certificate Sync Tool
After=network.target

[Service]
Type=simple
WorkingDirectory={work_dir}
ExecStart={exec_start}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    service_path = "/etc/systemd/system/autocertsync.service"
    try:
        with open(service_path, "w") as f:
            f.write(unit)
        os.system("systemctl daemon-reload")
        os.system("systemctl enable autocertsync")
        print(f"服务已安装: {service_path}")
        print("启动: systemctl start autocertsync")
        print("状态: systemctl status autocertsync")
    except PermissionError:
        print("错误：需要 root 权限，请使用 sudo", file=sys.stderr)
        sys.exit(1)


def _uninstall_service():
    """卸载 systemd 服务"""
    service_path = "/etc/systemd/system/autocertsync.service"
    try:
        os.system("systemctl stop autocertsync 2>/dev/null")
        os.system("systemctl disable autocertsync 2>/dev/null")
        if os.path.exists(service_path):
            os.remove(service_path)
        os.system("systemctl daemon-reload")
        print("服务已卸载")
    except PermissionError:
        print("错误：需要 root 权限，请使用 sudo", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
