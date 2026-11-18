"""1:1 채팅 상담 서비스와 WebSocket 연결 관리자."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from fastapi import WebSocket
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from team_backend.app.core.exceptions import BusinessError, NotFoundError
from team_backend.app.models.enums import ChatRoomStatus
from team_backend.app.models.member import Member
from team_backend.app.models.support import ChatMessage, ChatRoom
from team_backend.app.schemas.support import ChatMessageResponse, ChatRoomResponse

logger = logging.getLogger(__name__)


# 상담을 시작할 때 채팅방에 자동으로 보내는 안내 문구
WELCOME_MESSAGE = (
    "안녕하세요, 북스토어 고객센터입니다. "
    "문의 내용을 남겨 주시면 상담원이 순차적으로 답변드립니다. "
    "(상담 가능 시간: 평일 09:00 ~ 18:00)"
)


# 상담원과 연결되기 전에 자주 묻는 질문에 자동으로 답하는 규칙
# 각 규칙은 (검색할 키워드 묶음, 자동 답변)으로 구성된다.
AUTO_REPLY_RULES = [
    (
        ("배송", "언제", "도착"),
        "결제 완료 후 영업일 기준 1~3일 내 배송됩니다. "
        "마이페이지 > 주문 내역에서 배송 조회가 가능합니다.",
    ),
    (
        ("취소", "환불"),
        "상품 준비 중 단계까지는 마이페이지에서 직접 취소하실 수 있습니다. "
        "배송 시작 후에는 반품으로 접수해 주세요.",
    ),
    (
        ("배송비",),
        "2만 원 이상 구매 시 무료이며, 그 미만은 3,000원이 부과됩니다. "
        "회원 등급에 따라 무료 배송 기준이 달라집니다.",
    ),
    (
        ("포인트", "적립"),
        "구매 확정 시 결제 금액의 1~3%가 등급에 따라 적립되며, "
        "리뷰 작성 시 추가 적립됩니다.",
    ),
    (
        ("품절", "재입고"),
        "품절 도서는 재입고 알림을 신청하시면 입고 시 안내드립니다.",
    ),
]


# -----------------------------------------------------------------------------
# WebSocket 연결 관리
# -----------------------------------------------------------------------------
class ConnectionManager:
    """채팅방별 WebSocket 연결과 상담원 알림 연결을 관리한다."""

    def __init__(self) -> None:
        # 채팅방 번호별로 연결된 WebSocket들을 저장한다.
        # 예: {채팅방 번호: {연결1, 연결2}}
        self._rooms: Dict[int, Set[WebSocket]] = {}

        # 신규 문의 알림을 받을 상담원 WebSocket 연결 목록
        self._agents: Set[WebSocket] = set()

        # 여러 작업이 동시에 연결 목록을 변경할 때 충돌하지 않도록 잠금 객체를 둔다.
        self._lock = asyncio.Lock()

    async def connect(
        self,
        room_id: int,
        websocket: WebSocket,
    ) -> None:
        """사용자를 채팅방 WebSocket에 연결한다."""

        # 클라이언트와 WebSocket 연결을 수락한다.
        await websocket.accept()

        # 같은 시점에 여러 연결이 등록되어도 안전하도록 잠근 뒤 저장한다.
        async with self._lock:
            self._rooms.setdefault(room_id, set()).add(websocket)

        logger.info(
            "WebSocket 연결: room_id=%s 총 %d",
            room_id,
            len(self._rooms[room_id]),
        )

    async def connect_agent(self, websocket: WebSocket) -> None:
        """상담원을 신규 문의 알림용 WebSocket에 연결한다."""

        await websocket.accept()

        # 상담원 연결 목록에 등록한다.
        async with self._lock:
            self._agents.add(websocket)

    async def disconnect(
        self,
        room_id: int,
        websocket: WebSocket,
    ) -> None:
        """채팅방 또는 상담원 알림 연결에서 WebSocket을 제거한다."""

        async with self._lock:
            # 해당 채팅방 연결 목록에서 제거한다.
            conns = self._rooms.get(room_id)
            if conns and websocket in conns:
                conns.remove(websocket)

            # 연결이 하나도 남지 않은 방은 목록에서 지운다.
            if conns is not None and not conns:
                self._rooms.pop(room_id, None)

            # 상담원 연결 목록에도 있을 수 있으므로 함께 제거한다.
            self._agents.discard(websocket)

    async def broadcast(
        self,
        room_id: int,
        message: dict,
    ) -> None:
        """특정 채팅방에 연결된 모든 사람에게 메시지를 보낸다."""

        # dict 데이터를 WebSocket으로 보낼 수 있도록 JSON 문자열로 바꾼다.
        # ensure_ascii=False는 한글이 유니코드 이스케이프 문자로 바뀌지 않게 한다.
        payload = json.dumps(
            message,
            ensure_ascii=False,
            default=str,
        )

        # 전송에 실패한 연결은 나중에 목록에서 제거한다.
        dead: List[WebSocket] = []

        # 연결 목록을 복사해 순회하면서 각 참여자에게 메시지를 보낸다.
        for websocket in list(self._rooms.get(room_id, set())):
            try:
                await websocket.send_text(payload)
            except Exception:  # pragma: no cover
                dead.append(websocket)

        # 끊어진 연결을 채팅방 연결 목록에서 정리한다.
        for websocket in dead:
            await self.disconnect(room_id, websocket)

    async def notify_agents(self, message: dict) -> None:
        """연결된 상담원 전체에게 알림을 보낸다."""

        payload = json.dumps(
            message,
            ensure_ascii=False,
            default=str,
        )

        # 신규 문의 등의 알림을 모든 상담원 연결에 전달한다.
        for websocket in list(self._agents):
            try:
                await websocket.send_text(payload)
            except Exception:  # pragma: no cover
                # 전송이 실패한 상담원 연결은 목록에서 제거한다.
                self._agents.discard(websocket)

    def room_connection_count(self, room_id: int) -> int:
        """해당 채팅방에 현재 연결된 WebSocket 수를 반환한다."""

        return len(self._rooms.get(room_id, set()))


# 애플리케이션 전체에서 공유하는 WebSocket 연결 관리자
manager = ConnectionManager()


# -----------------------------------------------------------------------------
# 채팅 서비스
# -----------------------------------------------------------------------------
class ChatService:
    """채팅방, 메시지, 자동응답 등 DB 작업을 담당한다."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ 응답 변환
    @staticmethod
    def to_response(
        room: ChatRoom,
        include_messages: bool = False,
    ) -> ChatRoomResponse:
        """채팅방 DB 객체를 API 응답 형식으로 바꾼다."""

        return ChatRoomResponse(
            room_id=room.room_id,
            room_uuid=str(room.room_uuid),
            subject=room.subject,
            status=room.status.value,
            member_id=room.member_id,
            member_name=room.member.name if room.member else None,
            agent_id=room.agent_id,
            last_message=room.last_message,
            last_message_at=room.last_message_at,
            unread_user=room.unread_user,
            unread_agent=room.unread_agent,
            created_at=room.created_at,
            # include_messages=True일 때만 방 안의 메시지도 응답에 넣는다.
            # 메시지는 오래된 순서대로 정렬한다.
            messages=(
                [
                    ChatMessageResponse.model_validate(message)
                    for message in sorted(
                        room.messages,
                        key=lambda message: message.created_at,
                    )
                ]
                if include_messages
                else []
            ),
        )

    # ------------------------------------------------------------------ 채팅방 관리
    def create_room(
        self,
        member: Member,
        subject: str,
        first_message: Optional[str] = None,
    ) -> ChatRoom:
        """새 채팅방을 만들거나 회원의 기존 상담방을 재사용한다."""

        # 회원에게 종료되지 않은 채팅방이 이미 있는지 찾는다.
        existing = self.db.scalar(
            select(ChatRoom)
            .options(selectinload(ChatRoom.messages))
            .where(
                ChatRoom.member_id == member.member_id,
                ChatRoom.status != ChatRoomStatus.CLOSED,
            )
            .order_by(ChatRoom.created_at.desc())
        )

        # 진행 중인 상담방이 있으면 새로 만들지 않고 기존 방을 반환한다.
        if existing is not None:
            return existing

        # 진행 중인 방이 없으면 새 상담방을 만든다.
        room = ChatRoom(
            member_id=member.member_id,
            subject=subject,
        )
        self.db.add(room)

        # flush를 호출하면 DB에 INSERT를 보내 room_id를 먼저 확보할 수 있다.
        # 아직 최종 저장(commit)되지는 않는다.
        self.db.flush()

        # 새 상담방에 시스템 환영 메시지를 등록한다.
        self.db.add(
            ChatMessage(
                room_id=room.room_id,
                sender_type="SYSTEM",
                content=WELCOME_MESSAGE,
                is_read=True,
            )
        )

        # 채팅방 목록에서 보여줄 최근 메시지와 시각도 갱신한다.
        room.last_message = WELCOME_MESSAGE[:500]
        room.last_message_at = datetime.now(timezone.utc)

        # 첫 문의 내용이 함께 전달된 경우 사용자 메시지도 저장한다.
        if first_message:
            self.db.add(
                ChatMessage(
                    room_id=room.room_id,
                    sender_id=member.member_id,
                    sender_type="USER",
                    content=first_message,
                )
            )

            # 채팅방 목록에 첫 문의 내용을 최근 메시지로 표시한다.
            room.last_message = first_message[:500]

            # 상담원이 아직 읽지 않은 메시지 수를 1 늘린다.
            room.unread_agent += 1

        self.db.commit()
        self.db.refresh(room)

        logger.info(
            "채팅방 생성: room_id=%s member_id=%s",
            room.room_id,
            member.member_id,
        )
        return room

    def get_room(
        self,
        room_id: int,
        member: Optional[Member] = None,
    ) -> ChatRoom:
        """채팅방을 조회하고, 회원이 전달되면 조회 권한도 확인한다."""

        room = self.db.scalar(
            select(ChatRoom)
            .options(
                selectinload(ChatRoom.messages),
                selectinload(ChatRoom.member),
            )
            .where(ChatRoom.room_id == room_id)
        )

        if room is None:
            raise NotFoundError("채팅방을 찾을 수 없습니다.")

        # 일반 회원은 자신의 채팅방만 볼 수 있다.
        # 관리자는 다른 회원의 채팅방도 조회할 수 있다.
        if (
            member is not None
            and not member.is_admin
            and room.member_id != member.member_id
        ):
            raise BusinessError(
                "본인의 상담만 조회할 수 있습니다.",
                status_code=403,
            )

        return room

    def list_my_rooms(self, member: Member) -> List[ChatRoom]:
        """회원 본인의 채팅방 목록을 최신순으로 조회한다."""

        return list(
            self.db.scalars(
                select(ChatRoom)
                .options(selectinload(ChatRoom.member))
                .where(ChatRoom.member_id == member.member_id)
                .order_by(ChatRoom.created_at.desc())
            ).unique()
        )

    def list_rooms_admin(
        self,
        page: int = 1,
        size: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[ChatRoom], int]:
        """관리자용 채팅방 목록과 전체 건수를 조회한다."""

        conditions = []

        # 상태 조건이 전달되면 해당 상태의 채팅방만 조회한다.
        if status:
            conditions.append(
                ChatRoom.status == ChatRoomStatus(status)
            )

        # 페이지와 관계없이 조건에 맞는 전체 채팅방 수를 계산한다.
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(ChatRoom)
                .where(*conditions)
            )
            or 0
        )

        # 최근 메시지가 있는 방을 먼저 보여주고, 페이지에 맞는 수만 가져온다.
        rows = list(
            self.db.scalars(
                select(ChatRoom)
                .options(selectinload(ChatRoom.member))
                .where(*conditions)
                .order_by(ChatRoom.last_message_at.desc().nullslast())
                .offset((page - 1) * size)
                .limit(size)
            ).unique()
        )

        return rows, total

    def assign_agent(
        self,
        room_id: int,
        agent: Member,
    ) -> ChatRoom:
        """관리자 또는 상담원을 채팅방에 배정한다."""

        room = self.get_room(room_id)

        # 종료된 채팅방에는 상담원을 배정할 수 없다.
        if room.status == ChatRoomStatus.CLOSED:
            raise BusinessError("종료된 상담입니다.")

        room.agent_id = agent.member_id
        room.status = ChatRoomStatus.ASSIGNED

        self.db.commit()
        self.db.refresh(room)
        return room

    def close_room(
        self,
        room_id: int,
        member: Member,
    ) -> ChatRoom:
        """채팅 상담을 종료한다."""

        # 회원이 전달되므로 본인의 채팅방인지 확인한다.
        room = self.get_room(room_id, member)

        room.status = ChatRoomStatus.CLOSED
        room.closed_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(room)
        return room

    def rate_satisfaction(
        self,
        room_id: int,
        member: Member,
        score: int,
    ) -> ChatRoom:
        """종료된 상담에 회원이 만족도 점수를 등록한다."""

        room = self.get_room(room_id, member)

        # 상담이 끝난 뒤에만 만족도를 등록할 수 있다.
        if room.status != ChatRoomStatus.CLOSED:
            raise BusinessError("상담 종료 후 평가할 수 있습니다.")

        room.satisfaction = score

        self.db.commit()
        self.db.refresh(room)
        return room

    # ------------------------------------------------------------------ 메시지 관리
    def save_message(
        self,
        room_id: int,
        sender: Optional[Member],
        content: str,
        sender_type: str = "USER",
        attachment_url: Optional[str] = None,
    ) -> ChatMessage:
        """메시지를 저장하고 채팅방의 최근 메시지와 안 읽은 수를 갱신한다."""

        room = self.db.get(ChatRoom, room_id)
        if room is None:
            raise NotFoundError("채팅방을 찾을 수 없습니다.")

        # 종료된 채팅방에는 메시지를 추가할 수 없다.
        if room.status == ChatRoomStatus.CLOSED:
            raise BusinessError("종료된 상담에는 메시지를 보낼 수 없습니다.")

        # 보낸 사람, 내용, 첨부 파일 주소를 메시지 객체로 만든다.
        message = ChatMessage(
            room_id=room_id,
            sender_id=sender.member_id if sender else None,
            sender_type=sender_type,
            content=content,
            attachment_url=attachment_url,
        )
        self.db.add(message)

        # 채팅방 목록에서 보여줄 최근 메시지와 전송 시각을 갱신한다.
        room.last_message = content[:500]
        room.last_message_at = datetime.now(timezone.utc)

        # 사용자가 보내면 상담원이 읽지 않은 수를 늘린다.
        if sender_type == "USER":
            room.unread_agent += 1

        # 상담원이 보내면 사용자가 읽지 않은 수를 늘린다.
        elif sender_type == "AGENT":
            room.unread_user += 1

        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(
        self,
        room_id: int,
        member: Optional[Member] = None,
        before_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[ChatMessage]:
        """채팅 메시지를 조회한다. before_id를 사용해 이전 메시지를 더 불러올 수 있다."""

        # 방이 존재하는지, 회원이 전달되었다면 볼 권한이 있는지 확인한다.
        self.get_room(room_id, member)

        conditions = [ChatMessage.room_id == room_id]

        # 특정 메시지보다 이전에 작성된 메시지만 가져오도록 조건을 추가한다.
        if before_id:
            conditions.append(ChatMessage.message_id < before_id)

        # 최근 메시지부터 limit개를 가져온다.
        rows = list(
            self.db.scalars(
                select(ChatMessage)
                .where(*conditions)
                .order_by(ChatMessage.message_id.desc())
                .limit(limit)
            ).unique()
        )

        # 화면에는 오래된 메시지가 위에 오도록 순서를 뒤집어 반환한다.
        return list(reversed(rows))

    def mark_read(
        self,
        room_id: int,
        reader_type: str,
    ) -> int:
        """읽는 사람의 반대편에서 보낸 메시지를 읽음 처리한다."""

        # 사용자가 읽는다면 상담원 메시지를, 상담원이 읽는다면 사용자 메시지를 처리한다.
        opposite = "AGENT" if reader_type == "USER" else "USER"

        # 해당 방에서 상대방이 보낸 읽지 않은 메시지를 모두 읽음으로 변경한다.
        updated = (
            self.db.query(ChatMessage)
            .filter(
                ChatMessage.room_id == room_id,
                ChatMessage.sender_type == opposite,
                ChatMessage.is_read == False,  # noqa: E712
            )
            .update(
                {ChatMessage.is_read: True},
                synchronize_session=False,
            )
        )

        # 채팅방에 저장된 읽지 않은 메시지 수도 0으로 초기화한다.
        room = self.db.get(ChatRoom, room_id)
        if room:
            if reader_type == "USER":
                room.unread_user = 0
            else:
                room.unread_agent = 0

        self.db.commit()

        # 실제로 읽음 상태가 바뀐 메시지 수를 반환한다.
        return updated

    # ------------------------------------------------------------------ 자동응답
    @staticmethod
    def auto_reply(content: str) -> Optional[str]:
        """메시지에 키워드가 있는지 확인해 자동 답변을 반환한다."""

        # 띄어쓰기가 달라도 키워드를 찾을 수 있도록 공백을 제거한다.
        text = content.replace(" ", "")

        for keywords, answer in AUTO_REPLY_RULES:
            # 한 규칙에 키워드가 여러 개면 모두 포함된 경우 답변한다.
            # 단, 길이가 3글자 이상인 키워드 하나만 있어도 답변할 수 있다.
            if all(keyword in text for keyword in keywords) or any(
                keyword in text
                for keyword in keywords
                if len(keyword) >= 3
            ):
                return answer

        # 어떤 규칙에도 해당하지 않으면 자동 답변을 보내지 않는다.
        return None

    def open_room_count(self) -> int:
        """아직 종료되지 않은 새 상담방 수를 반환한다."""

        return (
            self.db.scalar(
                select(func.count())
                .select_from(ChatRoom)
                .where(ChatRoom.status == ChatRoomStatus.OPEN)
            )
            or 0
        )

    def satisfaction_avg(self) -> Optional[float]:
        """등록된 상담 만족도 점수의 평균을 반환한다."""

        value = self.db.scalar(
            select(func.avg(ChatRoom.satisfaction))
        )

        # 아직 평가가 없으면 None, 평가가 있으면 실수형 평균을 반환한다.
        return float(value) if value is not None else None