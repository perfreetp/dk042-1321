from datetime import datetime

from sqlalchemy.orm import Session

from app.models.channel import ChannelConfig, FieldMapping
from app.schemas.channel import ChannelConfigCreate, ChannelConfigUpdate, FieldMappingCreate


def create_channel(db: Session, data: ChannelConfigCreate) -> ChannelConfig:
    channel = ChannelConfig(
        channel_code=data.channel_code,
        channel_name=data.channel_name,
        channel_type=data.channel_type,
        callback_url=data.callback_url,
        secret_key=data.secret_key,
        enabled=data.enabled,
        remark=data.remark,
    )
    db.add(channel)
    db.flush()

    if data.field_mappings:
        for mapping_data in data.field_mappings:
            mapping = FieldMapping(
                channel_id=channel.id,
                internal_field=mapping_data.internal_field,
                external_field=mapping_data.external_field,
                field_type=mapping_data.field_type,
                transform_rule=mapping_data.transform_rule,
                required=mapping_data.required,
            )
            db.add(mapping)

    db.commit()
    db.refresh(channel)
    return channel


def get_channel(db: Session, channel_id: int) -> ChannelConfig:
    return db.query(ChannelConfig).filter(ChannelConfig.id == channel_id).first()


def get_channel_by_code(db: Session, channel_code: str) -> ChannelConfig:
    return db.query(ChannelConfig).filter(ChannelConfig.channel_code == channel_code).first()


def list_channels(
    db: Session,
    channel_type: str = None,
    enabled: bool = None,
    skip: int = 0,
    limit: int = 20,
) -> list:
    query = db.query(ChannelConfig)
    if channel_type:
        query = query.filter(ChannelConfig.channel_type == channel_type)
    if enabled is not None:
        query = query.filter(ChannelConfig.enabled == enabled)
    return query.offset(skip).limit(limit).all()


def update_channel(db: Session, channel_id: int, data: ChannelConfigUpdate) -> ChannelConfig:
    channel = db.query(ChannelConfig).filter(ChannelConfig.id == channel_id).first()
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(channel, key, value)
    db.commit()
    db.refresh(channel)
    return channel


def add_field_mapping(db: Session, channel_id: int, data: FieldMappingCreate) -> FieldMapping:
    mapping = FieldMapping(
        channel_id=channel_id,
        internal_field=data.internal_field,
        external_field=data.external_field,
        field_type=data.field_type,
        transform_rule=data.transform_rule,
        required=data.required,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def remove_field_mapping(db: Session, mapping_id: int) -> bool:
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        return False
    db.delete(mapping)
    db.commit()
    return True


def transform_price_data(db: Session, channel_code: str, internal_data: dict) -> dict:
    channel = get_channel_by_code(db, channel_code)
    if not channel:
        return {}
    result = {}
    for mapping in channel.field_mappings:
        value = internal_data.get(mapping.internal_field)
        if value is not None and mapping.transform_rule:
            parts = mapping.transform_rule.split(":")
            rule = parts[0]
            if rule == "multiply" and len(parts) == 2:
                value = value * float(parts[1])
            elif rule == "divide" and len(parts) == 2:
                value = value / float(parts[1])
            elif rule == "format" and len(parts) == 2:
                if isinstance(value, datetime):
                    value = value.strftime(parts[1])
                elif isinstance(value, str):
                    parsed = datetime.fromisoformat(value)
                    value = parsed.strftime(parts[1])
        result[mapping.external_field] = value
    return result
