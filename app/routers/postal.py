"""우편번호와 주소 검색 API."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import StringConstraints

from app.services.postal_service import search_addresses


router = APIRouter(prefix="/postal", tags=["우편번호"])


@router.get("/search")
def search_postal_addresses(
    # 검색어의 앞뒤 공백을 제거한 뒤 1~200자인지 검사한다.
    keyword: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)],
    # 페이지 번호는 1부터 시작하며, 생략하면 첫 페이지를 조회한다.
    page: Annotated[int, Query(ge=1)] = 1,
) -> list[dict[str, str]]:
    # 서비스가 반환한 주소 목록을 FastAPI가 JSON 배열로 변환한다.
    return search_addresses(keyword, page)
