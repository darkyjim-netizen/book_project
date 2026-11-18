"""리뷰 작성·조회와 감성 분석에 사용하는 요청/응답 스키마."""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreateRequest(BaseModel):
    """회원이 리뷰를 작성할 때 보낼 데이터."""

    book_id: int  # 리뷰를 작성할 도서 번호
    order_item_id: Optional[int] = None  # 구매한 상품과 리뷰를 연결할 때 사용
    rating: int = Field(
        ...,
        ge=1,  # 별점은 최소 1점
        le=5,  # 별점은 최대 5점
    )
    title: Optional[str] = Field(None, max_length=200)  # 리뷰 제목. 생략 가능
    content: str = Field(
        ...,
        min_length=10,  # 리뷰 본문은 최소 10자
        max_length=5000,  # 최대 5,000자
    )
    image_urls: List[str] = []  # 리뷰에 첨부할 이미지 주소 목록


class ReviewUpdateRequest(BaseModel):
    """기존 리뷰를 수정할 때 보낼 데이터."""

    # 각 항목은 선택값이라 전달한 내용만 수정하도록 사용할 수 있다.
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, min_length=10, max_length=5000)


class SentimentResponse(BaseModel):
    """AI가 분석한 리뷰 감성 결과."""

    # SQLAlchemy 모델 객체의 속성을 읽어 응답 데이터로 변환한다.
    model_config = ConfigDict(from_attributes=True)

    label: str  # 분석 결과 분류. 예: 긍정, 중립, 부정
    score: float  # 대표 감성 점수
    positive_prob: float  # 긍정으로 판단한 확률
    neutral_prob: Optional[float] = None  # 중립으로 판단한 확률 (없으면 None)
    negative_prob: float  # 부정으로 판단한 확률
    keywords: Optional[Dict] = None  # 분석에 영향을 준 단어 정보
    model_version: str  # 분석에 사용한 AI 모델 버전


class ReviewResponse(BaseModel):
    """리뷰 한 건을 화면에 표시할 때 사용할 데이터."""

    review_id: int  # 리뷰 번호
    book_id: int  # 리뷰 대상 도서 번호
    book_title: Optional[str] = None  # 도서 제목
    cover_image: Optional[str] = None  # 도서 표지 이미지 주소
    member_id: int  # 작성한 회원 번호
    member_name: str  # 화면에 표시할 작성자 이름
    rating: int  # 별점
    title: Optional[str] = None  # 리뷰 제목
    content: str  # 리뷰 본문
    like_count: int  # 리뷰가 받은 좋아요 수
    is_best: bool  # 베스트 리뷰인지 여부
    is_liked: bool = False  # 현재 조회한 사용자가 좋아요를 눌렀는지 여부
    images: List[str] = []  # 첨부 이미지 주소 목록
    reply_content: Optional[str] = None  # 관리자 답변
    replied_at: Optional[datetime] = None  # 관리자 답변 시각
    sentiment: Optional[SentimentResponse] = None  # 감성 분석 결과가 있으면 포함
    created_at: datetime  # 리뷰 작성 시각


class ReviewStatsResponse(BaseModel):
    """도서 리뷰의 별점과 감성 분석 요약."""

    book_id: int  # 통계를 계산한 도서 번호
    review_count: int  # 리뷰 전체 개수
    rating_avg: float  # 평균 별점

    # 별점별 리뷰 개수.
    # 예: {"1": 2, "2": 1, "3": 5, "4": 10, "5": 20}
    rating_distribution: Dict[str, int]

    positive_count: int  # 긍정 리뷰 수
    neutral_count: int  # 중립 리뷰 수
    negative_count: int  # 부정 리뷰 수
    sentiment_score: Optional[float] = None  # 전체 감성 점수
    positive_keywords: List[str] = []  # 긍정 리뷰에서 자주 나온 단어
    negative_keywords: List[str] = []  # 부정 리뷰에서 자주 나온 단어


class ReviewReplyRequest(BaseModel):
    """관리자가 리뷰에 답변을 작성할 때 보낼 데이터."""

    reply_content: str = Field(
        ...,
        min_length=1,  # 답변을 비워 둘 수 없다.
        max_length=2000,
    )


class SentimentAnalyzeRequest(BaseModel):
    """관리자나 테스트 사용자가 임의의 글을 감성 분석할 때 보낼 데이터."""

    text: str = Field(
        ...,
        min_length=1,  # 분석할 텍스트는 필수
        max_length=5000,
    )