"""ORM 모델 패키지.

모든 모델을 이곳에서 불러와 SQLAlchemy가 모델 간 관계를 찾을 수 있게 한다.
"""

# 이 파일에서 직접 사용하지 않아도 모델 등록과 패키지 외부 사용을 위해 가져온다.
# noqa: F401은 해당 import의 미사용 경고를 생략한다.

# AI 분석 결과와 모델 실행 이력
from app.models.ai_model import (  # noqa: F401
    AssociationRule,
    BookSimilarity,
    ChurnPrediction,
    CustomerSegment,
    ModelRun,
    Recommendation,
    SalesDaily,
    SalesForecast,
)

# 도서, 분류, 출판사와 관련 이력
from app.models.book import (  # noqa: F401
    Author,
    Book,
    BookAuthor,
    BookImage,
    Category,
    Publisher,
    RecentView,
    SearchLog,
    StockHistory,
)

from app.models.cart import Cart, CartItem, Wishlist  # noqa: F401

# 모델에서 공통으로 사용하는 상태와 유형
from app.models.enums import (  # noqa: F401
    BookStatus,
    CouponType,
    GenderType,
    MemberRole,
    MemberStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    PointReason,
    QnaStatus,
    SentimentLabel,
    ShipmentStatus,
)

# 회원 정보와 포인트·로그인 이력
from app.models.member import (  # noqa: F401
    LoginHistory,
    Member,
    MemberAddress,
    MemberGrade,
    MemberWithdrawal,
    PointHistory,
)

# 주문, 결제, 환불과 배송
from app.models.order import (  # noqa: F401
    Order,
    OrderItem,
    Payment,
    PaymentLog,
    Refund,
    Shipment,
    ShipmentTracking,
)

from app.models.promotion import Banner, Coupon, MemberCoupon  # noqa: F401
from app.models.review import Review, ReviewImage, ReviewLike, ReviewSentiment  # noqa: F401

# 공지, 문의, FAQ
from app.models.support import (  # noqa: F401
    Faq,
    Notice,
    NoticeAttachment,
    QnaAnswer,
    QnaQuestion,
)

# from app.models import *로 가져올 모델 이름을 지정한다.
__all__ = [
    "Member", "MemberGrade", "MemberAddress", "MemberWithdrawal", "PointHistory", "LoginHistory",
    "Category", "Publisher", "Author", "Book", "BookAuthor", "BookImage",
    "StockHistory", "RecentView", "SearchLog",
    "Cart", "CartItem", "Wishlist",
    "Order", "OrderItem", "Payment", "PaymentLog", "Refund", "Shipment", "ShipmentTracking",
    "Review", "ReviewImage", "ReviewLike", "ReviewSentiment",
    "Notice", "NoticeAttachment", "QnaQuestion", "QnaAnswer", "Faq",
    "Coupon", "MemberCoupon", "Banner",
    "ModelRun", "Recommendation", "BookSimilarity", "SalesDaily", "SalesForecast",
    "CustomerSegment", "ChurnPrediction", "AssociationRule",
]