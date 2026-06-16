from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import desc
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


def _update_latest_retry_log(
    db: Session,
    record: ReceiptRecord,
    status: str,
    error_message: str = None,
    response_data: str = None,
) -> None:
    latest_log = (
        db.query(RetryLog)
        .filter(RetryLog.receipt_id == record.id)
        .order_by(desc(RetryLog.retry_at))
        .first()
    )
    if latest_log and latest_log.status == "pending":
        latest_log.status = status
        latest_log.completed_at = datetime.utcnow()
        latest_log.error_message = error_message
        latest_log.response_data = response_data


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

    if record.retry_count > 0:
        _update_latest_retry_log(db, record, data.status, data.error_message, data.response_data)

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
        retry_no=record.retry_count,
        retry_at=datetime.utcnow(),
        status="pending",
    )
    db.add(log)
    db.commit()
    db.refresh(record)
    return record


def batch_retry_failed(db: Session) -> dict:
    records = (
        db.query(ReceiptRecord)
        .filter(ReceiptRecord.status == "failed")
        .filter(ReceiptRecord.retry_count < ReceiptRecord.max_retry)
        .all()
    )
    retried = []
    for record in records:
        try:
            result = retry_receipt(db, record.id)
            retried.append(result)
        except HTTPException:
            pass
    exhausted = (
        db.query(ReceiptRecord)
        .filter(ReceiptRecord.status == "failed")
        .filter(ReceiptRecord.retry_count >= ReceiptRecord.max_retry)
        .all()
    )
    for record in exhausted:
        record.status = "final_failed"
        log = RetryLog(
            receipt_id=record.id,
            retry_no=record.retry_count + 1,
            retry_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            status="final_failed",
            error_message=f"已达到最大重试次数({record.max_retry}次)，标记为最终失败",
        )
        db.add(log)
    if exhausted:
        db.commit()
        for r in exhausted:
            db.refresh(r)
    return {"retried": retried, "exhausted": exhausted}


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


def get_task_receipt_summary(db: Session, task_id: int) -> dict:
    records = db.query(ReceiptRecord).filter(ReceiptRecord.task_id == task_id).all()
    total = len(records)
    success = sum(1 for r in records if r.status == "success")
    failed = sum(1 for r in records if r.status == "failed")
    final_failed = sum(1 for r in records if r.status == "final_failed")
    pending = sum(1 for r in records if r.status == "pending")
    channels = []
    for r in records:
        retries = db.query(RetryLog).filter(RetryLog.receipt_id == r.id).order_by(RetryLog.retry_no).all()
        channels.append({
            "receipt_id": r.id,
            "channel_code": r.channel_code,
            "status": r.status,
            "retry_count": r.retry_count,
            "max_retry": r.max_retry,
            "retries": [
                {
                    "retry_no": log.retry_no,
                    "retry_at": log.retry_at,
                    "completed_at": log.completed_at,
                    "status": log.status,
                    "error_message": log.error_message,
                }
                for log in retries
            ],
        })
    return {
        "task_id": task_id,
        "total": total,
        "success": success,
        "failed": failed,
        "final_failed": final_failed,
        "pending": pending,
        "channels": channels,
    }
