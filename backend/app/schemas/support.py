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
    is_published: bool = True
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


# 1:1 채팅
class ChatRoomCreateRequest(BaseModel):
    """상담방 제목과 선택적인 첫 메시지를 받는다."""

    subject: str = Field("1:1 문의", max_length=200)
    first_message: Optional[str] = Field(None, max_length=2000)


class ChatMessageRequest(BaseModel):
    """전송할 메시지 본문과 선택적인 첨부파일 URL을 받는다."""

    content: str = Field(..., min_length=1, max_length=2000)
    attachment_url: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """메시지 본문, 발신자, 읽음 여부와 작성 시각을 반환한다."""

    model_config = ConfigDict(from_attributes=True)

    message_id: int
    room_id: int
    sender_id: Optional[int] = None
    sender_type: str
    content: str
    attachment_url: Optional[str] = None
    is_read: bool
    created_at: datetime


class ChatRoomResponse(BaseModel):
    """상담방 상태, 참여자, 최근 메시지와 대화 내역을 반환한다."""

    room_id: int
    room_uuid: str
    subject: str
    status: str
    member_id: int
    member_name: Optional[str] = None
    agent_id: Optional[int] = None  # 상담원이 배정되기 전에는 비어 있을 수 있다.
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None

    # 회원과 상담원이 아직 읽지 않은 메시지 수를 각각 표시한다.
    unread_user: int = 0
    unread_agent: int = 0
    created_at: datetime
    messages: List[ChatMessageResponse] = []


class ChatSatisfactionRequest(BaseModel):
    """상담 만족도를 1~5점 사이의 정수로 받는다."""

    satisfaction: int = Field(..., ge=1, le=5)
