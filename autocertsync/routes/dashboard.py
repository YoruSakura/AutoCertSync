"""仪表盘路由"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from autocertsync.app import templates, get_db, get_engine, require_auth

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, _=Depends(require_auth)):
    db = get_db()
    servers = db.list_servers()
    cert_dirs = db.list_cert_dirs()
    recent_logs = db.list_sync_logs(limit=20)
    engine = get_engine()

    deploy_rules = db.list_deploy_rules()

    stats = {
        "server_count": len(servers),
        "enabled_servers": sum(1 for s in servers if s["enabled"]),
        "cert_dir_count": len(cert_dirs),
        "rule_count": len(deploy_rules),
        "is_syncing": engine.is_busy,
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "servers": servers,
        "recent_logs": recent_logs,
    })
