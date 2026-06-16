from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.risk import (
    ApprovalActionRequest,
    ApprovalRecordOut,
    ApprovalStrategyCreate,
    ApprovalStrategyOut,
    ConflictRecordOut,
    ConflictResolveRequest,
    FreezeRuleCreate,
    FreezeRuleOut,
    PriceLimitRuleCreate,
    PriceLimitRuleOut,
    PriceValidationRequest,
    PriceValidationResult,
    ReconciliationReportCreate,
    ReconciliationReportOut,
)
from app.services import risk as risk_service

router = APIRouter(prefix="/risk", tags=["风险拦截"])


@router.post("/limit-rules", response_model=PriceLimitRuleOut)
def create_limit_rule(data: PriceLimitRuleCreate, db: Session = Depends(get_db)):
    return risk_service.create_limit_rule(db, data)


@router.get("/limit-rules", response_model=List[PriceLimitRuleOut])
def list_limit_rules(
    brand_code: Optional[str] = None,
    fee_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return risk_service.list_limit_rules(db, brand_code, fee_type, skip, limit)


@router.put("/limit-rules/{rule_id}", response_model=PriceLimitRuleOut)
def update_limit_rule(
    rule_id: int,
    upper_limit: Optional[float] = None,
    lower_limit: Optional[float] = None,
    enabled: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    rule = risk_service.update_limit_rule(db, rule_id, upper_limit, lower_limit, enabled)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.post("/validate-price", response_model=PriceValidationResult)
def validate_price(data: PriceValidationRequest, db: Session = Depends(get_db)):
    return risk_service.validate_price(db, data.brand_code, data.fee_type, data.price)


@router.post("/freeze", response_model=FreezeRuleOut)
def create_freeze_rule(data: FreezeRuleCreate, db: Session = Depends(get_db)):
    return risk_service.create_freeze_rule(db, data)


@router.get("/freeze", response_model=List[FreezeRuleOut])
def list_freeze_rules(
    region_code: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return risk_service.list_freeze_rules(db, region_code, status, skip, limit)


@router.post("/freeze/{freeze_id}/lift", response_model=FreezeRuleOut)
def lift_freeze(freeze_id: int, operator: str, db: Session = Depends(get_db)):
    rule = risk_service.lift_freeze(db, freeze_id, operator)
    if not rule:
        raise HTTPException(status_code=404, detail="冻结规则不存在")
    return rule


@router.get("/freeze/check")
def check_region_frozen(region_code: str, db: Session = Depends(get_db)):
    frozen = risk_service.check_region_frozen(db, region_code)
    return {"region_code": region_code, "frozen": frozen}


@router.get("/conflicts", response_model=List[ConflictRecordOut])
def list_conflicts(
    template_id: Optional[int] = None,
    resolved: Optional[bool] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return risk_service.list_conflicts(db, template_id, resolved, skip, limit)


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictRecordOut)
def resolve_conflict(conflict_id: int, data: ConflictResolveRequest, db: Session = Depends(get_db)):
    record = risk_service.resolve_conflict(db, conflict_id, data)
    if not record:
        raise HTTPException(status_code=404, detail="冲突记录不存在")
    return record


@router.post("/reconciliation", response_model=ReconciliationReportOut)
def generate_reconciliation(data: ReconciliationReportCreate, db: Session = Depends(get_db)):
    return risk_service.generate_reconciliation(db, data)


@router.get("/reconciliation", response_model=List[ReconciliationReportOut])
def list_reconciliation_reports(
    channel_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return risk_service.list_reconciliation_reports(db, channel_code, skip, limit)


@router.post("/approval-strategies", response_model=ApprovalStrategyOut)
def create_approval_strategy(data: ApprovalStrategyCreate, db: Session = Depends(get_db)):
    return risk_service.create_approval_strategy(db, data)


@router.get("/approval-strategies", response_model=List[ApprovalStrategyOut])
def list_approval_strategies(
    brand_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return risk_service.list_approval_strategies(db, brand_code, skip, limit)


@router.get("/approvals", response_model=List[ApprovalRecordOut])
def list_approvals(
    task_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return risk_service.get_pending_approvals(db, task_id, skip, limit)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRecordOut)
def approve_approval(approval_id: int, data: ApprovalActionRequest, db: Session = Depends(get_db)):
    record = risk_service.approve_record(db, approval_id, data)
    if not record:
        raise HTTPException(status_code=404, detail="审批记录不存在")
    return record


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalRecordOut)
def reject_approval(approval_id: int, data: ApprovalActionRequest, db: Session = Depends(get_db)):
    record = risk_service.reject_record(db, approval_id, data)
    if not record:
        raise HTTPException(status_code=404, detail="审批记录不存在")
    return record
