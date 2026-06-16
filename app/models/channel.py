from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChannelConfig(Base):
    __tablename__ = "channel_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    channel_name: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False)
    callback_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    secret_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    remark: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    field_mappings: Mapped[list["FieldMapping"]] = relationship(back_populates="channel", cascade="all, delete-orphan")


class FieldMapping(Base):
    __tablename__ = "field_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel_configs.id"))
    internal_field: Mapped[str] = mapped_column(String(128), nullable=False)
    external_field: Mapped[str] = mapped_column(String(128), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), default="string")
    transform_rule: Mapped[str | None] = mapped_column(String(256), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    channel: Mapped["ChannelConfig"] = relationship(back_populates="field_mappings")
