"""API에서 사용할 공통 응답 데이터 형식."""
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field


# 여러 응답에서 재사용할 데이터 타입 자리표시자
# 예: ApiResponse[Book]이면 T가 Book이 된다.
T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """데이터 하나를 반환할 때 사용하는 표준 응답 형식."""

    success: bool = True  # 요청 성공 여부
    message: Optional[str] = None  # 화면에 표시할 안내 문구. 없을 수도 있다.
    data: Optional[T] = None  # 실제 응답 데이터. 타입 T는 API마다 다르게 지정한다.


class PageMeta(BaseModel):
    """목록을 여러 페이지로 나눠 보여줄 때 필요한 정보."""

    # Field는 값의 유효 범위와 API 문서에 표시할 설명을 지정한다.
    page: int = Field(
        1,
        ge=1,  # 1보다 작을 수 없다.
        description="현재 페이지(1-base)",  # 페이지 번호는 1부터 시작한다.
    )
    size: int = Field(
        20,
        ge=1,   # 페이지당 항목 수는 최소 1개
        le=100,  # 페이지당 항목 수는 최대 100개
        description="페이지 당 건수",
    )
    total: int = Field(
        0,
        ge=0,  # 전체 건수는 음수가 될 수 없다.
        description="전체 건수",
    )
    total_pages: int = Field(
        0,
        ge=0,  # 페이지 수는 음수가 될 수 없다.
        description="전체 페이지 수",
    )

    @classmethod
    def build(cls, page: int, size: int, total: int) -> "PageMeta":
        """전체 건수와 페이지 크기로 전체 페이지 수를 계산한다."""

        # 올림 나눗셈이다.
        # 예: 전체 41건을 페이지당 20건씩 보여주면 총 3페이지다.
        # size가 0이면 나눗셈 오류를 피하도록 0을 사용한다.
        total_pages = (total + size - 1) // size if size else 0

        # 계산한 값을 포함해 PageMeta 객체를 만들어 반환한다.
        return cls(
            page=page,
            size=size,
            total=total,
            total_pages=total_pages,
        )


class PageResponse(BaseModel, Generic[T]):
    """여러 항목과 페이지 정보를 함께 반환하는 응답 형식."""

    success: bool = True  # 요청 성공 여부
    items: List[T] = []  # 현재 페이지에 포함된 항목 목록
    meta: PageMeta = PageMeta()  # 현재 페이지와 전체 건수 등의 정보


class ErrorDetail(BaseModel):
    """오류의 종류와 설명."""

    code: str  # 프로그램에서 오류를 구분할 코드
    message: str  # 사용자가 이해할 수 있는 오류 메시지
    detail: Optional[object] = None  # 검증 실패 항목 등 추가 설명. 형식은 달라질 수 있다.


class ErrorResponse(BaseModel):
    """오류가 발생했을 때 반환하는 응답 형식."""

    success: bool = False  # 오류 응답이므로 기본값은 실패
    error: ErrorDetail  # 오류 코드, 메시지, 상세 정보


class MessageResponse(BaseModel):
    """데이터 없이 안내 메시지만 반환할 때 사용하는 응답 형식."""

    success: bool = True  # 요청 성공 여부
    message: str  # 사용자에게 보여줄 안내 문구