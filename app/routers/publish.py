from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.publish import PublishRollbackRequest, PublishTaskCreate, PublishTaskOut, PublishTaskOutWithLogs
from app.services import publish as publish_service

router = APIRouter(prefix="/publish", tags=["发布网关"])


@router.post("/tasks", response_model=PublishTaskOut)
def create_task(data: PublishTaskCreate, db: Session = Depends(get_db)):
    return publish_service.create_task(db, data)


@router.get("/tasks", response_model=List[PublishTaskOut])
def list_tasks(
    template_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return publish_service.list_tasks(db, template_id, status, skip, limit)


@router.get("/tasks/{task_id}", response_model=PublishTaskOutWithLogs)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = publish_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/tasks/{task_id}/publish", response_model=PublishTaskOut)
def publish_now(task_id: int, db: Session = Depends(get_db)):
    return publish_service.publish_now(db, task_id)


@router.post("/tasks/{task_id}/rollback", response_model=PublishTaskOut)
def rollback_task(task_id: int, data: PublishRollbackRequest, db: Session = Depends(get_db)):
    return publish_service.rollback_task(db, task_id, data)


@router.post("/tasks/{task_id}/cancel", response_model=PublishTaskOut)
def cancel_task(task_id: int, operator: str, db: Session = Depends(get_db)):
    return publish_service.cancel_task(db, task_id, operator)
