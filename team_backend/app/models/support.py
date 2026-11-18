"""공지, 문의, FAQ, 상담 채팅의 ORM 모델."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID as PgUUID
# Mapped는 파이썬에서 사용할 자료형을, mapped_column은 DB 컬럼 설정을 나타낸다.
# relationship은 외래 키로 연결된 행을 파이썬 객체나 목록으로 읽게 해 준다.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Base를 상속한 모델은 SQLAlchemy에 테이블 정의를 등록한다.
from team_backend.app.core.database import Base
from team_backend.app.models.enums import ChatRoomStatus, QnaStatus
from team_backend.app.models.member import Member


# 공지 한 건의 제목, 본문, 공개 설정을 저장한다.
class Notice(Base):
    # 스키마 이름과 테이블 이름을 합치면 DB에서 shop.notices를 가리킨다.
    __tablename__ = "notices"
    __table_args__ = {"schema": "shop"}

    # 기본 키(primary_key)는 테이블에서 각 공지를 구분하는 고유 번호다.
    notice_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # String(30)은 최대 30글자다. 값을 생략해 저장하면 DB가 기본값을 넣는다.
    category: Mapped[str] = mapped_column(String(30), server_default="GENERAL")
    title: Mapped[str] = mapped_column(String(250))
    content: Mapped[str] = mapped_column(Text)
    # is_pinned는 상단 고정 여부, is_published는 공개 여부다.
    is_pinned: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_published: Mapped[bool] = mapped_column(Boolean, server_default="true")
    view_count: Mapped[int] = mapped_column(Integer, server_default="0")
    # 작성자 번호는 회원 테이블을 참조한다. int | None은 값을 비워 둘 수 있다는 뜻이다.
    author_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("shop.members.member_id"))
    # 공개·등록·수정 시각을 저장한다. func.now()는 저장 시 DB의 현재 시각을 넣는다.
    # 이 기본값만으로는 행을 수정할 때 updated_at이 자동 갱신되지 않는다.
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # notice.attachments로 첨부파일 목록을 읽는다. 공지를 삭제하면 첨부 행은 DB가 지운다.
    attachments: Mapped[list["NoticeAttachment"]] = relationship(passive_deletes="all")


# 공지에 첨부된 파일 한 개의 이름, 주소, 크기를 저장한다.
class NoticeAttachment(Base):
    __tablename__ = "notice_attachments"
    __table_args__ = {"schema": "shop"}

    # notice_id로 어느 공지의 파일인지 연결한다. CASCADE는 공지를 지울 때 첨부 행도 지운다.
    attachment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    notice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shop.notices.notice_id", ondelete="CASCADE")
    )
    file_name: Mapped[str] = mapped_column(String(255))
    file_url: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer, server_default="0")


# 회원이 올린 문의 한 건을 저장한다.
class QnaQuestion(Base):
    __tablename__ = "qna_questions"
    __table_args__ = {"schema": "shop"}

    question_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shop.members.member_id", ondelete="CASCADE")
    )
    # 도서와 주문은 선택 사항이다. 연결 대상이 삭제되면 문의는 남기고 해당 번호만 비운다.
    book_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("shop.books.book_id", ondelete="SET NULL")
    )
    order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("shop.orders.order_id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(30), server_default="ETC")
    title: Mapped[str] = mapped_column(String(250))
    content: Mapped[str] = mapped_column(Text)
    # 문의 상태는 DB에 이미 있는 상태값 목록(ENUM)을 사용한다. 처음에는 답변 대기다.
    status: Mapped[QnaStatus] = mapped_column(
        ENUM(QnaStatus, name="qna_status", schema="shop", create_type=False),
        server_default=QnaStatus.WAITING.value,
    )
    is_secret: Mapped[bool] = mapped_column(Boolean, server_default="false")
    view_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # question.member로 작성자 정보를, question.answers로 답변 목록을 읽는다.
    member: Mapped[Member] = relationship()
    answers: Mapped[list["QnaAnswer"]] = relationship(
        order_by="QnaAnswer.answer_id", passive_deletes="all"
    )


# 문의에 달린 답변 한 건을 저장한다. 문의가 삭제되면 답변도 함께 삭제된다.
class QnaAnswer(Base):
    __tablename__ = "qna_answers"
    __table_args__ = {"schema": "shop"}

    answer_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shop.qna_questions.question_id", ondelete="CASCADE")
    )
    admin_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("shop.members.member_id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# 자주 묻는 질문과 답변을 저장한다.
class Faq(Base):
    __tablename__ = "faqs"
    __table_args__ = {"schema": "shop"}

    faq_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # String(30)은 최대 30글자다. 값을 생략해 저장하면 DB가 기본값을 넣는다.
    category: Mapped[str] = mapped_column(String(30), server_default="GENERAL")
    question: Mapped[str] = mapped_column(String(300))
    answer: Mapped[str] = mapped_column(Text)
    # sort_order는 화면에 보여 줄 순서, is_active는 노출 여부를 나타낸다.
    sort_order: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    view_count: Mapped[int] = mapped_column(Integer, server_default="0")


# 상담 채팅방의 참여자, 상담 상태, 마지막 메시지 정보를 저장한다.
class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    __table_args__ = {"schema": "shop"}

    room_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # DB가 임의의 UUID를 생성한다. 이 값은 숫자로 된 기본 키(room_id)와 별도다.
    room_uuid: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), server_default=func.gen_random_uuid())
    member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shop.members.member_id", ondelete="CASCADE")
    )
    agent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("shop.members.member_id"))
    subject: Mapped[str] = mapped_column(String(200), server_default="1:1 문의")
    # 채팅방은 생성할 때 OPEN(열림) 상태로 시작한다.
    status: Mapped[ChatRoomStatus] = mapped_column(
        ENUM(ChatRoomStatus, name="chat_room_status", schema="shop", create_type=False),
        server_default=ChatRoomStatus.OPEN.value,
    )
    last_message: Mapped[str | None] = mapped_column(String(500))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 회원과 상담원이 아직 읽지 않은 메시지 수를 각각 저장한다.
    unread_user: Mapped[int] = mapped_column(Integer, server_default="0")
    unread_agent: Mapped[int] = mapped_column(Integer, server_default="0")
    satisfaction: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 회원과 상담원이 같은 테이블에 있으므로 회원 관계에 사용할 키를 지정한다.
    member: Mapped[Member] = relationship(foreign_keys=[member_id])
    # room.messages로 채팅 내역을 읽는다. 방 삭제 시 메시지 행은 DB가 지운다.
    messages: Mapped[list["ChatMessage"]] = relationship(passive_deletes="all")


# 채팅방에서 주고받은 메시지 한 건을 저장한다.
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = {"schema": "shop"}

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    room_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shop.chat_rooms.room_id", ondelete="CASCADE")
    )
    # sender_id는 보낸 사람의 회원 번호, sender_type은 보낸 사람의 구분이다.
    sender_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("shop.members.member_id"))
    sender_type: Mapped[str] = mapped_column(String(10), server_default="USER")
    content: Mapped[str] = mapped_column(Text)
    # 첨부가 없으면 URL은 비어 있고, 새 메시지는 읽지 않은 상태로 저장된다.
    attachment_url: Mapped[str | None] = mapped_column(String(255))
    is_read: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
