"""FastAPI 应用 - WebUI 入口"""

import os
import secrets
import shutil
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from autocertsync.config import AppConfig
from autocertsync.database import Database
from autocertsync.sync_engine import SyncEngine


def _extract_web_assets() -> Path:
    """从 .pyz 中提取 templates 和 static 到真实目录，
    如果是普通运行则直接返回包目录"""
    base = Path(__file__).parent

    # 普通运行（非 zip），直接使用
    if base.is_dir() and (base / "templates").is_dir():
        return base

    # 从 .pyz (zip) 中提取 web 资源
    web_dir = Path("./data/web")
    # 找到 zip 文件路径：__file__ 形如 /path/to/app.pyz/autocertsync/app.py
    zip_path = None
    for parent in Path(__file__).parents:
        if parent.suffix == ".pyz" and zipfile.is_zipfile(str(parent)):
            zip_path = str(parent)
            break

    if not zip_path:
        raise RuntimeError("无法定位 .pyz 文件")

    # 每次启动提取最新资源
    if web_dir.exists():
        shutil.rmtree(web_dir)
    web_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            # 提取 autocertsync/templates/ 和 autocertsync/static/
            if "/templates/" in name or "/static/" in name:
                # 去掉 autocertsync/ 前缀，保留 templates/... 和 static/...
                parts = name.split("/", 1)
                if len(parts) > 1:
                    rel = parts[1]  # templates/xxx 或 static/xxx
                    target = web_dir / rel
                    if name.endswith("/"):
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(name) as src, open(target, "wb") as dst:
                            dst.write(src.read())

    return web_dir


WEB_DIR = _extract_web_assets()
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
templates.env.filters["basename"] = lambda p: os.path.basename(p)

# 全局实例，由 create_app 初始化
_db: Optional[Database] = None
_config: Optional[AppConfig] = None
_engine: Optional[SyncEngine] = None


def get_db() -> Database:
    return _db


def get_config() -> AppConfig:
    return _config


def get_engine() -> SyncEngine:
    return _engine


def require_auth(request: Request):
    """认证依赖：未登录则重定向到登录页"""
    if not request.session.get("authenticated"):
        raise RedirectException()
    return True


class RedirectException(Exception):
    pass


def create_app(config: AppConfig, db: Database, engine: SyncEngine) -> FastAPI:
    global _db, _config, _engine
    _db = db
    _config = config
    _engine = engine

    app = FastAPI(title="AutoCertSync", docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    @app.exception_handler(RedirectException)
    async def redirect_to_login(request: Request, exc: RedirectException):
        return RedirectResponse(url="/login", status_code=302)

    from autocertsync.routes.auth import router as auth_router
    from autocertsync.routes.dashboard import router as dashboard_router
    from autocertsync.routes.servers import router as servers_router
    from autocertsync.routes.certs import router as certs_router
    from autocertsync.routes.sync import router as sync_router
    from autocertsync.routes.logs import router as logs_router
    from autocertsync.routes.settings import router as settings_router

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(servers_router)
    app.include_router(certs_router)
    app.include_router(sync_router)
    app.include_router(logs_router)
    app.include_router(settings_router)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        if request.session.get("authenticated"):
            return RedirectResponse(url="/dashboard", status_code=302)
        return RedirectResponse(url="/login", status_code=302)

    return app
