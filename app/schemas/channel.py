from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FieldMappingCreate(BaseModel):
    internal_field: str
    external_field: str
    field_type: Optional[str] = "string"
    transform_rule: Optional[str] = None
    required: Optional[bool] = True


class FieldMappingOut(FieldMappingCreate):
    id: int
    channel_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChannelConfigCreate(BaseModel):
    channel_code: str
    channel_name: str
    channel_type: str
    callback_url: Optional[str] = None
    secret_key: Optional[str] = None
    enabled: Optional[bool] = True
    remark: Optional[str] = None
    field_mappings: Optional[List[FieldMappingCreate]] = None


class ChannelConfigOut(BaseModel):
    id: int
    channel_code: str
    channel_name: str
    channel_type: str
    callback_url: Optional[str]
    enabled: bool
    remark: Optional[str]
    field_mappings: List[FieldMappingOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChannelConfigUpdate(BaseModel):
    channel_name: Optional[str] = None
    callback_url: Optional[str] = None
    secret_key: Optional[str] = None
    enabled: Optional[bool] = None
    remark: Optional[str] = None
