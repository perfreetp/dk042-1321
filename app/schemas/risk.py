from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PriceLimitRuleCreate(BaseModel):
    brand_code: str
    fee_type: str
    upper_limit: float
    lower_limit: float
    enabled: Optional[bool] = True


class PriceLimitRuleOut(BaseModel):
    id: int
    brand_code: str
    fee_type: str
    upper_limit: float
    lower_limit: float
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalStrategyCreate(BaseModel):
    brand_code: str
    site_code: Optional[str] = None
    channel_code: Optional[str] = None
    max_increase_pct: float
    enabled: Optional[bool] = True


class ApprovalStrategyOut(BaseModel):
    id: int
    brand_code: str
    site_code: Optional[str]
    channel_code: Optional[str]
    max_increase_pct: float
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalRecordOut(BaseModel):
    id: int
    task_id: int
    strategy_id: int
    approval_type: str
    trigger_detail: Optional[str]
    status: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejected_by: Optional[str]
    rejected_at: Optional[datetime]
    reject_reason: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalActionRequest(BaseModel):
    operator: str
    reason: Optional[str] = None


class FreezeRuleCreate(BaseModel):
    region_code: str
    region_name: str
    reason: str
    operator: str


class FreezeRuleOut(BaseModel):
    id: int
    region_code: str
    region_name: str
    reason: str
    operator: str
    status: str
    lifted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConflictRecordOut(BaseModel):
    id: int
    template_id: int
    conflict_type: str
    conflict_detail: Optional[str]
    resolved: bool
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ConflictResolveRequest(BaseModel):
    resolved_by: str


class ReconciliationReportCreate(BaseModel):
    channel_code: str
    period_start: datetime
    period_end: datetime


class ReconciliationReportOut(BaseModel):
    id: int
    report_no: str
    channel_code: str
    period_start: datetime
    period_end: datetime
    total_changes: int
    success_count: int
    failed_count: int
    detail_data: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PriceValidationRequest(BaseModel):
    brand_code: str
    fee_type: str
    price: float


class PriceValidationResult(BaseModel):
    valid: bool
    message: str
    upper_limit: Optional[float] = None
    lower_limit: Optional[float] = None
