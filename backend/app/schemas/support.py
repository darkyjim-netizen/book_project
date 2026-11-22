"""공지 / Q&A / FAQ / 채팅 스키마."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# 공지사항
class NoticeCreateRequest(BaseModel):
    """공지사항을 등록할 때 필요한 정보를 받는다."""

    category: str = Field("GENERAL", max_length=30)
    title: str = Field(..., max_length=250)
    content: str = Field(..., min_length=1)
    is_pinned: bool = False  # 상단 고정 여부
    is_published: bool = True  # 공개 여부


class NoticeUpdateRequest(BaseModel):
    """공지사항 수정 요청에서 각 필드를 선택적으로 받는다."""

    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_published: Optional[bool] = None


class NoticeResponse(BaseModel):
    """공지사항의 제목, 본문, 조회수와 게시 시각을 반환한다."""

    # ORM 객체의 속성에서 응답 필드를 읽을 수 있도록 한다.
    model_config = ConfigDict(from_attributes=True)

    notice_id: int
    category: str
    title: str
    content: Optional[str] = None
    is_pinned: bool
    view_count: int
    published_at: datetime


# Q&A
class QnaCreateRequest(BaseModel):
    """새 문의의 제목, 본문, 관련 도서나 주문 정보를 받는다."""

    category: str = Field("ETC", max_length=30)
    title: str = Field(..., max_length=250)
    content: str = Field(..., min_length=1)
    book_id: Optional[int] = None
    order_id: Optional[int] = None
    is_secret: bool = False  # 비공개 문의 여부


class QnaAnswerRequest(BaseModel):
    """문의에 등록할 답변 본문을 받는다."""

    content: str = Field(..., min_length=1)


class QnaAnswerResponse(BaseModel):
    """답변 ID, 본문, 작성 시각을 반환한다."""

    model_config = ConfigDict(from_attributes=True)

    answer_id: int
    content: str
    created_at: datetime


class QnaResponse(BaseModel):
    """문의의 처리 상태, 작성자, 관련 도서와 답변 목록을 반환한다."""

    question_id: int
    category: str
    title: str
    content: Optional[str] = None
    status: str
    is_secret: bool
    member_name: str
    book_id: Optional[int] = None
    book_title: Optional[str] = None
    view_count: int
    answers: List[QnaAnswerResponse] = []
    created_at: datetime


# FAQ
class FaqResponse(BaseModel):
    """자주 묻는 질문의 내용과 표시 순서를 반환한다."""

    model_config = ConfigDict(from_attributes=True)

    faq_id: int
    category: str
    question: str
    answer: str
    sort_order: int


class FaqCreateRequest(BaseModel):
    """FAQ 등록에 필요한 질문과 답변, 표시 설정을 받는다."""

    category: str = Field("GENERAL", max_length=30)
    question: str = Field(..., max_length=300)
    answer: str = Field(..., min_length=1)
    sort_order: int = 0
    is_active: bool = True
