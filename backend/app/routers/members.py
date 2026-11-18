"""회원 마이페이지 API 경로."""
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db  # 요청 중 사용할 DB 세션
from app.core.security import get_current_member  # 로그인한 회원 확인
from app.models.member import Member
from app.schemas.common import MessageResponse, PageMeta, PageResponse
from app.schemas.member import (
    AddressCreateRequest,
    AddressResponse,
    CouponResponse,
    MemberResponse,
    MemberStatsResponse,
    MemberUpdateRequest,
    PointHistoryResponse,
)
from app.schemas.review import ReviewResponse
from app.services.member_service import MemberService
from app.services.review_service import ReviewService

# 이 라우터에 등록한 모든 주소 앞에는 /members가 붙는다.
router = APIRouter(prefix="/members", tags=["회원"])


@router.get("/me", response_model=MemberResponse, summary="내 정보")
def get_me(member: Member = Depends(get_current_member)):
    """로그인한 회원 정보를 반환한다."""
    # get_current_member가 토큰을 확인하고 로그인한 회원을 전달한다.
    return MemberResponse.model_validate(member)


@router.put("/me", response_model=MemberResponse, summary="내 정보 수정")
def update_me(
    payload: MemberUpdateRequest,  # 수정할 회원 정보
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """로그인한 회원의 정보를 수정한다."""
    updated = MemberService(db).update_profile(member, payload)
    return MemberResponse.model_validate(updated)


@router.get(
    "/me/stats",
    response_model=MemberStatsResponse,
    summary="마이페이지 요약",
)
def my_stats(
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """주문·포인트·쿠폰·리뷰 등의 요약 정보를 반환한다."""
    return MemberService(db).my_stats(member)


# -----------------------------------------------------------------------------
# 배송지
# -----------------------------------------------------------------------------
@router.get(
    "/me/addresses",
    response_model=List[AddressResponse],
    summary="배송지 목록",
)
def list_addresses(
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """로그인 회원의 배송지 목록을 반환한다."""
    rows = MemberService(db).list_addresses(member)

    # 각 ORM 배송지 객체를 API 응답 스키마로 바꾼다.
    return [AddressResponse.model_validate(row) for row in rows]


@router.post(
    "/me/addresses",
    response_model=AddressResponse,
    summary="배송지 등록",
)
def create_address(
    payload: AddressCreateRequest,  # 새 배송지 정보
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """배송지를 등록한다. 회원당 최대 10개까지 등록할 수 있다."""
    address = MemberService(db).create_address(member, payload)
    return AddressResponse.model_validate(address)


@router.put(
    "/me/addresses/{address_id}",
    response_model=AddressResponse,
    summary="배송지 수정",
)
def update_address(
    address_id: int,  # 수정할 배송지 번호
    payload: AddressCreateRequest,  # 수정할 배송지 정보
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """로그인 회원 본인의 배송지를 수정한다."""
    address = MemberService(db).update_address(address_id, member, payload)
    return AddressResponse.model_validate(address)


@router.delete(
    "/me/addresses/{address_id}",
    response_model=MessageResponse,
    summary="배송지 삭제",
)
def delete_address(
    address_id: int,  # 삭제할 배송지 번호
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """로그인 회원 본인의 배송지를 삭제한다."""
    MemberService(db).delete_address(address_id, member)
    return MessageResponse(message="배송지가 삭제되었습니다.")


# -----------------------------------------------------------------------------
# 포인트
# -----------------------------------------------------------------------------
@router.get(
    "/me/points",
    response_model=PageResponse[PointHistoryResponse],
    summary="포인트 내역",
)
def list_points(
    page: int = Query(1, ge=1),  # 조회할 페이지 번호. 1부터 시작
    size: int = Query(20, ge=1, le=100),  # 페이지당 항목 수. 1~100 허용
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """포인트 적립·사용 내역을 페이지 단위로 조회한다."""
    rows, total = MemberService(db).list_points(member, page, size)

    # 현재 페이지의 내역과 전체 페이지 정보를 묶어 반환한다.
    return PageResponse[PointHistoryResponse](
        items=[PointHistoryResponse.model_validate(row) for row in rows],
        meta=PageMeta.build(page, size, total),
    )


# -----------------------------------------------------------------------------
# 쿠폰
# -----------------------------------------------------------------------------
@router.get(
    "/me/coupons",
    response_model=List[CouponResponse],
    summary="보유 쿠폰",
)
def list_coupons(
    include_used: bool = False,  # True면 사용했거나 만료된 쿠폰도 조회
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """회원이 보유한 쿠폰 목록을 반환한다."""
    rows = MemberService(db).list_coupons(member, include_used)

    # 회원별 쿠폰 발급 기록과 연결된 쿠폰 정보를 응답 형식으로 만든다.
    return [
        CouponResponse(
            member_coupon_id=row.member_coupon_id,
            coupon_id=row.coupon_id,
            name=row.coupon.name,
            coupon_type=row.coupon.coupon_type.value,
            discount_value=float(row.coupon.discount_value),
            max_discount=(
                float(row.coupon.max_discount)
                if row.coupon.max_discount
                else None
            ),
            min_order_amount=float(row.coupon.min_order_amount),
            is_used=row.is_used,
            expires_at=row.expires_at,
        )
        for row in rows
    ]


@router.post(
    "/me/coupons",
    response_model=MessageResponse,
    summary="쿠폰 코드 등록",
)
def issue_coupon(
    code: str = Body(..., embed=True),  # JSON 본문에서 {"code": "..."} 형식으로 받는다.
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """쿠폰 코드를 확인해 로그인 회원에게 발급한다."""
    MemberService(db).issue_coupon(member, code)
    return MessageResponse(message="쿠폰이 발급되었습니다.")


@router.get(
    "/me/coupons/available",
    response_model=List[dict],
    summary="적용 가능 쿠폰",
)
def available_coupons(
    amount: float = Query(
        ...,
        ge=0,
        description="주문 금액",
    ),  # 쿠폰 적용 가능 여부를 확인할 주문 금액
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """주문 금액에 적용할 수 있는 쿠폰과 예상 할인액을 반환한다."""
    return MemberService(db).available_coupons_for_amount(member, amount)


# -----------------------------------------------------------------------------
# 내 리뷰
# -----------------------------------------------------------------------------
@router.get(
    "/me/reviews",
    response_model=PageResponse[ReviewResponse],
    summary="내가 쓴 리뷰",
)
def my_reviews(
    page: int = Query(1, ge=1),  # 조회할 페이지 번호
    size: int = Query(10, ge=1, le=50),  # 페이지당 리뷰 수. 1~50 허용
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """로그인 회원이 작성한 리뷰를 페이지 단위로 조회한다."""
    items, total = ReviewService(db).list_by_member(member, page, size)

    return PageResponse[ReviewResponse](
        items=items,
        meta=PageMeta.build(page, size, total),
    )


@router.get(
    "/me/reviewable",
    response_model=List[dict],
    summary="리뷰 작성 가능 상품",
)
def reviewable(
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """배송 완료됐지만 아직 리뷰를 작성하지 않은 주문 상품을 반환한다."""
    rows = ReviewService(db).reviewable_items(member)

    # ORM 객체에서 리뷰 작성 화면에 필요한 정보만 골라 응답한다.
    return [
        {
            "order_item_id": item.order_item_id,
            "book_id": item.book_id,
            "book_title": item.book_title,
            "cover_image": item.book.cover_image if item.book else None,
            "created_at": item.created_at,
        }
        for item in rows
    ]


# -----------------------------------------------------------------------------
# AI 추천
# -----------------------------------------------------------------------------
@router.get(
    "/me/recommendations",
    response_model=List[dict],
    summary="내 맞춤 추천 도서",
)
def my_recommendations(
    limit: int = Query(10, ge=1, le=30),  # 가져올 추천 도서 수
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """협업 필터링으로 계산한 회원 맞춤 도서를 반환한다."""

    # 이 API에서만 필요한 기능이므로 요청을 처리할 때 모듈을 불러온다.
    from app.ai.recommender import get_recommender
    from app.ai.stored_recs import stored_recommendations
    from app.services.book_service import BookService

    recommender = get_recommender(db)

    # 추천 결과는 (도서 번호, 추천 점수, 추천 이유) 형태의 묶음으로 받는다.
    triples, _ = stored_recommendations(db, member.member_id, limit)
    if not triples:
        triples = recommender.recommend_for_member(member.member_id, limit)

    # 추천된 도서의 상세 정보를 한 번에 조회해 도서 번호로 찾기 쉽게 만든다.
    book_service = BookService(db)
    books = {
        book.book_id: book
        for book in book_service.list_by_ids([item[0] for item in triples])
    }

    result = []
    for book_id, score, reason in triples:
        book = books.get(book_id)

        # 도서 정보가 조회되지 않은 추천 항목은 응답에서 건너뛴다.
        if book is None:
            continue

        # 도서 정보에 추천 점수와 이유를 더해 응답 항목을 만든다.
        payload = book.model_dump()
        payload.update({"score": score, "reason": reason})
        result.append(payload)

    return result