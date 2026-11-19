"""장바구니와 위시리스트 API 라우터."""
import uuid
from typing import List

from fastapi import APIRouter, Body, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db  # 요청에 사용할 DB 세션 제공
from app.core.security import get_current_member, get_current_member_optional
from app.models.member import Member
from app.schemas.book import BookListItem
from app.schemas.common import MessageResponse, PageMeta, PageResponse
from app.schemas.order import CartItemAddRequest, CartItemUpdateRequest, CartResponse
from app.services.book_service import BookService
from app.services.cart_service import CartService

# 장바구니 API는 /cart로 시작한다.
router = APIRouter(prefix="/cart", tags=["장바구니"])

# 비회원 장바구니를 식별할 쿠키 이름
SESSION_COOKIE = "cart_session"


def _ensure_session(request: Request, response: Response) -> str:
    """비회원 식별용 세션 키를 쿠키에서 가져오거나 새로 만든다."""

    # 브라우저가 기존에 보낸 장바구니 세션 쿠키를 확인한다.
    key = request.cookies.get(SESSION_COOKIE)

    if not key:
        # 쿠키가 없다면 새 UUID를 만들고 브라우저에 저장한다.
        key = uuid.uuid4().hex
        response.set_cookie(
            SESSION_COOKIE,
            key,
            max_age=60 * 60 * 24 * 30,  # 쿠키 유효 기간은 30일
            httponly=True,  # 브라우저 자바스크립트에서 직접 읽지 못하게 한다.
            samesite="lax",  # 다른 사이트에서 시작된 일부 요청에는 쿠키를 보내지 않는다.
        )

    return key


@router.get("", response_model=CartResponse, summary="장바구니 조회")
def get_cart(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),  # 로그인하지 않아도 조회할 수 있다.
):
    """회원 또는 비회원의 장바구니와 예상 결제 금액을 반환한다."""

    service = CartService(db)

    # 회원이면 회원 번호로 장바구니를 찾고,
    # 비회원이면 세션 쿠키로 장바구니를 찾는다.
    session_key = None if member else _ensure_session(request, response)
    cart = service.get_or_create_cart(member, session_key)

    # 상품 목록과 금액 합계를 응답 형식으로 만든다.
    return service.build_response(cart, member)


@router.post("/items", response_model=CartResponse, summary="장바구니 담기")
def add_item(
    payload: CartItemAddRequest,  # 도서 번호와 담을 수량
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """도서를 장바구니에 추가한다. 이미 담긴 도서면 수량을 늘린다."""

    service = CartService(db)
    session_key = None if member else _ensure_session(request, response)
    cart = service.get_or_create_cart(member, session_key)

    service.add_item(cart, payload.book_id, payload.quantity)
    return service.build_response(cart, member)


@router.put(
    "/items/{cart_item_id}",
    response_model=CartResponse,
    summary="장바구니 수량/선택 변경",
)
def update_item(
    cart_item_id: int,  # 수정할 장바구니 항목 번호
    payload: CartItemUpdateRequest,  # 새 수량 또는 선택 상태
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """장바구니 항목의 수량이나 주문 선택 여부를 바꾼다."""

    service = CartService(db)
    session_key = None if member else _ensure_session(request, response)
    cart = service.get_or_create_cart(member, session_key)

    service.update_item(
        cart,
        cart_item_id,
        payload.quantity,
        payload.is_selected,
    )
    return service.build_response(cart, member)


@router.delete(
    "/items/{cart_item_id}",
    response_model=CartResponse,
    summary="장바구니 항목 삭제",
)
def remove_item(
    cart_item_id: int,  # 삭제할 항목 번호
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """장바구니에서 상품 항목 하나를 삭제한다."""

    service = CartService(db)
    session_key = None if member else _ensure_session(request, response)
    cart = service.get_or_create_cart(member, session_key)

    service.remove_item(cart, cart_item_id)
    return service.build_response(cart, member)


@router.post(
    "/items/bulk-delete",
    response_model=CartResponse,
    summary="장바구니 선택 삭제",
)
def bulk_delete(
    request: Request,
    response: Response,
    # 요청 JSON 예: {"cart_item_ids": [1, 2, 3]}
    cart_item_ids: List[int] = Body(..., embed=True),
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """지정한 여러 장바구니 항목을 한 번에 삭제한다."""

    service = CartService(db)
    session_key = None if member else _ensure_session(request, response)
    cart = service.get_or_create_cart(member, session_key)

    service.remove_items(cart, cart_item_ids)
    return service.build_response(cart, member)


@router.post(
    "/select-all",
    response_model=CartResponse,
    summary="전체 선택/해제",
)
def select_all(
    request: Request,
    response: Response,
    # 요청 JSON 예: {"selected": false}
    selected: bool = Body(True, embed=True),
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """장바구니 항목 전체를 선택하거나 선택 해제한다."""

    service = CartService(db)
    session_key = None if member else _ensure_session(request, response)
    cart = service.get_or_create_cart(member, session_key)

    service.select_all(cart, selected)
    return service.build_response(cart, member)


@router.delete("", response_model=MessageResponse, summary="장바구니 비우기")
def clear_cart(
    request: Request,
    response: Response,
    only_selected: bool = False,  # True면 선택된 항목만 삭제
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """장바구니 전체 또는 선택한 항목을 비운다."""

    service = CartService(db)
    session_key = None if member else _ensure_session(request, response)
    cart = service.get_or_create_cart(member, session_key)

    count = service.clear(cart, only_selected)
    return MessageResponse(message=f"{count}건이 삭제되었습니다.")


# -----------------------------------------------------------------------------
# 위시리스트
# -----------------------------------------------------------------------------
# 위시리스트 API는 /wishlist로 시작한다.
wishlist_router = APIRouter(prefix="/wishlist", tags=["위시리스트"])


@wishlist_router.get(
    "",
    response_model=PageResponse[BookListItem],
    summary="위시리스트 조회",
)
def list_wishlist(
    page: int = 1,  # 조회할 페이지 번호
    size: int = 20,  # 페이지당 항목 수
    member: Member = Depends(get_current_member),  # 위시리스트는 로그인 회원만 조회
    db: Session = Depends(get_db),
):
    """로그인 회원의 위시리스트를 페이지 단위로 반환한다."""

    rows, total = CartService(db).list_wishlist(member, page, size)
    service = BookService(db)

    # 위시리스트 항목에서 도서 정보를 꺼내 목록 응답으로 바꾼다.
    items = [
        service.to_list_item(row.book)
        for row in rows
        if row.book
    ]

    return PageResponse[BookListItem](
        items=items,
        meta=PageMeta.build(page, size, total),
    )


@wishlist_router.post(
    "/{book_id}",
    response_model=dict,
    summary="위시리스트 토글",
)
def toggle_wishlist(
    book_id: int,  # 위시리스트에 추가하거나 제거할 도서 번호
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """도서가 없으면 추가하고, 이미 있으면 제거한다."""

    added = CartService(db).toggle_wishlist(member, book_id)

    # 추가한 경우 wished=True, 제거한 경우 wished=False가 된다.
    return {"book_id": book_id, "wished": added}