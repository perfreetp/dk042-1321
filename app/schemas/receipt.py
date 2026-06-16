from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ReceiptRecordCreate(BaseModel):
    task_id: int
    channel_code: str
    request_data: Optional[str] = None
    max_retry: int = 3


class RetryLogOut(BaseModel):
    id: int
    receipt_id: int
    retry_no: int
    retry_at: datetime
    completed_at: Optional[datetime]
    status: str
    error_message: Optional[str]
    response_data: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiptRecordOut(BaseModel):
    id: int
    task_id: int
    channel_code: str
    status: str
    request_data: Optional[str]
    response_data: Optional[str]
    error_message: Optional[str]
    retry_count: int
    max_retry: int
    next_retry_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReceiptRecordOutWithRetries(ReceiptRecordOut):
    retries: List[RetryLogOut] = []


class ReceiptCallbackRequest(BaseModel):
    channel_code: str
    task_id: int
    status: str
    response_data: Optional[str] = None
    error_message: Optional[str] = None
