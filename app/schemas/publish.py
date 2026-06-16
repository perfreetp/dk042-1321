from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PublishTaskCreate(BaseModel):
    template_id: int
    publish_type: str
    scheduled_at: Optional[datetime] = None
    grayscale_ratio: Optional[float] = None
    grayscale_channel_codes: Optional[str] = None
    operator: str
    remark: Optional[str] = None


class PublishLogOut(BaseModel):
    id: int
    task_id: int
    action: str
    detail: Optional[str]
    operator: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PublishTaskOut(BaseModel):
    id: int
    template_id: int
    publish_type: str
    status: str
    scheduled_at: Optional[datetime]
    grayscale_ratio: Optional[float]
    grayscale_channel_codes: Optional[str]
    published_at: Optional[datetime]
    rollback_at: Optional[datetime]
    operator: str
    remark: Optional[str]
    snapshot_data: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PublishTaskOutWithLogs(PublishTaskOut):
    logs: List[PublishLogOut] = []


class PublishRollbackRequest(BaseModel):
    operator: str
    remark: Optional[str] = None
