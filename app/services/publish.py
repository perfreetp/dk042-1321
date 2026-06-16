import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.publish import PublishLog, PublishTask
from app.models.strategy import FeeItem, PriceTemplate
from app.schemas.publish import PublishRollbackRequest, PublishTaskCreate
from app.services.risk import check_region_frozen, detect_conflict, validate_price


def _add_log(db: Session, task_id: int, action: str, detail: str = None, operator: str = None):
    log = PublishLog(task_id=task_id, action=action, detail=detail, operator=operator)
    db.add(log)


def _get_template(db: Session, template_id: int) -> PriceTemplate:
    tpl = db.query(PriceTemplate).filter(PriceTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="价格模板不存在")
    return tpl


def _validate_template_prices(db: Session, tpl: PriceTemplate) -> None:
    fee_items = db.query(FeeItem).filter(FeeItem.template_id == tpl.id).all()
    for fi in fee_items:
        result = validate_price(db, tpl.brand_code, fi.fee_type, fi.price_per_unit)
        if not result.valid:
            raise HTTPException(
                status_code=400,
                detail=f"费用类型[{fi.fee_type} - {fi.fee_name}]不合规: {result.message}, 当前价格: {fi.price_per_unit}",
            )


def _check_region_freeze(db: Session, tpl: PriceTemplate) -> None:
    if check_region_frozen(db, tpl.site_code):
        raise HTTPException(
            status_code=403,
            detail=f"站点[{tpl.site_code}]所属区域已被冻结，禁止发布调价",
        )


def _check_conflicts(db: Session, template_id: int, operator: str, brand_code: str = None, site_code: str = None) -> None:
    conflicts = detect_conflict(db, template_id, brand_code, site_code)
    if conflicts:
        detail_list = []
        for c in conflicts:
            detail_list.append({
                "conflict_id": c.id,
                "conflict_type": c.conflict_type,
                "conflict_detail": json.loads(c.conflict_detail) if c.conflict_detail else None,
            })
        raise HTTPException(
            status_code=409,
            detail={
                "message": "检测到发布冲突",
                "conflicts": detail_list,
            },
        )


def _activate_template(db: Session, tpl: PriceTemplate) -> None:
    same_group_templates = (
        db.query(PriceTemplate)
        .filter(
            PriceTemplate.brand_code == tpl.brand_code,
            PriceTemplate.site_code == tpl.site_code,
            PriceTemplate.status == "active",
            PriceTemplate.id != tpl.id,
        )
        .all()
    )
    for t in same_group_templates:
        t.status = "archived"
    tpl.status = "active"
    db.flush()


def _rollback_template(db: Session, tpl: PriceTemplate, task: PublishTask) -> None:
    tpl.status = "archived"
    prev_task = (
        db.query(PublishTask)
        .join(PriceTemplate, PublishTask.template_id == PriceTemplate.id)
        .filter(
            PriceTemplate.brand_code == tpl.brand_code,
            PriceTemplate.site_code == tpl.site_code,
            PriceTemplate.id != tpl.id,
            PublishTask.status == "published",
            PublishTask.published_at < task.published_at,
        )
        .order_by(desc(PublishTask.published_at))
        .first()
    )
    if prev_task:
        prev_tpl = db.query(PriceTemplate).filter(PriceTemplate.id == prev_task.template_id).first()
        if prev_tpl:
            prev_tpl.status = "active"
    db.flush()


def create_task(db: Session, data: PublishTaskCreate) -> PublishTask:
    if data.publish_type == "scheduled":
        if not data.scheduled_at or data.scheduled_at <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="定时发布时间必须大于当前时间")
    if data.publish_type == "grayscale":
        if not data.grayscale_ratio or data.grayscale_ratio <= 0:
            raise HTTPException(status_code=400, detail="灰度比例必须大于0")

    tpl = _get_template(db, data.template_id)
    _validate_template_prices(db, tpl)
    _check_region_freeze(db, tpl)
    _check_conflicts(db, data.template_id, data.operator, tpl.brand_code, tpl.site_code)

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

    tpl = _get_template(db, task.template_id)
    _validate_template_prices(db, tpl)
    _check_region_freeze(db, tpl)

    task.status = "publishing"
    db.flush()

    snapshot = json.dumps({
        "template_id": task.template_id,
        "template_name": tpl.template_name,
        "template_version": tpl.template_version,
        "publish_type": task.publish_type,
        "brand_code": tpl.brand_code,
        "site_code": tpl.site_code,
    })
    task.snapshot_data = snapshot

    _activate_template(db, tpl)

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

    tpl = _get_template(db, task.template_id)
    _rollback_template(db, tpl, task)

    task.status = "rolled_back"
    task.rollback_at = datetime.utcnow()
    task.rollback_operator = data.operator
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
        try:
            published.append(publish_now(db, task.id))
        except HTTPException:
            pass
    return published
