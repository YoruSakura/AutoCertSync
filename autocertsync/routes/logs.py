"""日志查看路由"""

import collections

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse

from autocertsync.app import templates, get_db, get_config, require_auth

router = APIRouter(prefix="/logs")


@router.get("", response_class=HTMLResponse)
async def log_page(request: Request, _=Depends(require_auth)):
    db = get_db()
    logs = db.list_sync_logs(limit=20)
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": logs,
    })


@router.get("/content", response_class=PlainTextResponse)
async def log_content(_=Depends(require_auth), lines: int = 200):
    """读取日志文件最后 N 行"""
    config = get_config()
    log_file = config.log_file
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            tail = collections.deque(f, maxlen=lines)
        return "".join(tail)
    except FileNotFoundError:
        return "日志文件不存在"
    except Exception as e:
        return f"读取日志失败: {e}"
