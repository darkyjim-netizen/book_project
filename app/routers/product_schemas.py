from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ProductInput(BaseModel):
    title: str = Field(validation_alias=AliasChoices("title", "Title"), min_length=1, max_length=200)
    author: str = Field(validation_alias=AliasChoices("author", "Author"), min_length=1, max_length=200)
    price: int = Field(validation_alias=AliasChoices("price", "Price"), ge=0, le=100_000_000)
    stock: int = Field(validation_alias=AliasChoices("stock", "Stock"), ge=0, le=1_000_000)
    category_id: int = Field(validation_alias=AliasChoices("category_id", "CategoryId"), gt=0)


class ProductResponse(ProductInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
