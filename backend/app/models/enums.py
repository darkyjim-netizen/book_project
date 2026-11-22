"""PostgreSQL ENUM 값과 맞춰 사용하는 파이썬 Enum 정의."""
import enum


# str을 함께 상속해 Enum 값이 문자열처럼도 사용될 수 있게 한다.
# enum.Enum은 관련된 값을 하나의 이름 묶음으로 관리한다.
class MemberRole(str, enum.Enum):
    """회원의 역할."""
    USER = "USER"        # 일반 회원
    SELLER = "SELLER"    # 판매자
    STAFF = "STAFF"      # 상담원 또는 직원
    ADMIN = "ADMIN"      # 관리자


class MemberStatus(str, enum.Enum):
    """회원 계정의 상태."""
    ACTIVE = "ACTIVE"        # 정상 이용 중
    DORMANT = "DORMANT"      # 휴면 상태
    SUSPENDED = "SUSPENDED"  # 이용 정지
    WITHDRAWN = "WITHDRAWN"  # 탈퇴


class GenderType(str, enum.Enum):
    """회원의 성별 구분."""
    M = "M"  # 남성
    F = "F"  # 여성
    N = "N"  # 미입력 또는 해당 없음


class BookStatus(str, enum.Enum):
    """도서 상품의 판매 상태."""
    SALE = "SALE"          # 판매 중
    SOLDOUT = "SOLDOUT"    # 품절
    STOP = "STOP"          # 판매 중지
    PREORDER = "PREORDER"  # 예약 판매
    DELETED = "DELETED"    # 삭제 처리


class OrderStatus(str, enum.Enum):
    """주문의 진행 상태."""
    PENDING = "PENDING"            # 결제 대기
    PAID = "PAID"                  # 결제 완료
    PREPARING = "PREPARING"        # 상품 준비 중
    SHIPPING = "SHIPPING"          # 배송 중
    DELIVERED = "DELIVERED"        # 배송 완료
    CONFIRMED = "CONFIRMED"        # 구매 확정
    CANCELLED = "CANCELLED"        # 주문 취소
    RETURN_REQ = "RETURN_REQ"      # 반품 신청
    RETURNED = "RETURNED"          # 반품 완료
    EXCHANGE_REQ = "EXCHANGE_REQ"  # 교환 신청
    EXCHANGED = "EXCHANGED"        # 교환 완료


class PaymentMethod(str, enum.Enum):
    """결제에 사용한 수단."""
    CARD = "CARD"          # 신용카드 또는 체크카드
    VBANK = "VBANK"        # 가상계좌
    TRANSFER = "TRANSFER"  # 계좌이체
    PHONE = "PHONE"        # 휴대폰 결제
    KAKAOPAY = "KAKAOPAY"  # 카카오페이
    NAVERPAY = "NAVERPAY"  # 네이버페이
    TOSSPAY = "TOSSPAY"    # 토스페이
    POINT = "POINT"        # 포인트 결제


class PaymentStatus(str, enum.Enum):
    """결제 처리 결과."""
    READY = "READY"                        # 결제 요청 또는 승인 대기
    PAID = "PAID"                          # 결제 완료
    CANCELLED = "CANCELLED"                # 결제 취소
    PARTIAL_CANCELLED = "PARTIAL_CANCELLED"  # 일부 금액만 취소
    FAILED = "FAILED"                      # 결제 실패


class ShipmentStatus(str, enum.Enum):
    """배송 진행 상태."""
    READY = "READY"                    # 배송 준비
    PICKED = "PICKED"                  # 택배사에서 상품 수거
    IN_TRANSIT = "IN_TRANSIT"          # 배송 중
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"  # 배송지로 배달 출발
    DELIVERED = "DELIVERED"            # 배송 완료
    FAILED = "FAILED"                  # 배송 실패
    RETURNING = "RETURNING"            # 판매자에게 반송 중


class SentimentLabel(str, enum.Enum):
    """리뷰 감성 분석 결과."""
    POSITIVE = "POSITIVE"  # 긍정
    NEUTRAL = "NEUTRAL"    # 중립
    NEGATIVE = "NEGATIVE"  # 부정


class QnaStatus(str, enum.Enum):
    """게시판 문의의 답변 상태."""
    WAITING = "WAITING"    # 답변 대기
    ANSWERED = "ANSWERED"  # 답변 완료
    CLOSED = "CLOSED"      # 문의 종료


class CouponType(str, enum.Enum):
    """쿠폰의 할인 방식."""
    AMOUNT = "AMOUNT"      # 정해진 금액 할인
    PERCENT = "PERCENT"    # 일정 비율 할인
    FREESHIP = "FREESHIP"  # 배송비 무료


class PointReason(str, enum.Enum):
    """포인트가 적립되거나 사용된 이유."""
    ORDER_SAVE = "ORDER_SAVE"          # 주문으로 포인트 적립
    ORDER_USE = "ORDER_USE"            # 주문에서 포인트 사용
    REVIEW = "REVIEW"                  # 리뷰 작성 적립
    EVENT = "EVENT"                    # 이벤트 적립
    ADMIN_ADJUST = "ADMIN_ADJUST"      # 관리자에 의한 조정
    EXPIRE = "EXPIRE"                  # 유효기간 만료
    CANCEL_RESTORE = "CANCEL_RESTORE"  # 주문 취소 후 포인트 복원


# 주문 취소를 허용할 상태들.
# 예: if order.status in CANCELABLE_STATUSES: ...
CANCELABLE_STATUSES = (
    OrderStatus.PENDING,
    OrderStatus.PAID,
    OrderStatus.PREPARING,
)


# 매출 합계에 포함할 주문 상태들.
# 결제 후 취소되지 않고 처리 중이거나 배송·구매가 완료된 주문이다.
SALES_STATUSES = (
    OrderStatus.PAID,
    OrderStatus.PREPARING,
    OrderStatus.SHIPPING,
    OrderStatus.DELIVERED,
    OrderStatus.CONFIRMED,
)