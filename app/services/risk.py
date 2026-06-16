import json
import uuid
from datetime import datetime

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.models.publish import PublishTask
from app.models.receipt import ReceiptRecord
from app.models.risk import (
    ApprovalRecord,
    ApprovalStrategy,
    ConflictRecord,
    FreezeRule,
    PriceLimitRule,
    ReconciliationReport,
)
from app.models.strategy import FeeItem, PriceTemplate
from app.schemas.risk import (
    ApprovalActionRequest,
    ConflictResolveRequest,
    PriceValidationResult,
    ReconciliationReportCreate,
)


def create_limit_rule(db: Session, data) -> PriceLimitRule:
    rule = PriceLimitRule(
        brand_code=data.brand_code,
        fee_type=data.fee_type,
        upper_limit=data.upper_limit,
        lower_limit=data.lower_limit,
        enabled=data.enabled if data.enabled is not None else True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_limit_rules(db: Session, brand_code=None, fee_type=None, skip=0, limit=20) -> list:
    query = db.query(PriceLimitRule)
    if brand_code:
        query = query.filter(PriceLimitRule.brand_code == brand_code)
    if fee_type:
        query = query.filter(PriceLimitRule.fee_type == fee_type)
    return query.offset(skip).limit(limit).all()


def update_limit_rule(db: Session, rule_id, upper_limit=None, lower_limit=None, enabled=None) -> PriceLimitRule:
    rule = db.query(PriceLimitRule).filter(PriceLimitRule.id == rule_id).first()
    if upper_limit is not None:
        rule.upper_limit = upper_limit
    if lower_limit is not None:
        rule.lower_limit = lower_limit
    if enabled is not None:
        rule.enabled = enabled
    db.commit()
    db.refresh(rule)
    return rule


def validate_price(db: Session, brand_code, fee_type, price) -> PriceValidationResult:
    rule = (
        db.query(PriceLimitRule)
        .filter(
            PriceLimitRule.brand_code == brand_code,
            PriceLimitRule.fee_type == fee_type,
            PriceLimitRule.enabled == True,
        )
        .first()
    )
    if not rule:
        return PriceValidationResult(valid=True, message="未找到价格规则，默认通过")
    if price > rule.upper_limit:
        return PriceValidationResult(
            valid=False,
            message=f"价格超出上限 {rule.upper_limit}",
            upper_limit=rule.upper_limit,
            lower_limit=rule.lower_limit,
        )
    if price < rule.lower_limit:
        return PriceValidationResult(
            valid=False,
            message=f"价格低于下限 {rule.lower_limit}",
            upper_limit=rule.upper_limit,
            lower_limit=rule.lower_limit,
        )
    return PriceValidationResult(
        valid=True,
        message="价格校验通过",
        upper_limit=rule.upper_limit,
        lower_limit=rule.lower_limit,
    )


def create_freeze_rule(db: Session, data) -> FreezeRule:
    rule = FreezeRule(
        region_code=data.region_code,
        region_name=data.region_name,
        reason=data.reason,
        operator=data.operator,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_freeze_rules(db: Session, region_code=None, status=None, skip=0, limit=20) -> list:
    query = db.query(FreezeRule)
    if region_code:
        query = query.filter(FreezeRule.region_code == region_code)
    if status:
        query = query.filter(FreezeRule.status == status)
    return query.offset(skip).limit(limit).all()


def lift_freeze(db: Session, freeze_id, operator) -> FreezeRule:
    rule = db.query(FreezeRule).filter(FreezeRule.id == freeze_id).first()
    rule.status = "lifted"
    rule.operator = operator
    rule.lifted_at = datetime.utcnow()
    db.commit()
    db.refresh(rule)
    return rule


def check_region_frozen(db: Session, region_code) -> bool:
    return (
        db.query(FreezeRule)
        .filter(FreezeRule.region_code == region_code, FreezeRule.status == "active")
        .first()
        is not None
    )


def detect_conflict(db: Session, template_id, brand_code=None, site_code=None) -> list:
    conflicts = []
    pending_tasks = (
        db.query(PublishTask)
        .filter(
            PublishTask.template_id == template_id,
            PublishTask.status.in_(["pending", "publishing"]),
        )
        .all()
    )
    if len(pending_tasks) > 1:
        detail = json.dumps(
            [{"task_id": t.id, "status": t.status, "publish_type": t.publish_type} for t in pending_tasks]
        )
        conflict = ConflictRecord(
            template_id=template_id,
            conflict_type="duplicate_publish",
            conflict_detail=detail,
        )
        db.add(conflict)
        conflicts.append(conflict)
    if len(pending_tasks) >= 1:
        existing_conflict = (
            db.query(ConflictRecord)
            .filter(
                ConflictRecord.template_id == template_id,
                ConflictRecord.conflict_type == "override_conflict",
                ConflictRecord.resolved == False,
            )
            .first()
        )
        if not existing_conflict:
            detail = json.dumps(
                [{"task_id": t.id, "status": t.status, "publish_type": t.publish_type} for t in pending_tasks]
            )
            conflict = ConflictRecord(
                template_id=template_id,
                conflict_type="override_conflict",
                conflict_detail=detail,
            )
            db.add(conflict)
            conflicts.append(conflict)
    if brand_code and site_code:
        site_pending_tasks = (
            db.query(PublishTask)
            .join(PriceTemplate, PublishTask.template_id == PriceTemplate.id)
            .filter(
                PriceTemplate.brand_code == brand_code,
                PriceTemplate.site_code == site_code,
                PriceTemplate.id != template_id,
                PublishTask.status.in_(["pending", "publishing"]),
            )
            .all()
        )
        if site_pending_tasks:
            existing_site_conflict = (
                db.query(ConflictRecord)
                .filter(
                    ConflictRecord.template_id == template_id,
                    ConflictRecord.conflict_type == "site_conflict",
                    ConflictRecord.resolved == False,
                )
                .first()
            )
            if not existing_site_conflict:
                detail = json.dumps(
                    [
                        {
                            "task_id": t.id,
                            "template_id": t.template_id,
                            "status": t.status,
                            "publish_type": t.publish_type,
                        }
                        for t in site_pending_tasks
                    ]
                )
                conflict = ConflictRecord(
                    template_id=template_id,
                    conflict_type="site_conflict",
                    conflict_detail=detail,
                )
                db.add(conflict)
                conflicts.append(conflict)
    if conflicts:
        db.commit()
        for c in conflicts:
            db.refresh(c)
    return conflicts


def resolve_conflict(db: Session, conflict_id, data: ConflictResolveRequest) -> ConflictRecord:
    record = db.query(ConflictRecord).filter(ConflictRecord.id == conflict_id).first()
    record.resolved = True
    record.resolved_by = data.resolved_by
    record.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


def list_conflicts(db: Session, template_id=None, resolved=None, skip=0, limit=20) -> list:
    query = db.query(ConflictRecord)
    if template_id:
        query = query.filter(ConflictRecord.template_id == template_id)
    if resolved is not None:
        query = query.filter(ConflictRecord.resolved == resolved)
    return query.offset(skip).limit(limit).all()


def generate_reconciliation(db: Session, data: ReconciliationReportCreate) -> ReconciliationReport:
    query = db.query(ReceiptRecord).filter(
        ReceiptRecord.channel_code == data.channel_code,
        ReceiptRecord.created_at >= data.period_start,
        ReceiptRecord.created_at <= data.period_end,
    )
    total = query.count()
    success_count = query.filter(ReceiptRecord.status == "success").count()
    failed_count = query.filter(ReceiptRecord.status == "failed").count()

    report = ReconciliationReport(
        report_no=uuid.uuid4().hex[:16],
        channel_code=data.channel_code,
        period_start=data.period_start,
        period_end=data.period_end,
        total_changes=total,
        success_count=success_count,
        failed_count=failed_count,
        status="completed",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_reconciliation_reports(db: Session, channel_code=None, skip=0, limit=20) -> list:
    query = db.query(ReconciliationReport)
    if channel_code:
        query = query.filter(ReconciliationReport.channel_code == channel_code)
    return query.offset(skip).limit(limit).all()


def create_approval_strategy(db: Session, data) -> ApprovalStrategy:
    strategy = ApprovalStrategy(
        brand_code=data.brand_code,
        site_code=data.site_code,
        channel_code=data.channel_code,
        max_increase_pct=data.max_increase_pct,
        enabled=data.enabled if data.enabled is not None else True,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


def list_approval_strategies(db: Session, brand_code=None, skip=0, limit=20) -> list:
    query = db.query(ApprovalStrategy)
    if brand_code:
        query = query.filter(ApprovalStrategy.brand_code == brand_code)
    return query.offset(skip).limit(limit).all()


def check_approval_needed(db: Session, template_id: int) -> list:
    tpl = db.query(PriceTemplate).filter(PriceTemplate.id == template_id).first()
    if not tpl:
        return []
    strategies = db.query(ApprovalStrategy).filter(
        ApprovalStrategy.brand_code == tpl.brand_code,
        ApprovalStrategy.enabled == True,
        or_(
            ApprovalStrategy.site_code == None,
            ApprovalStrategy.site_code == tpl.site_code,
        ),
    ).all()
    if not strategies:
        return []
    active_tpl = db.query(PriceTemplate).filter(
        PriceTemplate.brand_code == tpl.brand_code,
        PriceTemplate.site_code == tpl.site_code,
        PriceTemplate.status == "active",
        PriceTemplate.id != tpl.id,
    ).first()
    if not active_tpl:
        return []
    old_fees = {fi.fee_type: fi.price_per_unit for fi in db.query(FeeItem).filter(FeeItem.template_id == active_tpl.id).all()}
    new_fees = {fi.fee_type: fi.price_per_unit for fi in db.query(FeeItem).filter(FeeItem.template_id == tpl.id).all()}
    triggered = []
    for strategy in strategies:
        for fee_type, new_price in new_fees.items():
            old_price = old_fees.get(fee_type)
            if old_price and old_price > 0:
                increase_pct = ((new_price - old_price) / old_price) * 100
                if increase_pct > strategy.max_increase_pct:
                    triggered.append({
                        "strategy": strategy,
                        "fee_type": fee_type,
                        "old_price": old_price,
                        "new_price": new_price,
                        "increase_pct": round(increase_pct, 2),
                    })
    return triggered


def create_approval_records(db: Session, task_id: int, triggered: list) -> list:
    records = []
    for item in triggered:
        strategy = item["strategy"]
        detail = json.dumps({
            "fee_type": item["fee_type"],
            "old_price": item["old_price"],
            "new_price": item["new_price"],
            "increase_pct": item["increase_pct"],
            "max_increase_pct": strategy.max_increase_pct,
        })
        record = ApprovalRecord(
            task_id=task_id,
            strategy_id=strategy.id,
            approval_type="price_increase",
            trigger_detail=detail,
        )
        db.add(record)
        records.append(record)
    if records:
        db.commit()
        for r in records:
            db.refresh(r)
    return records


def get_pending_approvals(db: Session, task_id: int = None, skip=0, limit=20) -> list:
    query = db.query(ApprovalRecord)
    if task_id:
        query = query.filter(ApprovalRecord.task_id == task_id)
    return query.offset(skip).limit(limit).all()


def approve_record(db: Session, approval_id: int, data: ApprovalActionRequest) -> ApprovalRecord:
    record = db.query(ApprovalRecord).filter(ApprovalRecord.id == approval_id).first()
    if not record:
        return None
    record.status = "approved"
    record.approved_by = data.operator
    record.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


def reject_record(db: Session, approval_id: int, data: ApprovalActionRequest) -> ApprovalRecord:
    record = db.query(ApprovalRecord).filter(ApprovalRecord.id == approval_id).first()
    if not record:
        return None
    record.status = "rejected"
    record.rejected_by = data.operator
    record.rejected_at = datetime.utcnow()
    record.reject_reason = data.reason
    db.commit()
    db.refresh(record)
    return record


def check_task_approval_status(db: Session, task_id: int) -> str:
    records = db.query(ApprovalRecord).filter(ApprovalRecord.task_id == task_id).all()
    if not records:
        return "not_required"
    if any(r.status == "pending" for r in records):
        return "pending"
    if any(r.status == "rejected" for r in records):
        return "rejected"
    return "approved"
