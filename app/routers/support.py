"""공지사항, Q&A, FAQ API 라우터."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    get_current_member,
    get_current_member_optional,
    require_admin,
)
from app.models.member import Member
from app.schemas.common import MessageResponse, PageMeta, PageResponse
from app.schemas.support import (
    FaqCreateRequest,
    FaqResponse,
    NoticeCreateRequest,
    NoticeResponse,
    NoticeUpdateRequest,
    QnaAnswerRequest,
    QnaCreateRequest,
    QnaResponse,
)
from app.services.support_service import FaqService, NoticeService, QnaService


# -----------------------------------------------------------------------------
# 공지사항 API: 주소가 /notices로 시작한다.
# -----------------------------------------------------------------------------
notice_router = APIRouter(prefix="/notices", tags=["공지사항"])


@notice_router.get(
    "",
    response_model=PageResponse[NoticeResponse],
    summary="공지 목록",
)
def list_notices(
    page: int = Query(1, ge=1),  # 조회할 페이지 번호
    size: int = Query(10, ge=1, le=50),  # 페이지당 공지 수
    category: Optional[str] = None,  # 공지 카테고리 필터
    keyword: Optional[str] = None,  # 제목·내용 검색어
    db: Session = Depends(get_db),
):
    """공지 목록을 조회한다. 고정 공지가 먼저 표시된다."""

    rows, total = NoticeService(db).list_notices(
        page,
        size,
        category,
        keyword,
    )

    # 목록에서는 본문을 제외하고 공지 요약 정보만 반환한다.
    items = [
        NoticeResponse(
            notice_id=notice.notice_id,
            category=notice.category,
            title=notice.title,
            content=None,
            is_pinned=notice.is_pinned,
            view_count=notice.view_count,
            published_at=notice.published_at,
        )
        for notice in rows
    ]

    return PageResponse[NoticeResponse](
        items=items,
        meta=PageMeta.build(page, size, total),
    )


@notice_router.get(
    "/{notice_id}",
    response_model=NoticeResponse,
    summary="공지 상세",
)
def get_notice(
    notice_id: int,
    db: Session = Depends(get_db),
):
    """공지 본문을 조회하고 조회수를 증가시킨다."""

    notice = NoticeService(db).get_notice(notice_id)
    return NoticeResponse.model_validate(notice)


@notice_router.get(
    "/{notice_id}/adjacent",
    response_model=dict,
    summary="이전/다음 공지",
)
def adjacent_notice(
    notice_id: int,
    db: Session = Depends(get_db),
):
    """현재 공지의 이전 글과 다음 글 정보를 반환한다."""

    return NoticeService(db).get_adjacent(notice_id)


# -----------------------------------------------------------------------------
# 관리자 공지사항 API
# -----------------------------------------------------------------------------
admin_notice_router = APIRouter(
    prefix="/admin/notices",
    tags=["관리자-공지사항"],
)


@admin_notice_router.get(
    "",
    response_model=PageResponse[NoticeResponse],
    summary="공지 목록(관리자)",
)
def admin_list_notices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _admin: Member = Depends(require_admin),  # 관리자 권한 확인
    db: Session = Depends(get_db),
):
    """게시되지 않은 공지도 포함해 관리자가 공지 목록을 조회한다."""

    rows, total = NoticeService(db).list_notices(
        page,
        size,
        include_unpublished=True,
    )

    return PageResponse[NoticeResponse](
        items=[
            NoticeResponse.model_validate(notice)
            for notice in rows
        ],
        meta=PageMeta.build(page, size, total),
    )


@admin_notice_router.post(
    "",
    response_model=NoticeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="공지 등록",
)
def create_notice(
    payload: NoticeCreateRequest,
    admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 새 공지사항을 등록한다."""

    notice = NoticeService(db).create_notice(
        payload,
        admin.member_id,
    )
    return NoticeResponse.model_validate(notice)


@admin_notice_router.put(
    "/{notice_id}",
    response_model=NoticeResponse,
    summary="공지 수정",
)
def update_notice(
    notice_id: int,
    payload: NoticeUpdateRequest,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 기존 공지사항을 수정한다."""

    notice = NoticeService(db).update_notice(notice_id, payload)
    return NoticeResponse.model_validate(notice)


@admin_notice_router.delete(
    "/{notice_id}",
    response_model=MessageResponse,
    summary="공지 삭제",
)
def delete_notice(
    notice_id: int,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 공지사항을 삭제한다."""

    NoticeService(db).delete_notice(notice_id)
    return MessageResponse(message="공지사항이 삭제되었습니다.")


# -----------------------------------------------------------------------------
# Q&A API: 회원이 문의를 올리고 답변을 확인한다.
# -----------------------------------------------------------------------------
qna_router = APIRouter(prefix="/qna", tags=["묻고답하기"])


@qna_router.get(
    "",
    response_model=PageResponse[QnaResponse],
    summary="Q&A 목록",
)
def list_qna(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    only_mine: bool = False,  # True면 로그인한 회원의 문의만 조회
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),  # 비회원 조회도 허용
):
    """Q&A 목록을 조회한다. 비밀글 내용은 권한에 따라 가려진다."""

    service = QnaService(db)
    rows, total = service.list_questions(
        page,
        size,
        member,
        only_mine,
        status_filter,
        category,
        keyword,
    )

    return PageResponse[QnaResponse](
        items=[
            service.to_response(question, member)
            for question in rows
        ],
        meta=PageMeta.build(page, size, total),
    )


