from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.auth_dependencies import admin_member
from app.database import get_db
from app.models.order_model import Order
from app.models.user_model import Member


router = APIRouter(prefix="/api/admin/dashboard", tags=["관리자 대시보드"],
                   dependencies=[Depends(admin_member)])
KST = timezone(timedelta(hours=9))


class AdminStatsResponse(BaseModel):
    total_sales: int
    member_count: int
    order_count: int
    daily_orders: dict[str, int]


class AdminAnalyticsResponse(BaseModel):
    orders_by_region: dict[str, int]
    orders_by_age_group: dict[str, int]
    units_by_category: dict[int, int]


@router.get("/stats", response_model=AdminStatsResponse)
def stats(db: Session = Depends(get_db)):
    today = datetime.now(KST).date()
    first_day = today - timedelta(days=6)
    since = datetime.combine(first_day, datetime.min.time(), KST).astimezone(timezone.utc)
    recent = db.scalars(select(Order.created_at).where(Order.created_at >= since))
    daily = {(first_day + timedelta(days=i)).isoformat(): 0 for i in range(7)}
    for created_at in recent:
        created_at = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
        day = created_at.astimezone(KST).date().isoformat()
        if day in daily:
            daily[day] += 1

    return AdminStatsResponse(
        total_sales=db.scalar(select(func.coalesce(func.sum(Order.total), 0))) or 0,
        member_count=db.scalar(select(func.count()).select_from(Member)) or 0,
        order_count=db.scalar(select(func.count()).select_from(Order)) or 0,
        daily_orders=daily,
    )


@router.get("/analytics", response_model=AdminAnalyticsResponse)
def analytics(db: Session = Depends(get_db)):
    regions, ages, categories = Counter(), Counter(), Counter()
    rows = db.execute(select(Order.region, Order.age_group, Order.items).execution_options(yield_per=100))
    for region, age, items in rows:
        regions[region or "미응답"] += 1
        ages[age or "미응답"] += 1
        for item in items:
            categories[item["category_id"]] += item["quantity"]
    return AdminAnalyticsResponse(orders_by_region=dict(regions), orders_by_age_group=dict(ages),
                                  units_by_category=dict(categories))
