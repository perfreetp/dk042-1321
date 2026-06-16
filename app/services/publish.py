import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.publish import PublishLog, PublishTask
from app.schemas.publish import PublishRollbackRequest, PublishTaskCreate


def _add_log(db: Session, task_id: int, action: str, detail: str = None, operator: str = None):
    log = PublishLog(task_id=task_id, action=action, detail=detail, operator=operator)
    db.add(log)


def create_task(db: Session, data: PublishTaskCreate) -> PublishTask:
    if data.publish_type == "scheduled":
        if not data.scheduled_at or data.scheduled_at <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="定时发布时间必须大于当前时间")
    if data.publish_type == "grayscale":
        if not data.grayscale_ratio or data.grayscale_ratio <= 0:
            raise HTTPException(status_code=400, detail="灰度比例必须大于0")

    task = PublishTask(
        template_id=data.template_id,
        publish_type=data.publish_type,
        scheduled_at=data.scheduled_at,
        grayscale_ratio=data.grayscale_ratio or 0.0,
        grayscale_channel_codes=data.grayscale_channel_codes,
        operator=data.operator,
        remark=data.remark,
    )
    db.add(task)
    db.flush()
    _add_log(db, task.id, "create", operator=data.operator)
    db.commit()
    db.refresh(task)

    if data.publish_type == "immediate":
        task = publish_now(db, task.id)

    return task


def get_task(db: Session, task_id: int) -> PublishTask:
    return db.query(PublishTask).filter(PublishTask.id == task_id).first()


def list_tasks(db: Session, template_id: int = None, status: str = None, skip: int = 0, limit: int = 20) -> list:
    query = db.query(PublishTask)
    if template_id:
        query = query.filter(PublishTask.template_id == template_id)
    if status:
        query = query.filter(PublishTask.status == status)
    return query.offset(skip).limit(limit).all()


def publish_now(db: Session, task_id: int) -> PublishTask:
    task = db.query(PublishTask).filter(PublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="仅pending状态可执行发布")

    task.status = "publishing"
    db.flush()

    snapshot = json.dumps({"template_id": task.template_id, "publish_type": task.publish_type})
    task.snapshot_data = snapshot
    task.status = "published"
    task.published_at = datetime.utcnow()
    _add_log(db, task.id, "publish", detail=snapshot, operator=task.operator)
    db.commit()
    db.refresh(task)
    return task


def rollback_task(db: Session, task_id: int, data: PublishRollbackRequest) -> PublishTask:
    task = db.query(PublishTask).filter(PublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "published":
        raise HTTPException(status_code=400, detail="仅published状态可回滚")

    task.status = "rolled_back"
    task.rollback_at = datetime.utcnow()
    _add_log(db, task.id, "rollback", detail=data.remark, operator=data.operator)
    db.commit()
    db.refresh(task)
    return task


def cancel_task(db: Session, task_id: int, operator: str) -> PublishTask:
    task = db.query(PublishTask).filter(PublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="仅pending状态可取消")

    task.status = "cancelled"
    _add_log(db, task.id, "cancel", operator=operator)
    db.commit()
    db.refresh(task)
    return task


def check_and_publish_scheduled(db: Session) -> list:
    tasks = (
        db.query(PublishTask)
        .filter(PublishTask.publish_type == "scheduled")
        .filter(PublishTask.status == "pending")
        .filter(PublishTask.scheduled_at <= datetime.utcnow())
        .all()
    )
    published = []
    for task in tasks:
        published.append(publish_now(db, task.id))
    return published
