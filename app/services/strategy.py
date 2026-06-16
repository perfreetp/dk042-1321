from sqlalchemy.orm import Session

from app.models.strategy import ChannelPrice, FeeItem, PriceTemplate
from app.schemas.strategy import PriceTemplateCreate, PriceTemplateUpdate


def create_template(db: Session, data: PriceTemplateCreate) -> PriceTemplate:
    template = PriceTemplate(
        brand_code=data.brand_code,
        site_code=data.site_code,
        template_name=data.template_name,
        effective_date=data.effective_date,
        expire_date=data.expire_date,
    )
    db.add(template)
    db.flush()

    for fee_item_data in data.fee_items:
        fee_item = FeeItem(
            template_id=template.id,
            fee_type=fee_item_data.fee_type,
            fee_name=fee_item_data.fee_name,
            price_per_unit=fee_item_data.price_per_unit,
            unit=fee_item_data.unit,
            calculation_rule=fee_item_data.calculation_rule,
        )
        db.add(fee_item)

    for channel_price_data in data.channel_prices:
        channel_price = ChannelPrice(
            template_id=template.id,
            channel_code=channel_price_data.channel_code,
            display_price=channel_price_data.display_price,
            settlement_price=channel_price_data.settlement_price,
            discount_rate=channel_price_data.discount_rate,
        )
        db.add(channel_price)

    db.commit()
    db.refresh(template)
    return template


def get_template(db: Session, template_id: int) -> PriceTemplate:
    return db.query(PriceTemplate).filter(PriceTemplate.id == template_id).first()


def list_templates(
    db: Session,
    brand_code: str = None,
    site_code: str = None,
    status: str = None,
    skip: int = 0,
    limit: int = 20,
) -> list:
    query = db.query(PriceTemplate)
    if brand_code:
        query = query.filter(PriceTemplate.brand_code == brand_code)
    if site_code:
        query = query.filter(PriceTemplate.site_code == site_code)
    if status:
        query = query.filter(PriceTemplate.status == status)
    return query.offset(skip).limit(limit).all()


def update_template(db: Session, template_id: int, data: PriceTemplateUpdate) -> PriceTemplate:
    template = db.query(PriceTemplate).filter(PriceTemplate.id == template_id).first()
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)
    db.commit()
    db.refresh(template)
    return template


def archive_template(db: Session, template_id: int) -> PriceTemplate:
    template = db.query(PriceTemplate).filter(PriceTemplate.id == template_id).first()
    template.status = "archived"
    db.commit()
    db.refresh(template)
    return template
