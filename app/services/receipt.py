from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.receipt import ReceiptRecord, RetryLog
from app.schemas.receipt import ReceiptCallbackRequest, ReceiptRecordCreate


def create_receipt(db: Session, data: ReceiptRecordCreate) -> ReceiptRecord:
    record = ReceiptRecord(
        task_id=data.task_id,
        channel_code=data.channel_code,
        request_data=data.request_data,
        max_retry=data.max_retry,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_receipt(db: Session, receipt_id: int) -> ReceiptRecord:
    return db.query(ReceiptRecord).filter(ReceiptRecord.id == receipt_id).first()


def list_receipts(
    db: Session,
    task_id: int = None,
    channel_code: str = None,
    status: str = None,
    skip: int = 0,
    limit: int = 20,
) -> list:
    query = db.query(ReceiptRecord)
    if task_id is not None:
        query = query.filter(ReceiptRecord.task_id == task_id)
    if channel_code is not None:
        query = query.filter(ReceiptRecord.channel_code == channel_code)
    if status is not None:
        query = query.filter(ReceiptRecord.status == status)
    return query.offset(skip).limit(limit).all()


def handle_callback(db: Session, data: ReceiptCallbackRequest) -> ReceiptRecord:
    record = (
        db.query(ReceiptRecord)
        .filter(ReceiptRecord.task_id == data.task_id, ReceiptRecord.channel_code == data.channel_code)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="回执记录不存在")

    record.status = data.status
    record.response_data = data.response_data
    record.error_message = data.error_message
    record.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


def retry_receipt(db: Session, receipt_id: int) -> ReceiptRecord:
    record = db.query(ReceiptRecord).filter(ReceiptRecord.id == receipt_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="回执记录不存在")
    if record.retry_count >= record.max_retry:
        raise HTTPException(status_code=400, detail=f"已达到最大重试次数({record.max_retry}次)，不再重试")

    record.retry_count += 1
    record.status = "pending"
    record.next_retry_at = datetime.utcnow()

    log = RetryLog(
        receipt_id=record.id,
        retry_at=datetime.utcnow(),
        status="failed",
        error_message=record.error_message,
        response_data=record.response_data,
    )
    db.add(log)
    db.commit()
    db.refresh(record)
    return record


def process_failed_receipts(db: Session) -> list:
    records = (
        db.query(ReceiptRecord)
        .filter(ReceiptRecord.status == "failed")
        .filter(ReceiptRecord.retry_count < ReceiptRecord.max_retry)
        .all()
    )
    retried = []
    for record in records:
        try:
            retried.append(retry_receipt(db, record.id))
        except HTTPException:
            pass
    return retried


def create_receipts_for_task(db: Session, task_id: int, channel_codes: list[str]) -> list[ReceiptRecord]:
    records = []
    for code in channel_codes:
        record = ReceiptRecord(task_id=task_id, channel_code=code)
        db.add(record)
        records.append(record)
    db.commit()
    for record in records:
        db.refresh(record)
    return records
