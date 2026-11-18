"""1:1 채팅 상담 API와 WebSocket 라우터."""
import json
import logging
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.security import decode_token, get_current_member, require_admin
from app.models.member import Member
from app.schemas.common import MessageResponse, PageMeta, PageResponse
from app.schemas.support import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatRoomCreateRequest,
    ChatRoomResponse,
    ChatSatisfactionRequest,
)
from app.services.chat_service import ChatService, manager

logger = logging.getLogger(__name__)

# 회원용 채팅 API 주소는 /chat으로 시작한다.
router = APIRouter(prefix="/chat", tags=["1:1 채팅상담"])


# -----------------------------------------------------------------------------
# REST API
# -----------------------------------------------------------------------------
@router.post(
    "/rooms",
    response_model=ChatRoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="상담 시작",
)
def create_room(
    payload: ChatRoomCreateRequest,  # 상담 제목과 첫 문의 내용
    member: Member = Depends(get_current_member),  # 로그인 회원 확인
    db: Session = Depends(get_db),  # 요청에서 사용할 DB 세션
):
    """채팅방을 만든다. 진행 중인 상담방이 있으면 기존 방을 재사용한다."""

    service = ChatService(db)

    # 채팅방 생성은 서비스에서 처리한다.
    room = service.create_room(
        member,
        payload.subject,
        payload.first_message,
    )

    # 새 상담방과 메시지를 함께 응답으로 반환한다.
    return service.to_response(room, include_messages=True)


