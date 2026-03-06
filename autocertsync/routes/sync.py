"""手动同步路由"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from autocertsync.app import get_db, get_engine, require_auth

router = APIRouter(prefix="/sync")


@router.post("/all")
async def sync_all(_=Depends(require_auth)):
    engine = get_engine()
    engine.sync_all()
    return JSONResponse({"status": "ok", "message": "已触发全量同步"})


@router.post("/cert-dir/{cert_dir_id}")
async def sync_cert_dir(cert_dir_id: int, _=Depends(require_auth)):
    engine = get_engine()
    engine.sync_cert_dir(cert_dir_id)
    return JSONResponse({"status": "ok", "message": f"已触发证书目录 {cert_dir_id} 同步"})


@router.post("/rule/{rule_id}")
async def sync_rule(rule_id: int, _=Depends(require_auth)):
    engine = get_engine()
    engine.sync_rule(rule_id)
    return JSONResponse({"status": "ok", "message": f"已触发部署规则 {rule_id} 同步"})
