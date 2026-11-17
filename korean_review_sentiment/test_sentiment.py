from app.services.sentiment_service import (
    get_sentiment_analyzer
)


analyzer = get_sentiment_analyzer()


reviews = [
    "배송도 빠르고 제품도 정말 좋아요.",
    "가격 대비 품질이 너무 훌륭합니다.",
    "다음에도 꼭 재구매하겠습니다.",
    "제품이 너무 불편하고 품질도 형편없습니다.",
    "배송이 늦고 포장도 엉망입니다.",
    "돈이 아까워서 다시는 구매하지 않겠습니다."
]


for review in reviews:

    result = analyzer.predict(review)

    print("=" * 60)

    print("리뷰:", result["review_text"])

    print("감정:", result["sentiment"])

    print(
        "신뢰도:",
        f'{result["confidence"] * 100:.2f}%'
    )

    print(
        "부정:",
        f'{result["negative_score"] * 100:.2f}%'
    )

    print(
        "긍정:",
        f'{result["positive_score"] * 100:.2f}%'
    )