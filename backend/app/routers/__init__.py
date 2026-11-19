"""라우터 패키지.

register_routers(app)을 호출해 모든 라우터를 애플리케이션에 등록한다.
"""

from fastapi import APIRouter, FastAPI

from app.core.config import settings
from app.routers import admin, admin_extras, ai_router, auth, books, cart, chat, members, orders, pages, postal, reviews, support


def register_routers(app: FastAPI) -> None:
    """API 및 페이지 라우터를 등록한다."""
    # 사용자 API와 관리자 API에 공통 경로 접두사(기본값 /api/v1)를 붙인다.
    api = APIRouter(prefix=settings.API_PREFIX)

    # 사용자 API: 인증, 회원, 도서, 장바구니, 위시리스트, 주문, 리뷰
    api.include_router(auth.router)
    api.include_router(members.router)
    # postal 라우터를 연결하면 기본 주소는 /api/v1/postal/search가 된다.
    api.include_router(postal.router)
    api.include_router(books.router)
    api.include_router(cart.router)
    api.include_router(cart.wishlist_router)
    api.include_router(orders.router)
    api.include_router(reviews.router)

    # 사용자 API: 공지사항, 문의, FAQ, 채팅, AI 기능
    api.include_router(support.notice_router)
    api.include_router(support.qna_router)
    api.include_router(support.faq_router)
    api.include_router(chat.router)
    api.include_router(ai_router.router)

    # 관리자 API: 관리 기능, 배송, 리뷰, 공지사항, 문의, 채팅
    api.include_router(admin.router)
    api.include_router(admin_extras.router)
    api.include_router(orders.admin_shipment_router)
    api.include_router(reviews.admin_router)
    api.include_router(support.admin_notice_router)
    api.include_router(support.admin_qna_router)
    api.include_router(chat.admin_router)

    # 모아 둔 API 라우터를 FastAPI 앱에 한 번에 연결한다.
    app.include_router(api)

    # 서버에서 HTML을 렌더링하는 페이지는 앱에 직접 등록한다.
    app.include_router(pages.router)
