from typing import List, Optional

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.strategy import PriceTemplate
from app.schemas.publish import PublishRollbackRequest, PublishTaskCreate, PublishTaskOut, PublishTaskOutWithLogs
from app.services import publish as publish_service

router = APIRouter(prefix="/publish", tags=["发布网关"])


def _enrich_task(task, db=None):
    out = PublishTaskOut.model_validate(task)
    if task.snapshot_data:
        try:
            snap = json.loads(task.snapshot_data)
            out.template_name = snap.get("template_name")
            out.template_version = snap.get("template_version")
            out.brand_code = snap.get("brand_code")
            out.site_code = snap.get("site_code")
        except Exception:
            pass
    if not out.brand_code and db:
        tpl = db.query(PriceTemplate).filter(PriceTemplate.id == task.template_id).first()
        if tpl:
            out.template_name = tpl.template_name
            out.template_version = tpl.template_version
            out.brand_code = tpl.brand_code
            out.site_code = tpl.site_code
    return out


@router.post("/tasks", response_model=PublishTaskOut)
def create_task(data: PublishTaskCreate, db: Session = Depends(get_db)):
    task = publish_service.create_task(db, data)
    return _enrich_task(task, db)


@router.get("/tasks", response_model=List[PublishTaskOut])
def list_tasks(
    template_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    tasks = publish_service.list_tasks(db, template_id, status, skip, limit)
    return [_enrich_task(t, db) for t in tasks]


@router.get("/tasks/{task_id}", response_model=PublishTaskOutWithLogs)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = publish_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    out = PublishTaskOutWithLogs.model_validate(task)
    if task.snapshot_data:
        try:
            snap = json.loads(task.snapshot_data)
            out.template_name = snap.get("template_name")
            out.template_version = snap.get("template_version")
            out.brand_code = snap.get("brand_code")
            out.site_code = snap.get("site_code")
        except Exception:
            pass
    if not out.brand_code:
        tpl = db.query(PriceTemplate).filter(PriceTemplate.id == task.template_id).first()
        if tpl:
            out.template_name = tpl.template_name
            out.template_version = tpl.template_version
            out.brand_code = tpl.brand_code
            out.site_code = tpl.site_code
    return out


@router.post("/tasks/{task_id}/publish", response_model=PublishTaskOut)
def publish_now(task_id: int, db: Session = Depends(get_db)):
    task = publish_service.publish_now(db, task_id)
    return _enrich_task(task, db)


@router.post("/tasks/{task_id}/rollback", response_model=PublishTaskOut)
def rollback_task(task_id: int, data: PublishRollbackRequest, db: Session = Depends(get_db)):
    task = publish_service.rollback_task(db, task_id, data)
    return _enrich_task(task, db)


@router.post("/tasks/{task_id}/cancel", response_model=PublishTaskOut)
def cancel_task(task_id: int, operator: str, db: Session = Depends(get_db)):
    task = publish_service.cancel_task(db, task_id, operator)
    return _enrich_task(task, db)


@router.get("/tasks/{task_id}/grayscale")
def get_grayscale_status(task_id: int, db: Session = Depends(get_db)):
    return publish_service.get_grayscale_status(db, task_id)


@router.post("/tasks/{task_id}/grayscale/{channel_code}/promote")
def promote_grayscale_channel(
    task_id: int,
    channel_code: str,
    ratio: float = 1.0,
    db: Session = Depends(get_db),
):
    return publish_service.promote_grayscale_channel(db, task_id, channel_code, ratio)


@router.post("/tasks/{task_id}/grayscale/{channel_code}/rollback")
def rollback_grayscale_channel(
    task_id: int,
    channel_code: str,
    operator: str,
    db: Session = Depends(get_db),
):
    return publish_service.rollback_grayscale_channel(db, task_id, channel_code, operator)
