from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.models.strategy import PriceTemplate, FeeItem, ChannelPrice
from app.models.publish import PublishTask, PublishLog
from app.models.channel import ChannelConfig, FieldMapping
from app.models.receipt import ReceiptRecord
from app.models.risk import ApprovalRecord
from app.services.channel import transform_price_data


def _get_last_action(db: Session, brand_code: str, site_code: str):
    published_tasks = (
        db.query(PublishTask)
        .join(PriceTemplate, PublishTask.template_id == PriceTemplate.id)
        .filter(
            PriceTemplate.brand_code == brand_code,
            PriceTemplate.site_code == site_code,
            PublishTask.status.in_(["published", "rolled_back"]),
        )
        .all()
    )
    last_event = None
    last_task = None
    last_action_type = None
    last_operator = None
    for task in published_tasks:
        if task.published_at and (last_event is None or task.published_at > last_event):
            last_event = task.published_at
            last_task = task
            last_action_type = "publish"
            last_operator = task.operator
        if task.rollback_at and (last_event is None or task.rollback_at > last_event):
            last_event = task.rollback_at
            last_task = task
            last_action_type = "rollback"
            last_operator = task.rollback_operator
    return {
        "task": last_task,
        "action_type": last_action_type,
        "action_at": last_event,
        "action_operator": last_operator,
    }


def query_current_price(
    db: Session,
    brand_code: str,
    site_code: Optional[str] = None,
    channel_code: Optional[str] = None,
) -> list:
    filters = [
        PriceTemplate.brand_code == brand_code,
        PriceTemplate.status == "active",
    ]
    if site_code:
        filters.append(PriceTemplate.site_code == site_code)
    templates = (
        db.query(PriceTemplate)
        .filter(and_(*filters))
        .order_by(desc(PriceTemplate.template_version))
        .all()
    )
    last_action_cache = {}
    results = []
    for tpl in templates:
        cache_key = f"{tpl.brand_code}:{tpl.site_code}"
        if cache_key not in last_action_cache:
            last_action_cache[cache_key] = _get_last_action(db, tpl.brand_code, tpl.site_code)
        last_action = last_action_cache[cache_key]
        fee_items = db.query(FeeItem).filter(FeeItem.template_id == tpl.id).all()
        channel_prices = db.query(ChannelPrice).filter(ChannelPrice.template_id == tpl.id).all()
        latest_publish = (
            db.query(PublishTask)
            .filter(
                PublishTask.template_id == tpl.id,
                PublishTask.status.in_(["published", "rolled_back"]),
            )
            .order_by(desc(PublishTask.published_at))
            .first()
        )
        publish_info = None
        if latest_publish:
            approval_records = db.query(ApprovalRecord).filter(ApprovalRecord.task_id == latest_publish.id).all()
            approval_status = "not_required"
            if approval_records:
                if any(r.status == "pending" for r in approval_records):
                    approval_status = "pending"
                elif any(r.status == "rejected" for r in approval_records):
                    approval_status = "rejected"
                else:
                    approval_status = "approved"
            publish_info = {
                "task_id": latest_publish.id,
                "status": latest_publish.status,
                "published_at": latest_publish.published_at,
                "rollback_at": latest_publish.rollback_at,
                "operator": latest_publish.operator,
                "approval_status": approval_status,
            }
        effective_info = None
        if last_action and last_action["task"]:
            last_task = last_action["task"]
            last_tpl = db.query(PriceTemplate).filter(PriceTemplate.id == last_task.template_id).first()
            effective_info = {
                "action_type": last_action["action_type"],
                "action_at": last_action["action_at"],
                "action_task_id": last_task.id,
                "action_operator": last_action["action_operator"],
                "action_template_id": last_task.template_id,
                "action_template_name": last_tpl.template_name if last_tpl else None,
                "action_template_version": last_tpl.template_version if last_tpl else None,
                "current_template_id": tpl.id,
                "current_template_name": tpl.template_name,
                "current_template_version": tpl.template_version,
            }
        tpl_data = {
            "template_id": tpl.id,
            "brand_code": tpl.brand_code,
            "site_code": tpl.site_code,
            "template_name": tpl.template_name,
            "template_version": tpl.template_version,
            "effective_date": tpl.effective_date,
            "expire_date": tpl.expire_date,
            "fee_items": [
                {
                    "fee_type": f.fee_type,
                    "fee_name": f.fee_name,
                    "price_per_unit": f.price_per_unit,
                    "unit": f.unit,
                    "calculation_rule": f.calculation_rule,
                }
                for f in fee_items
            ],
            "channel_prices": [],
            "publish_status": publish_info,
            "effective_info": effective_info,
        }
        for cp in channel_prices:
            if channel_code and cp.channel_code != channel_code:
                continue
            price_entry = {
                "channel_code": cp.channel_code,
                "display_price": cp.display_price,
                "settlement_price": cp.settlement_price,
                "discount_rate": cp.discount_rate,
            }
            if channel_code:
                internal_data = {
                    "display_price": cp.display_price,
                    "settlement_price": cp.settlement_price,
                    "discount_rate": cp.discount_rate,
                }
                try:
                    transformed = transform_price_data(db, channel_code, internal_data)
                    price_entry["transformed"] = transformed
                except Exception:
                    pass
            tpl_data["channel_prices"].append(price_entry)
        results.append(tpl_data)
    return results


