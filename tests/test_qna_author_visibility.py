from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.models.enums import QnaStatus
from app.services.support_service import QnaService

@pytest.mark.parametrize('admin,expected', [(True,'김회원'),(False,'김**'),(None,'김**')])
def test_only_admin_sees_full_question_author(admin,expected):
    q=SimpleNamespace(question_id=1,member_id=5,member=SimpleNamespace(name='김회원'),is_secret=True,category='ETC',title='문의',content='비밀 문의',status=QnaStatus.WAITING,book_id=None,view_count=0,answers=[],created_at=datetime.now(timezone.utc))
    viewer=None if admin is None else SimpleNamespace(member_id=9,is_admin=admin)
    result=QnaService(Mock()).to_response(q,viewer)
    assert result.member_name==expected
    assert result.content==('비밀 문의' if admin else None)
