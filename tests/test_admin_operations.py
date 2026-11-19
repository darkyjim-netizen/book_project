from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from app.core.security import get_current_member
from app.models.enums import MemberRole
from app.routers.admin_extras import CouponCreate
from app.routers.admin_extras import review_sentiment_summary
from app.models.enums import SentimentLabel


def test_coupon_rules_reject_invalid_discount_and_expiry():
    base = dict(code='TEST', name='테스트', coupon_type='PERCENT', discount_value=10,
                valid_to=datetime.now(timezone.utc) + timedelta(days=1))
    assert CouponCreate(**base).discount_value == 10
    for invalid in ({'discount_value': 101}, {'discount_value': 0},
                    {'valid_to': datetime.now(timezone.utc) - timedelta(days=1)},
                    {'total_quantity': 0}, {'code': '공백 코드'}):
        with pytest.raises(ValidationError):
            CouponCreate(**{**base, **invalid})


@pytest.mark.parametrize('path', ['/api/v1/admin/reviews', '/api/v1/admin/coupons', '/api/v1/admin/analysis/review-sentiment'])
def test_new_admin_lists_reject_regular_members(path):
    app.dependency_overrides[get_current_member] = lambda: SimpleNamespace(role=MemberRole.USER)
    try:
        with TestClient(app) as client:
            response = client.get(path)
            assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_member, None)


def test_sentiment_summary_reports_coverage_and_labels():
    db = Mock()
    db.scalar.side_effect = [7, None]
    db.execute.return_value.all.return_value = [(SentimentLabel.POSITIVE, 2), (SentimentLabel.NEGATIVE, 1)]
    db.scalars.return_value.all.return_value = ['test-model']
    result = review_sentiment_summary(None, db)
    assert result['total_reviews'] == 7
    assert result['analyzed_reviews'] == 3
    assert result['counts'] == {'POSITIVE': 2, 'NEUTRAL': 0, 'NEGATIVE': 1}
    assert result['model_versions'] == ['test-model']
