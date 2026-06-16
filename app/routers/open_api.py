from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.open_api import query_current_price, query_price_history, query_change_notifications

router = APIRouter(prefix="/open", tags=["对外接口"])


@router.get("/price/query")
def get_current_price(
    brand_code: str = Query(...),
    site_code: Optional[str] = Query(None),
    channel_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return {"data": query_current_price(db, brand_code, site_code, channel_code)}


@router.get("/price/history")
def get_price_history(
    brand_code: str = Query(...),
    site_code: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return {"data": query_price_history(db, brand_code, site_code, skip, limit)}


@router.get("/change/notifications")
def get_change_notifications(
    channel_code: str = Query(...),
    since: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return {"data": query_change_notifications(db, channel_code, since, skip, limit)}
