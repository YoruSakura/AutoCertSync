"""证书信息与目录管理路由"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse

from autocertsync.app import templates, get_db, require_auth
from autocertsync.cert_utils import find_cert_files, get_cert_info

router = APIRouter(prefix="/certs")


@router.get("", response_class=HTMLResponse)
async def cert_list(request: Request, _=Depends(require_auth)):
    db = get_db()
    cert_dirs = db.list_cert_dirs()

    dirs_info = []
    for cd in cert_dirs:
        files = find_cert_files(cd["local_path"])
        certs = []
        for f in files:
            info = get_cert_info(f)
            if info:
                certs.append(info)
        dirs_info.append({
            **cd,
            "certs": certs,
            "file_count": len(files),
        })

    return templates.TemplateResponse("certs.html", {
        "request": request,
        "cert_dirs": dirs_info,
    })


@router.post("/add")
async def cert_dir_add(
    request: Request,
    _=Depends(require_auth),
    local_path: str = Form(...),
    description: str = Form(""),
):
    db = get_db()
    db.add_cert_dir(local_path=local_path, description=description or None)
    return RedirectResponse(url="/certs", status_code=302)


@router.post("/{cert_dir_id}/edit")
async def cert_dir_edit(
    cert_dir_id: int,
    request: Request,
    _=Depends(require_auth),
    local_path: str = Form(...),
    description: str = Form(""),
):
    db = get_db()
    db.update_cert_dir(cert_dir_id, local_path=local_path, description=description or None)
    return RedirectResponse(url="/certs", status_code=302)


@router.post("/{cert_dir_id}/delete")
async def cert_dir_delete(cert_dir_id: int, _=Depends(require_auth)):
    db = get_db()
    db.delete_cert_dir(cert_dir_id)
    return RedirectResponse(url="/certs", status_code=302)


@router.post("/{cert_dir_id}/toggle")
async def cert_dir_toggle(cert_dir_id: int, _=Depends(require_auth)):
    db = get_db()
    cd = db.get_cert_dir(cert_dir_id)
    if cd:
        db.update_cert_dir(cert_dir_id, enabled=0 if cd["enabled"] else 1)
    return RedirectResponse(url="/certs", status_code=302)