@qna_router.post(
    "",
    response_model=QnaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="문의 등록",
)
def create_qna(
    payload: QnaCreateRequest,
    member: Member = Depends(get_current_member),  # 로그인 회원만 문의 가능
    db: Session = Depends(get_db),
):
    """로그인 회원이 새 문의를 등록한다."""

    service = QnaService(db)
    question = service.create_question(member, payload)
    return service.to_response(question, member)


@qna_router.get(
    "/{question_id}",
    response_model=QnaResponse,
    summary="문의 상세",
)
def get_qna(
    question_id: int,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """문의 상세와 답변을 조회한다."""

    service = QnaService(db)
    question = service.get_question(question_id)
    return service.to_response(question, member)


@qna_router.delete(
    "/{question_id}",
    response_model=MessageResponse,
    summary="문의 삭제",
)
def delete_qna(
    question_id: int,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """회원 본인의 문의를 삭제한다."""

    QnaService(db).delete_question(question_id, member)
    return MessageResponse(message="문의가 삭제되었습니다.")


# -----------------------------------------------------------------------------
# 관리자 Q&A API
# -----------------------------------------------------------------------------
admin_qna_router = APIRouter(
    prefix="/admin/qna",
    tags=["관리자-묻고답하기"],
)


@admin_qna_router.post(
    "/{question_id}/answer",
    response_model=QnaResponse,
    summary="답변 등록",
)
def answer_qna(
    question_id: int,
    payload: QnaAnswerRequest,
    admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 문의에 답변하고 답변이 포함된 문의를 반환한다."""

    service = QnaService(db)
    service.answer(question_id, admin, payload.content)

    # 상세 조회 시 조회수가 오르지 않도록 increase_view=False로 호출한다.
    question = service.get_question(
        question_id,
        increase_view=False,
    )
    return service.to_response(question, admin)


@admin_qna_router.post(
    "/{question_id}/close",
    response_model=MessageResponse,
    summary="문의 종료",
)
def close_qna(
    question_id: int,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 문의 상태를 종료로 변경한다."""

    QnaService(db).close_question(question_id)
    return MessageResponse(message="문의가 종료되었습니다.")


@admin_qna_router.get(
    "/waiting-count",
    response_model=dict,
    summary="미답변 건수",
)
def waiting_count(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자에게 답변을 기다리는 문의 건수를 반환한다."""

    return {"waiting": QnaService(db).waiting_count()}


# -----------------------------------------------------------------------------
# FAQ API
# -----------------------------------------------------------------------------
faq_router = APIRouter(prefix="/faqs", tags=["FAQ"])


@faq_router.get(
    "",
    response_model=List[FaqResponse],
    summary="FAQ 목록",
)
def list_faqs(
    category: Optional[str] = None,  # 지정하면 해당 카테고리만 조회
    db: Session = Depends(get_db),
):
    """활성화된 FAQ 목록을 조회한다."""

    rows = FaqService(db).list_faqs(category)
    return [
        FaqResponse.model_validate(faq)
        for faq in rows
    ]


@faq_router.get(
    "/categories",
    response_model=List[str],
    summary="FAQ 카테고리",
)
def faq_categories(
    db: Session = Depends(get_db),
):
    """사용 중인 FAQ 카테고리 목록을 반환한다."""

    return FaqService(db).categories()


@faq_router.post(
    "",
    response_model=FaqResponse,
    summary="FAQ 등록(관리자)",
)
def create_faq(
    payload: FaqCreateRequest,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 FAQ를 등록한다."""

    faq = FaqService(db).create_faq(payload)
    return FaqResponse.model_validate(faq)


@faq_router.delete(
    "/{faq_id}",
    response_model=MessageResponse,
    summary="FAQ 삭제(관리자)",
)
def delete_faq(
    faq_id: int,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 FAQ를 삭제한다."""

    FaqService(db).delete_faq(faq_id)
    return MessageResponse(message="FAQ가 삭제되었습니다.")