@router.get(
    "/rooms",
    response_model=List[ChatRoomResponse],
    summary="내 상담 목록",
)
def list_my_rooms(
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """로그인 회원이 만든 채팅방 목록을 조회한다."""

    service = ChatService(db)

    # 회원의 채팅방마다 응답 형식으로 변환해 반환한다.
    return [
        service.to_response(room)
        for room in service.list_my_rooms(member)
    ]


@router.get(
    "/rooms/{room_id}",
    response_model=ChatRoomResponse,
    summary="상담 상세",
)
def get_room(
    room_id: int,  # 조회할 채팅방 번호
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """채팅방 정보와 메시지를 조회하고, 상대방이 보낸 메시지를 읽음 처리한다."""

    service = ChatService(db)

    # 채팅방 존재 여부와 회원의 조회 권한을 확인한다.
    room = service.get_room(room_id, member)

    # 관리자는 사용자 메시지를, 일반 회원은 상담원 메시지를 읽은 것으로 표시한다.
    reader_type = "AGENT" if member.is_admin else "USER"
    service.mark_read(room_id, reader_type)

    # 메시지 내역을 포함해 응답한다.
    return service.to_response(room, include_messages=True)


@router.get(
    "/rooms/{room_id}/messages",
    response_model=List[ChatMessageResponse],
    summary="메시지 조회",
)
def list_messages(
    room_id: int,
    # 전달하면 해당 메시지보다 이전의 메시지를 가져온다(무한 스크롤용).
    before_id: Optional[int] = Query(
        None,
        description="이 ID 이전 메시지를 조회(무한 스크롤)",
    ),
    limit: int = Query(50, ge=1, le=200),  # 한 번에 가져올 메시지 수
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """채팅방 메시지를 커서 기준으로 조회한다."""

    rows = ChatService(db).list_messages(
        room_id,
        member,
        before_id,
        limit,
    )

    # DB 메시지 객체를 API 응답 형식으로 변환한다.
    return [
        ChatMessageResponse.model_validate(message)
        for message in rows
    ]


@router.post(
    "/rooms/{room_id}/messages",
    response_model=ChatMessageResponse,
    summary="메시지 전송(REST)",
)
def send_message(
    room_id: int,
    payload: ChatMessageRequest,  # 메시지 내용과 선택적 첨부 파일 주소
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """WebSocket을 사용할 수 없는 경우 REST 방식으로 메시지를 보낸다."""

    service = ChatService(db)

    # 해당 회원이 채팅방을 사용할 권한이 있는지 확인한다.
    service.get_room(room_id, member)

    # 관리자 계정이면 상담원 메시지, 그 외에는 사용자 메시지로 저장한다.
    sender_type = "AGENT" if member.is_admin else "USER"

    message = service.save_message(
        room_id,
        member,
        payload.content,
        sender_type,
        payload.attachment_url,
    )

    return ChatMessageResponse.model_validate(message)


@router.post(
    "/rooms/{room_id}/close",
    response_model=MessageResponse,
    summary="상담 종료",
)
def close_room(
    room_id: int,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """회원이 상담을 종료한다."""

    ChatService(db).close_room(room_id, member)
    return MessageResponse(message="상담이 종료되었습니다.")


@router.post(
    "/rooms/{room_id}/satisfaction",
    response_model=MessageResponse,
    summary="상담 만족도 평가",
)
def rate(
    room_id: int,
    payload: ChatSatisfactionRequest,  # 회원이 선택한 만족도 점수
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """상담 종료 후 회원이 만족도를 등록한다."""

    ChatService(db).rate_satisfaction(
        room_id,
        member,
        payload.satisfaction,
    )
    return MessageResponse(message="평가가 등록되었습니다. 감사합니다.")


# -----------------------------------------------------------------------------
# WebSocket 실시간 채팅
# -----------------------------------------------------------------------------
@router.websocket("/ws/{room_id}")
async def chat_websocket(
    websocket: WebSocket,
    room_id: int,
    # WebSocket 주소의 쿼리 문자열에서 인증 토큰을 받는다.
    token: str = Query(...),
):
    """실시간 채팅용 WebSocket 연결을 처리한다.

    클라이언트가 보내는 JSON 예시:
        {"type": "message", "content": "문의 내용"}
        {"type": "typing"}
        {"type": "read"}

    서버가 보내는 JSON 예시:
        {"type": "message", "message_id": 1, "sender_type": "USER",
         "content": "문의 내용", "created_at": "2026-01-01T10:00:00+09:00"}
    """

    # 일반 REST 요청의 DB 의존성을 사용할 수 없으므로 직접 DB 세션을 연다.
    db = SessionLocal()
    member: Optional[Member] = None

    # 토큰을 확인해 현재 연결한 회원을 찾는다.
    try:
        payload = decode_token(token)
        member = db.get(Member, int(payload["sub"]))

    except Exception:
        # 토큰이 없거나 잘못된 경우 연결을 거부한다.
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION
        )
        db.close()
        return

    if member is None:
        # 토큰은 읽었지만 해당 회원이 DB에 없으면 연결을 거부한다.
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION
        )
        db.close()
        return

    service = ChatService(db)

    # 해당 회원이 이 채팅방을 볼 권한이 있는지 확인한다.
    try:
        service.get_room(room_id, member)
    except Exception:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION
        )
        db.close()
        return

    # 관리자는 상담원, 일반 회원은 사용자로 메시지를 구분한다.
    sender_type = "AGENT" if member.is_admin else "USER"

    # 채팅방의 WebSocket 연결 목록에 현재 연결을 추가한다.
    await manager.connect(room_id, websocket)

    try:
        # 연결이 완료됐음을 클라이언트에 알린다.
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connected",
                    "room_id": room_id,
                    "sender_type": sender_type,
                },
                ensure_ascii=False,
            )
        )

        # 연결이 유지되는 동안 클라이언트 메시지를 계속 기다린다.
        while True:
            raw = await websocket.receive_text()

            # 우선 수신한 문장을 JSON으로 해석한다.
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # JSON이 아니면 일반 메시지로 간주한다.
                data = {
                    "type": "message",
                    "content": raw,
                }

            # type이 없으면 일반 메시지 이벤트로 처리한다.
            event = data.get("type", "message")

            if event == "typing":
                # 입력 중 알림은 DB에 저장하지 않고 상대방에게 바로 보낸다.
                await manager.broadcast(
                    room_id,
                    {
                        "type": "typing",
                        "sender_type": sender_type,
                    },
                )
                continue

            if event == "read":
                # 상대방 메시지를 읽음 처리하고 채팅방 참여자에게 알린다.
                service.mark_read(room_id, sender_type)
                await manager.broadcast(
                    room_id,
                    {
                        "type": "read",
                        "sender_type": sender_type,
                    },
                )
                continue

            # 메시지 앞뒤 공백을 제거한다.
            content = (data.get("content") or "").strip()

            # 내용이 비어 있으면 저장하거나 전송하지 않는다.
            if not content:
                continue

            # 메시지를 DB에 저장하고 채팅방 요약 정보도 갱신한다.
            message = service.save_message(
                room_id,
                member,
                content,
                sender_type,
                data.get("attachment_url"),
            )

            # 저장된 메시지를 해당 방에 연결된 모든 사람에게 전송한다.
            await manager.broadcast(
                room_id,
                {
                    "type": "message",
                    "message_id": message.message_id,
                    "sender_id": message.sender_id,
                    "sender_type": message.sender_type,
                    "content": message.content,
                    "attachment_url": message.attachment_url,
                    "created_at": message.created_at,
                },
            )

            # 사용자가 보낸 메시지는 자동응답 여부와 상담원 알림을 확인한다.
            if sender_type == "USER":
                room = service.get_room(room_id)

                # 아직 상담원이 배정되지 않은 방에만 자동응답을 시도한다.
                if room.agent_id is None:
                    auto = service.auto_reply(content)

                    if auto:
                        # 자동 답변도 SYSTEM 발신 메시지로 DB에 저장한다.
                        bot = service.save_message(
                            room_id,
                            None,
                            auto,
                            "SYSTEM",
                        )

                        # 저장한 자동 답변을 채팅방 참여자에게 전송한다.
                        await manager.broadcast(
                            room_id,
                            {
                                "type": "message",
                                "message_id": bot.message_id,
                                "sender_type": "SYSTEM",
                                "content": bot.content,
                                "created_at": bot.created_at,
                            },
                        )

                # 상담원 모니터링 연결에 새 메시지 알림을 보낸다.
                await manager.notify_agents(
                    {
                        "type": "new_message",
                        "room_id": room_id,
                        "content": content[:100],
                    }
                )

    except WebSocketDisconnect:
        # 브라우저가 연결을 끊으면 연결 목록에서 제거한다.
        await manager.disconnect(room_id, websocket)
        logger.info(
            "WebSocket 종료: room_id=%s member_id=%s",
            room_id,
            member.member_id,
        )

    except Exception as exc:  # pragma: no cover
        # 예상하지 못한 오류가 생겨도 연결 목록에서 제거한다.
        logger.error("WebSocket 오류: %s", exc)
        await manager.disconnect(room_id, websocket)

    finally:
        # 정상 종료와 오류 종료 모두 DB 세션을 닫는다.
        db.close()


