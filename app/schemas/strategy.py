from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FeeItemCreate(BaseModel):
    fee_type: str
    fee_name: str
    price_per_unit: float
    unit: Optional[str] = "kWh"
    calculation_rule: Optional[str] = None


class FeeItemOut(FeeItemCreate):
    id: int
    template_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChannelPriceCreate(BaseModel):
    channel_code: str
    display_price: float
    settlement_price: float
    discount_rate: Optional[float] = 1.0


class ChannelPriceOut(ChannelPriceCreate):
    id: int
    template_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceTemplateCreate(BaseModel):
    brand_code: str
    site_code: str
    template_name: str
    template_version: Optional[int] = None
    effective_date: Optional[datetime] = None
    expire_date: Optional[datetime] = None
    fee_items: List[FeeItemCreate]
    channel_prices: List[ChannelPriceCreate]


class PriceTemplateOut(BaseModel):
    id: int
    brand_code: str
    site_code: str
    template_name: str
    template_version: int
    status: str
    effective_date: Optional[datetime]
    expire_date: Optional[datetime]
    fee_items: List[FeeItemOut]
    channel_prices: List[ChannelPriceOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceTemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    effective_date: Optional[datetime] = None
    expire_date: Optional[datetime] = None
    status: Optional[str] = None
