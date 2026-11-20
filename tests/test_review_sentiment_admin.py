from unittest.mock import Mock
import pytest
from app.core.exceptions import BusinessError
from app.models.enums import SentimentLabel
from app.routers.admin_extras import review_sentiment_summary, sentiment_review_results, run_review_sentiment


def test_summary_counts_labels_and_missing_reviews():
    db=Mock()
    db.scalar.side_effect=[5,None]
    db.execute.return_value.all.return_value=[(SentimentLabel.POSITIVE,2),(SentimentLabel.NEUTRAL,1),(SentimentLabel.NEGATIVE,1)]
    db.scalars.return_value.all.return_value=['hf-bert-3class-v1']
    result=review_sentiment_summary(None,db)
    assert result['total_reviews']==5
    assert result['analyzed_reviews']==4
    assert result['counts']=={'POSITIVE':2,'NEUTRAL':1,'NEGATIVE':1}


def test_running_analysis_is_not_started_twice():
    db=Mock()
    db.scalar.return_value=False
    with pytest.raises(BusinessError) as exc:
        run_review_sentiment(None,db)
    assert exc.value.status_code==409


def test_result_page_filters_label_and_paginates():
    db=Mock()
    db.scalar.return_value=0
    db.execute.return_value.all.return_value=[]
    result=sentiment_review_results(label='NEGATIVE',page=2,size=20,admin=None,db=db)
    assert result['items']==[]
    query=db.execute.call_args.args[0].compile().params
    assert 'NEGATIVE' in query.values()
    assert 20 in query.values()
