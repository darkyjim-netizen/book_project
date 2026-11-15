from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# 도서 등록·수정에 필요한 필드와 값의 허용 범위를 정의합니다.
class ProductInput(BaseModel):
    title: str = Field(validation_alias=AliasChoices("title", "Title"), min_length=1, max_length=200)
    author: str = Field(validation_alias=AliasChoices("author", "Author"), min_length=1, max_length=200)
    price: int = Field(validation_alias=AliasChoices("price", "Price"), ge=0, le=100_000_000)
    stock: int = Field(validation_alias=AliasChoices("stock", "Stock"), ge=0, le=1_000_000)
    category_id: int = Field(validation_alias=AliasChoices("category_id", "CategoryId"), gt=0)


# 도서 객체를 기본 정보, ID, 등록 시각이 포함된 응답으로 변환합니다.
class ProductResponse(ProductInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
