from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.strategy import PriceTemplateCreate, PriceTemplateOut, PriceTemplateUpdate
from app.services import strategy as strategy_service

router = APIRouter(prefix="/strategy", tags=["策略编排"])


@router.post("/templates", response_model=PriceTemplateOut)
def create_template(data: PriceTemplateCreate, db: Session = Depends(get_db)):
    return strategy_service.create_template(db, data)


@router.get("/templates", response_model=List[PriceTemplateOut])
def list_templates(
    brand_code: Optional[str] = None,
    site_code: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return strategy_service.list_templates(db, brand_code, site_code, status, skip, limit)


@router.get("/templates/{template_id}", response_model=PriceTemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db)):
    template = strategy_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return template


@router.put("/templates/{template_id}", response_model=PriceTemplateOut)
def update_template(template_id: int, data: PriceTemplateUpdate, db: Session = Depends(get_db)):
    template = strategy_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return strategy_service.update_template(db, template_id, data)


@router.put("/templates/{template_id}/archive", response_model=PriceTemplateOut)
def archive_template(template_id: int, db: Session = Depends(get_db)):
    template = strategy_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return strategy_service.archive_template(db, template_id)
