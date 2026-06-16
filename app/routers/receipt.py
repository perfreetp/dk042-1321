from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.receipt import ReceiptCallbackRequest, ReceiptRecordCreate, ReceiptRecordOut, ReceiptRecordOutWithRetries
from app.services import receipt as receipt_service

router = APIRouter(prefix="/receipt", tags=["回执中心"])


@router.post("/records", response_model=ReceiptRecordOut)
def create_receipt(data: ReceiptRecordCreate, db: Session = Depends(get_db)):
    return receipt_service.create_receipt(db, data)


@router.get("/records", response_model=List[ReceiptRecordOut])
def list_receipts(
    task_id: Optional[int] = None,
    channel_code: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return receipt_service.list_receipts(db, task_id, channel_code, status, skip, limit)


@router.get("/records/{receipt_id}", response_model=ReceiptRecordOutWithRetries)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    record = receipt_service.get_receipt(db, receipt_id)
    if not record:
        raise HTTPException(status_code=404, detail="回执记录不存在")
    return record


@router.post("/callback", response_model=ReceiptRecordOut)
def handle_callback(data: ReceiptCallbackRequest, db: Session = Depends(get_db)):
    return receipt_service.handle_callback(db, data)


@router.post("/records/{receipt_id}/retry", response_model=ReceiptRecordOut)
def retry_receipt(receipt_id: int, db: Session = Depends(get_db)):
    return receipt_service.retry_receipt(db, receipt_id)


@router.post("/batch-retry")
def batch_retry_failed(db: Session = Depends(get_db)):
    result = receipt_service.batch_retry_failed(db)
    return {
        "retried_count": len(result["retried"]),
        "exhausted_count": len(result["exhausted"]),
        "retried": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "channel_code": r.channel_code,
                "retry_count": r.retry_count,
                "max_retry": r.max_retry,
                "status": r.status,
            }
            for r in result["retried"]
        ],
        "exhausted": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "channel_code": r.channel_code,
                "retry_count": r.retry_count,
                "max_retry": r.max_retry,
                "status": r.status,
            }
            for r in result["exhausted"]
        ],
    }


@router.post("/batch", response_model=List[ReceiptRecordOut])
def create_receipts_for_task(task_id: int, channel_codes: List[str], db: Session = Depends(get_db)):
    return receipt_service.create_receipts_for_task(db, task_id, channel_codes)


@router.get("/task-summary/{task_id}")
def get_task_receipt_summary(task_id: int, db: Session = Depends(get_db)):
    return receipt_service.get_task_receipt_summary(db, task_id)
