"""配置导入导出路由"""

import io

import yaml
from fastapi import APIRouter, Request, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse

from autocertsync.app import templates, get_db, require_auth

router = APIRouter(prefix="/settings")


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request, _=Depends(require_auth)):
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/export")
async def export_config(_=Depends(require_auth)):
    db = get_db()
    data = db.export_config()
    yaml_content = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return StreamingResponse(
        io.BytesIO(yaml_content.encode("utf-8")),
        media_type="application/x-yaml",
        headers={"Content-Disposition": "attachment; filename=autocertsync_config.yaml"},
    )


@router.post("/import")
async def import_config(request: Request, _=Depends(require_auth), file: UploadFile = File(...)):
    db = get_db()
    content = await file.read()
    try:
        data = yaml.safe_load(content.decode("utf-8"))
        db.import_config(data)
    except Exception as e:
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "error": f"导入失败: {e}",
        })
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "success": "配置导入成功",
    })
