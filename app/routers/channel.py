from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.channel import ChannelConfigCreate, ChannelConfigOut, ChannelConfigUpdate, FieldMappingCreate, FieldMappingOut
from app.services import channel as channel_service

router = APIRouter(prefix="/channel", tags=["渠道映射"])


@router.post("/configs", response_model=ChannelConfigOut)
def create_channel(data: ChannelConfigCreate, db: Session = Depends(get_db)):
    return channel_service.create_channel(db, data)


@router.get("/configs", response_model=List[ChannelConfigOut])
def list_channels(
    channel_type: Optional[str] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return channel_service.list_channels(db, channel_type, enabled, skip, limit)


@router.get("/configs/{channel_id}", response_model=ChannelConfigOut)
def get_channel(channel_id: int, db: Session = Depends(get_db)):
    channel = channel_service.get_channel(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return channel


@router.get("/configs/code/{channel_code}", response_model=ChannelConfigOut)
def get_channel_by_code(channel_code: str, db: Session = Depends(get_db)):
    channel = channel_service.get_channel_by_code(db, channel_code)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return channel


@router.put("/configs/{channel_id}", response_model=ChannelConfigOut)
def update_channel(channel_id: int, data: ChannelConfigUpdate, db: Session = Depends(get_db)):
    channel = channel_service.get_channel(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return channel_service.update_channel(db, channel_id, data)


@router.post("/configs/{channel_id}/mappings", response_model=FieldMappingOut)
def add_field_mapping(channel_id: int, data: FieldMappingCreate, db: Session = Depends(get_db)):
    channel = channel_service.get_channel(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return channel_service.add_field_mapping(db, channel_id, data)


@router.delete("/mappings/{mapping_id}")
def remove_field_mapping(mapping_id: int, db: Session = Depends(get_db)):
    success = channel_service.remove_field_mapping(db, mapping_id)
    if not success:
        raise HTTPException(status_code=404, detail="字段映射不存在")
    return {"ok": True}


@router.post("/transform")
def transform_price_data(channel_code: str, internal_data: Dict, db: Session = Depends(get_db)):
    result = channel_service.transform_price_data(db, channel_code, internal_data)
    if not result:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return result
