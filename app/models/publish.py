from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PublishTask(Base):
    __tablename__ = "publish_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("price_templates.id"), nullable=False)
    publish_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    grayscale_ratio: Mapped[float | None] = mapped_column(Float, default=0.0)
    grayscale_channel_codes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rollback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rollback_operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator: Mapped[str] = mapped_column(String(64), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(512), nullable=True)
    snapshot_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    logs: Mapped[list["PublishLog"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class PublishLog(Base):
    __tablename__ = "publish_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("publish_tasks.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["PublishTask"] = relationship(back_populates="logs")
