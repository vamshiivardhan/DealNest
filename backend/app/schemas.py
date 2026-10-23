from pydantic import BaseModel, ConfigDict


class DealResponse(BaseModel):
    id: int
    product_name: str
    brand: str | None
    category: str | None
    mrp: float
    selling_price: float
    discount_pct: float
    image_url: str | None
    url: str
    platform: str
    in_stock: bool

    model_config = ConfigDict(from_attributes=True)
