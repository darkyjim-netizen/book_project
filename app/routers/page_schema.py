from typing import Generic, TypeVar

from pydantic import BaseModel


Item = TypeVar("Item")


# 여러 종류의 목록에서 재사용할 페이지 응답 형식을 정의합니다.
class PageResponse(BaseModel, Generic[Item]):
    items: list[Item]
    total: int
    page: int
    size: int
