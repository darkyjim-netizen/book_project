from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.core.exceptions import NotFoundError
from app.routers.admin_extras import ReviewManagementUpdate, update_review_management

@pytest.mark.parametrize('private,reply',[(True,'관리자 답글'),(False,'' )])
def test_review_state_and_reply_saved_together(private,reply):
    review=SimpleNamespace(content='회원 원문',is_blinded=False,reply_content='기존 답글',replied_at=None)
    db=Mock(); db.get.return_value=review
    update_review_management(1,ReviewManagementUpdate(is_blinded=private,reply_content=reply),None,db)
    assert review.content=='회원 원문'
    assert review.is_blinded==private
    assert review.reply_content==(reply or None)
    db.commit.assert_called_once()

def test_missing_review_is_not_saved():
    db=Mock();db.get.return_value=None
    with pytest.raises(NotFoundError):
        update_review_management(1,ReviewManagementUpdate(is_blinded=False),None,db)
    db.commit.assert_not_called()
