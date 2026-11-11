from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.auth_dependencies import admin_member
from app.database import get_db
from app.models.order_model import Order, OrderStatus
from app.models.user_model import Member


router = APIRouter(prefix="/api/admin/dashboard", tags=["관리자 대시보드"],
                   dependencies=[Depends(admin_member)])
# 일별 주문 수를 한국 표준시 기준으로 계산합니다.
KST = timezone(timedelta(hours=9))
# 결제가 끝난 주문만 매출과 판매 수량에 포함합니다. 결제 대기·취소·환불 주문은 제외합니다.
SOLD_STATUSES = [status.value for status in (
    OrderStatus.PAID, OrderStatus.PREPARING, OrderStatus.SHIPPED, OrderStatus.DELIVERED)]


# 총매출, 회원 수, 주문 수와 최근 일별 주문 수의 응답 형식입니다.
class AdminStatsResponse(BaseModel):
    total_sales: int
    member_count: int
    order_count: int
    daily_orders: dict[str, int]


# 지역·연령대별 주문 수와 카테고리별 판매 수량의 응답 형식입니다.
class AdminAnalyticsResponse(BaseModel):
    orders_by_region: dict[str, int]
    orders_by_age_group: dict[str, int]
    units_by_category: dict[int, int]


# 전체 매출과 회원·주문 수를 조회하고 한국 시간 기준 최근 7일 주문 수를 집계합니다.
@router.get("/stats", response_model=AdminStatsResponse)
def stats(db: Session = Depends(get_db)):
    today = datetime.now(KST).date()
    first_day = today - timedelta(days=6)
    # 한국 시간 기준 첫날 자정을 데이터베이스 조회용 UTC 시각으로 변환합니다.
    since = datetime.combine(first_day, datetime.min.time(), KST).astimezone(timezone.utc)
    recent = db.scalars(select(Order.created_at).where(Order.created_at >= since))
    # 주문이 없는 날짜도 표시할 수 있도록 최근 7일을 0건으로 초기화합니다.
    daily = {(first_day + timedelta(days=i)).isoformat(): 0 for i in range(7)}
    for created_at in recent:
        # 시간대가 없는 저장 시각은 UTC로 간주한 뒤 한국 날짜로 변환합니다.
        created_at = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
        day = created_at.astimezone(KST).date().isoformat()
        if day in daily:
            daily[day] += 1

    return AdminStatsResponse(
        total_sales=db.scalar(select(func.coalesce(func.sum(Order.total), 0))
                              .where(Order.status.in_(SOLD_STATUSES))) or 0,
        member_count=db.scalar(select(func.count()).select_from(Member)) or 0,
        order_count=db.scalar(select(func.count()).select_from(Order)) or 0,
        daily_orders=daily,
    )


# 주문 데이터를 순회하며 지역·연령대별 주문 수와 카테고리별 판매 수량을 집계합니다.
@router.get("/analytics", response_model=AdminAnalyticsResponse)
def analytics(db: Session = Depends(get_db)):
    regions, ages, categories = Counter(), Counter(), Counter()
    # 주문을 100건 단위로 읽어 통계 집계 시 메모리 사용을 줄입니다.
    rows = db.execute(select(Order.region, Order.age_group, Order.items, Order.status)
                      .execution_options(yield_per=100))
    for region, age, items, status in rows:
        # 지역이나 연령대가 입력되지 않은 주문은 미응답으로 묶습니다.
        regions[region or "미응답"] += 1
        ages[age or "미응답"] += 1
        # 판매 수량은 결제가 끝난 주문만 셉니다.
        if status not in SOLD_STATUSES:
            continue
        for item in items:
            categories[item["category_id"]] += item["quantity"]
    return AdminAnalyticsResponse(orders_by_region=dict(regions), orders_by_age_group=dict(ages),
                                  units_by_category=dict(categories))