# -----------------------------------------------------------------------------
# 관리자·상담원 API
# -----------------------------------------------------------------------------
admin_router = APIRouter(
    prefix="/admin/chat",
    tags=["관리자-상담"],
)


@admin_router.get(
    "/rooms",
    response_model=PageResponse[ChatRoomResponse],
    summary="상담 목록",
)
def admin_list_rooms(
    page: int = Query(1, ge=1),  # 조회할 페이지 번호
    size: int = Query(20, ge=1, le=100),  # 페이지당 채팅방 수
    status_filter: Optional[str] = Query(None, alias="status"),
    _admin: Member = Depends(require_admin),  # 관리자 권한 확인
    db: Session = Depends(get_db),
):
    """관리자가 전체 상담 목록을 조회한다."""

    service = ChatService(db)
    rows, total = service.list_rooms_admin(
        page,
        size,
        status_filter,
    )

    return PageResponse[ChatRoomResponse](
        items=[
            service.to_response(room)
            for room in rows
        ],
        meta=PageMeta.build(page, size, total),
    )


@admin_router.post(
    "/rooms/{room_id}/assign",
    response_model=ChatRoomResponse,
    summary="상담원 배정",
)
def assign_agent(
    room_id: int,
    admin: Member = Depends(require_admin),  # 로그인한 관리자·상담원 정보
    db: Session = Depends(get_db),
):
    """현재 로그인한 상담원을 해당 채팅방에 배정한다."""

    service = ChatService(db)
    room = service.assign_agent(room_id, admin)
    return service.to_response(room)


@admin_router.get(
    "/stats",
    response_model=dict,
    summary="상담 통계",
)
def chat_stats(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """열린 상담 수와 평균 만족도를 반환한다."""

    service = ChatService(db)

    return {
        "open_rooms": service.open_room_count(),
        "satisfaction_avg": service.satisfaction_avg(),
    }