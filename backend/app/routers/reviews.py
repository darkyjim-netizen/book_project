"""리뷰 API 라우터."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_member, require_admin
from app.models.member import Member
from app.schemas.common import MessageResponse
from app.schemas.review import (
    ReviewCreateRequest,
    ReviewReplyRequest,
    ReviewResponse,
    ReviewUpdateRequest,
    SentimentAnalyzeRequest,
)
from app.services.review_service import ReviewService


# 이 라우터의 주소는 /reviews로 시작한다.
router = APIRouter(prefix="/reviews", tags=["리뷰"])


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="리뷰 작성",
)
def create_review(
    payload: ReviewCreateRequest,  # 작성할 도서, 별점, 제목, 내용, 이미지 정보
    member: Member = Depends(get_current_member),  # 로그인한 회원만 작성 가능
    db: Session = Depends(get_db),  # 요청 중 사용할 DB 세션
):
    """리뷰를 작성하고 감성분석과 포인트 적립을 수행한다."""

    service = ReviewService(db)

    # 서비스에서 리뷰 저장, 감성분석, 포인트 적립을 처리한다.
    review = service.create_review(member, payload)

    # 로그인 회원이 이 리뷰에 '도움돼요'를 눌렀는지도 포함해 응답으로 바꾼다.
    return service.to_response(review, member.member_id)


@router.put(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="리뷰 수정",
)
def update_review(
    review_id: int,  # 수정할 리뷰 번호
    payload: ReviewUpdateRequest,  # 변경할 리뷰 내용
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """리뷰를 수정한다. 리뷰 본문이 바뀌면 감성분석도 다시 한다."""

    service = ReviewService(db)

    # 서비스가 작성자 본인 또는 관리자인지 확인하고 리뷰를 수정한다.
    review = service.update_review(review_id, member, payload)

    return service.to_response(review, member.member_id)


@router.delete(
    "/{review_id}",
    response_model=MessageResponse,
    summary="리뷰 삭제",
)
def delete_review(
    review_id: int,  # 삭제할 리뷰 번호
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """리뷰를 삭제한다."""

    # 작성자 본인 또는 관리자만 삭제할 수 있도록 서비스에서 확인한다.
    ReviewService(db).delete_review(review_id, member)

    # 삭제 결과를 간단한 메시지로 반환한다.
    return MessageResponse(message="리뷰가 삭제되었습니다.")


@router.post(
    "/{review_id}/like",
    response_model=dict,
    summary="리뷰 도움됨 토글",
)
def toggle_like(
    review_id: int,  # 도움돼요를 누르거나 취소할 리뷰 번호
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """리뷰의 도움돼요 상태를 등록하거나 취소한다."""

    # 이미 눌렀다면 취소하고, 누르지 않았다면 새로 등록한다.
    liked = ReviewService(db).toggle_like(review_id, member)

    # liked가 True면 등록, False면 취소된 것이다.
    return {
        "review_id": review_id,
        "liked": liked,
    }


@router.post(
    "/analyze-sentiment",
    response_model=dict,
    summary="텍스트 감성분석",
)
def analyze_sentiment(
    payload: SentimentAnalyzeRequest,  # 분석할 텍스트
):
    """리뷰를 저장하지 않고 입력된 텍스트의 감성분석 결과만 반환한다."""

    # 이 API를 사용할 때 감성분석 모듈을 불러온다.
    from app.ai.sentiment import get_analyzer

    # 분석 결과에는 감성 분류와 점수, 키워드 등이 포함된다.
    return get_analyzer().analyze(payload.text)


# -----------------------------------------------------------------------------
# 관리자 리뷰 API
# -----------------------------------------------------------------------------

# 관리자용 리뷰 API는 /admin/reviews로 시작한다.
admin_router = APIRouter(
    prefix="/admin/reviews",
    tags=["관리자-리뷰"],
)


@admin_router.post(
    "/{review_id}/reply",
    response_model=ReviewResponse,
    summary="리뷰 답글 등록",
)
def reply_review(
    review_id: int,  # 답글을 달 리뷰 번호
    payload: ReviewReplyRequest,  # 답글 내용
    admin: Member = Depends(require_admin),  # 관리자 권한 확인
    db: Session = Depends(get_db),
):
    """관리자가 리뷰에 답글을 등록한다."""

    service = ReviewService(db)

    # 답글 내용과 작성 시각을 리뷰에 저장한다.
    review = service.reply(review_id, payload.reply_content)

    # 관리자 본인이 이 리뷰에 도움돼요를 눌렀는지도 포함해 응답한다.
    return service.to_response(review, admin.member_id)


@admin_router.post(
    "/{review_id}/blind",
    response_model=ReviewResponse,
    summary="리뷰 블라인드",
)
def blind_review(
    review_id: int,  # 블라인드 처리하거나 해제할 리뷰 번호
    blinded: bool = True,  # True면 블라인드, False면 블라인드 해제
    admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 부적절한 리뷰를 숨기거나 다시 공개한다."""

    service = ReviewService(db)

    # blinded 값에 따라 리뷰의 공개 여부를 바꾼다.
    review = service.set_blind(review_id, blinded)

    return service.to_response(review, admin.member_id)


@admin_router.post(
    "/mark-best",
    response_model=MessageResponse,
    summary="베스트 리뷰 선정",
)
def mark_best(
    top_n: int = 20,  # 베스트 리뷰로 선정할 리뷰 수
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """도움돼요 수가 많은 리뷰를 베스트 리뷰로 선정한다."""

    # 기존 베스트 표시를 갱신하고 상위 리뷰를 선정한다.
    count = ReviewService(db).mark_best_reviews(top_n)

    return MessageResponse(
        message=f"베스트 리뷰 {count}건이 선정되었습니다."
    )