def query_price_history(
    db: Session,
    brand_code: str,
    site_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> list:
    filters = [PriceTemplate.brand_code == brand_code]
    if site_code:
        filters.append(PriceTemplate.site_code == site_code)
    templates = (
        db.query(PriceTemplate)
        .filter(and_(*filters))
        .order_by(desc(PriceTemplate.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    results = []
    for tpl in templates:
        fee_items = db.query(FeeItem).filter(FeeItem.template_id == tpl.id).all()
        channel_prices = db.query(ChannelPrice).filter(ChannelPrice.template_id == tpl.id).all()
        publish_tasks = db.query(PublishTask).filter(PublishTask.template_id == tpl.id).all()
        results.append({
            "template_id": tpl.id,
            "brand_code": tpl.brand_code,
            "site_code": tpl.site_code,
            "template_name": tpl.template_name,
            "template_version": tpl.template_version,
            "status": tpl.status,
            "effective_date": tpl.effective_date,
            "expire_date": tpl.expire_date,
            "fee_items": [
                {"fee_type": f.fee_type, "fee_name": f.fee_name, "price_per_unit": f.price_per_unit}
                for f in fee_items
            ],
            "channel_prices": [
                {"channel_code": c.channel_code, "display_price": c.display_price, "settlement_price": c.settlement_price}
                for c in channel_prices
            ],
            "publish_records": [
                {
                    "id": t.id,
                    "publish_type": t.publish_type,
                    "status": t.status,
                    "published_at": t.published_at,
                    "operator": t.operator,
                }
                for t in publish_tasks
            ],
            "created_at": tpl.created_at,
        })
    return results


def query_change_notifications(
    db: Session,
    channel_code: str,
    since: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 20,
) -> list:
    filters = [ReceiptRecord.channel_code == channel_code]
    if since:
        filters.append(ReceiptRecord.created_at >= since)
    receipts = (
        db.query(ReceiptRecord)
        .filter(and_(*filters))
        .order_by(desc(ReceiptRecord.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    results = []
    for r in receipts:
        task = db.query(PublishTask).filter(PublishTask.id == r.task_id).first()
        template = None
        if task:
            template = db.query(PriceTemplate).filter(PriceTemplate.id == task.template_id).first()
        results.append({
            "receipt_id": r.id,
            "task_id": r.task_id,
            "channel_code": r.channel_code,
            "status": r.status,
            "created_at": r.created_at,
            "completed_at": r.completed_at,
            "publish_info": {
                "publish_type": task.publish_type if task else None,
                "operator": task.operator if task else None,
                "published_at": task.published_at if task else None,
            } if task else None,
            "template_info": {
                "brand_code": template.brand_code if template else None,
                "site_code": template.site_code if template else None,
                "template_name": template.template_name if template else None,
                "template_version": template.template_version if template else None,
            } if template else None,
        })
    return results
