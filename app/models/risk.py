from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceLimitRule(Base):
    __tablename__ = "price_limit_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_code: Mapped[str] = mapped_column(String(64), nullable=False)
    fee_type: Mapped[str] = mapped_column(String(32), nullable=False)
    upper_limit: Mapped[float] = mapped_column(Float, nullable=False)
    lower_limit: Mapped[float] = mapped_column(Float, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApprovalStrategy(Base):
    __tablename__ = "approval_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_code: Mapped[str] = mapped_column(String(64), nullable=False)
    site_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    max_increase_pct: Mapped[float] = mapped_column(Float, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("publish_tasks.id"), nullable=False)
    strategy_id: Mapped[int] = mapped_column(Integer, nullable=False)
    approval_type: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FreezeRule(Base):
    __tablename__ = "freeze_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    region_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    operator: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    lifted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConflictRecord(Base):
    __tablename__ = "conflict_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(32), nullable=False)
    conflict_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    channel_code: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_changes: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    detail_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="generating")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
