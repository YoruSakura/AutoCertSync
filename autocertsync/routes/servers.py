"""服务器配置管理路由"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse

from autocertsync.app import templates, get_db, require_auth

router = APIRouter(prefix="/servers")


@router.get("", response_class=HTMLResponse)
async def server_list(request: Request, _=Depends(require_auth)):
    db = get_db()
    servers = db.list_servers()
    # 为每台服务器附加部署规则
    for s in servers:
        s["rules"] = db.list_deploy_rules(server_id=s["id"])
    cert_dirs = db.list_cert_dirs()
    return templates.TemplateResponse("servers.html", {
        "request": request,
        "servers": servers,
        "cert_dirs": cert_dirs,
    })


@router.post("/add")
async def server_add(
    request: Request,
    _=Depends(require_auth),
    name: str = Form(...),
    host: str = Form(...),
    port: int = Form(22),
    auth_type: str = Form("password"),
    username: str = Form(...),
    password: str = Form(""),
    private_key: str = Form(""),
):
    db = get_db()
    db.add_server(
        name=name, host=host, port=port, auth_type=auth_type,
        username=username, password=password or None,
        private_key=private_key or None,
    )
    return RedirectResponse(url="/servers", status_code=302)


@router.post("/{server_id}/edit")
async def server_edit(
    server_id: int,
    request: Request,
    _=Depends(require_auth),
    name: str = Form(...),
    host: str = Form(...),
    port: int = Form(22),
    auth_type: str = Form("password"),
    username: str = Form(...),
    password: str = Form(""),
    private_key: str = Form(""),
):
    db = get_db()
    db.update_server(
        server_id,
        name=name, host=host, port=port, auth_type=auth_type,
        username=username, password=password or None,
        private_key=private_key or None,
    )
    return RedirectResponse(url="/servers", status_code=302)


@router.post("/{server_id}/delete")
async def server_delete(server_id: int, _=Depends(require_auth)):
    db = get_db()
    db.delete_server(server_id)
    return RedirectResponse(url="/servers", status_code=302)


@router.post("/{server_id}/toggle")
async def server_toggle(server_id: int, _=Depends(require_auth)):
    db = get_db()
    server = db.get_server(server_id)
    if server:
        db.update_server(server_id, enabled=0 if server["enabled"] else 1)
    return RedirectResponse(url="/servers", status_code=302)


# ========== 部署规则 ==========

@router.post("/{server_id}/rules/add")
async def rule_add(
    server_id: int,
    _=Depends(require_auth),
    cert_dir_id: int = Form(...),
    remote_cert_dir: str = Form(...),
    pre_deploy_command: str = Form(""),
    post_deploy_command: str = Form(""),
    cert_filename: str = Form(""),
    key_filename: str = Form(""),
):
    db = get_db()
    db.add_deploy_rule(
        server_id=server_id, cert_dir_id=cert_dir_id,
        remote_cert_dir=remote_cert_dir,
        pre_deploy_command=pre_deploy_command or None,
        post_deploy_command=post_deploy_command or None,
        cert_filename=cert_filename or None,
        key_filename=key_filename or None,
    )
    return RedirectResponse(url="/servers", status_code=302)


@router.post("/rules/{rule_id}/edit")
async def rule_edit(
    rule_id: int,
    _=Depends(require_auth),
    cert_dir_id: int = Form(...),
    remote_cert_dir: str = Form(...),
    pre_deploy_command: str = Form(""),
    post_deploy_command: str = Form(""),
    cert_filename: str = Form(""),
    key_filename: str = Form(""),
):
    db = get_db()
    db.update_deploy_rule(
        rule_id,
        cert_dir_id=cert_dir_id,
        remote_cert_dir=remote_cert_dir,
        pre_deploy_command=pre_deploy_command or None,
        post_deploy_command=post_deploy_command or None,
        cert_filename=cert_filename or None,
        key_filename=key_filename or None,
    )
    return RedirectResponse(url="/servers", status_code=302)


@router.post("/rules/{rule_id}/delete")
async def rule_delete(rule_id: int, _=Depends(require_auth)):
    db = get_db()
    db.delete_deploy_rule(rule_id)
    return RedirectResponse(url="/servers", status_code=302)


@router.post("/rules/{rule_id}/toggle")
async def rule_toggle(rule_id: int, _=Depends(require_auth)):
    db = get_db()
    rule = db.get_deploy_rule(rule_id)
    if rule:
        db.update_deploy_rule(rule_id, enabled=0 if rule["enabled"] else 1)
    return RedirectResponse(url="/servers", status_code=302)
