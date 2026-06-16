from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PriceTemplate(Base):
    __tablename__ = "price_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    site_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    effective_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expire_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fee_items: Mapped[list["FeeItem"]] = relationship(back_populates="template", cascade="all, delete-orphan")
    channel_prices: Mapped[list["ChannelPrice"]] = relationship(back_populates="template", cascade="all, delete-orphan")


class FeeItem(Base):
    __tablename__ = "fee_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("price_templates.id"))
    fee_type: Mapped[str] = mapped_column(String(32), nullable=False)
    fee_name: Mapped[str] = mapped_column(String(128))
    price_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="kWh")
    calculation_rule: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template: Mapped["PriceTemplate"] = relationship(back_populates="fee_items")


class ChannelPrice(Base):
    __tablename__ = "channel_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("price_templates.id"))
    channel_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_price: Mapped[float] = mapped_column(Float, nullable=False)
    settlement_price: Mapped[float] = mapped_column(Float, nullable=False)
    discount_rate: Mapped[float | None] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template: Mapped["PriceTemplate"] = relationship(back_populates="channel_prices")
