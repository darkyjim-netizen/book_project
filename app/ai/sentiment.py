"""한국어 리뷰 감성 분석 모듈.

감성 어휘 사전 분석과 머신러닝 분석을 함께 사용한다.
머신러닝 모델이 없더라도 어휘 사전 분석만으로 결과를 낼 수 있다.
"""
import logging
import math
import os
import re
from typing import Dict, List, Optional, Tuple

from app.core.config import settings

# 추가
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
#여기까지

logger = logging.getLogger(__name__)

# 설정 파일에 지정된 모델 버전을 사용한다.
MODEL_VERSION = settings.SENTIMENT_MODEL_VERSION
# Hugging Face 3클래스(부정·중립·긍정) 모델로 분석한 결과에 붙이는 이름.
HF_MODEL_VERSION = "hf-bert-3class-v1"

# 학습한 머신러닝 모델을 저장할 파일 이름
ARTIFACT_NAME = "sentiment_lr.pkl"


# -----------------------------------------------------------------------------
# 감성 어휘 사전
# -----------------------------------------------------------------------------

# 단어별 긍정 점수다. 점수가 클수록 긍정적인 표현으로 강하게 본다.
POSITIVE_LEXICON: Dict[str, float] = {
    "좋다": 1.0, "좋았": 1.0, "좋은": 1.0, "좋네": 1.0, "좋아": 1.0, "좋습니": 1.0,
    "최고": 1.5, "훌륭": 1.4, "완벽": 1.5, "만족": 1.2, "추천": 1.3, "강추": 1.6,
    "감동": 1.4, "재미": 1.1, "재밌": 1.2, "흥미": 1.0, "유익": 1.2, "도움": 1.0,
    "친절": 0.9, "빠른": 0.8, "빠르": 0.8, "깔끔": 0.9, "선명": 0.7, "편안": 0.8,
    "잘읽": 1.0, "술술": 1.0, "몰입": 1.2, "여운": 1.0, "인상적": 1.2, "명작": 1.5,
    "탄탄": 1.0, "알차": 1.1, "쉽게": 0.8, "친근": 0.7, "가성비": 0.9, "저렴": 0.7,
    "정성": 0.9, "꼼꼼": 0.9, "유용": 1.1, "실용": 1.0, "참고": 0.6, "체계적": 1.1,
    "명확": 1.0, "친절한": 0.9, "포장": 0.4, "튼튼": 0.7, "감사": 0.9, "행복": 1.1,
    "사랑": 1.0, "따뜻": 1.0, "위로": 1.0, "성장": 0.8, "통찰": 1.2, "깊이": 0.9,
}

# 단어별 부정 점수다. 값이 클수록 부정적인 표현으로 강하게 본다.
NEGATIVE_LEXICON: Dict[str, float] = {
    "나쁘": 1.2, "최악": 1.8, "실망": 1.4, "불만": 1.2, "별로": 1.1, "아쉽": 0.9,
    "지루": 1.2, "지겨": 1.2, "노잼": 1.4, "재미없": 1.4, "어렵": 0.8, "난해": 1.0,
    "부실": 1.2, "엉성": 1.2, "허술": 1.2, "빈약": 1.1, "조잡": 1.3, "산만": 1.0,
    "오타": 0.9, "오역": 1.3, "번역": 0.4, "불친절": 1.2, "늦게": 0.9, "지연": 1.0,
    "파손": 1.5, "훼손": 1.5, "구겨": 1.2, "찢어": 1.4, "더럽": 1.3, "불량": 1.5,
    "환불": 1.2, "반품": 1.2, "후회": 1.4, "낭비": 1.3, "비싸": 0.9, "과대": 1.0,
    "뻔한": 1.0, "진부": 1.1, "억지": 1.1, "불편": 1.0, "짜증": 1.3, "화나": 1.3,
    "이해안": 1.1, "모르겠": 0.7, "두서없": 1.2, "반복": 0.6, "얇": 0.6, "부족": 1.0,
}

# 이 표현들이 감성 단어 앞뒤에 있으면 긍정·부정의 방향을 바꿀 수 있다.
NEGATION_PATTERNS = [
    "안",
    "못",
    "없",
    "않",
    "아니",
    "말고",
    "비추",
]

# 감성을 더 강하게 또는 약하게 만드는 부사와 배율
INTENSIFIERS = {
    "너무": 1.4,
    "정말": 1.3,
    "진짜": 1.3,
    "매우": 1.3,
    "완전": 1.4,
    "엄청": 1.35,
    "아주": 1.25,
    "굉장히": 1.3,
    "조금": 0.7,
    "약간": 0.7,
    "다소": 0.75,
    "살짝": 0.7,
}

# 한글, 영문, 숫자를 각각 하나의 토큰으로 찾는 정규식
TOKEN_RE = re.compile(r"[가-힣]+|[A-Za-z]+|\d+")


def tokenize(text: str) -> List[str]:
    """문장에서 한글·영문·숫자 토큰을 추출한다."""

    # text가 None이거나 빈 값이면 빈 문자열을 분석한다.
    return TOKEN_RE.findall(text or "")


# -----------------------------------------------------------------------------
# 사전 기반 분석기
# -----------------------------------------------------------------------------
class LexiconSentimentAnalyzer:
    """미리 정해 둔 긍정·부정 단어 사전으로 감성을 계산한다."""

    def score(
        self,
        text: str,
    ) -> Tuple[float, List[str], List[str]]:
        """감성 점수와 긍정·부정 키워드 목록을 반환한다."""

        if not text:
            return 0.0, [], []

        tokens = tokenize(text)
        positive_hits: List[str] = []
        negative_hits: List[str] = []
        total = 0.0

        # 문장의 각 토큰을 하나씩 확인한다.
        for idx, token in enumerate(tokens):
            multiplier = 1.0

            # 현재 단어 앞의 두 토큰까지 살펴 강조 부사가 있는지 확인한다.
            # 예: "정말 재미있다"에서 "정말"의 배율을 "재미있다"에 적용한다.
            for back in range(1, 3):
                previous_index = idx - back

                if (
                    previous_index >= 0
                    and tokens[previous_index] in INTENSIFIERS
                ):
                    multiplier *= INTENSIFIERS[tokens[previous_index]]

            # 감성 단어 뒤의 두 토큰에서 부정 표현을 찾는다.
            # 예: "재미 있지 않다"의 "않"을 찾으려는 처리다.
            negated = any(
                neg in tokens[idx + offset]
                for offset in (1, 2)
                if idx + offset < len(tokens)
                for neg in NEGATION_PATTERNS
            )

            # "좋지 않다"처럼 부정 표현이 현재 토큰 안에 포함된 경우도 확인한다.
            negated = negated or any(
                neg in token
                for neg in ("않", "없", "아니")
            )

            # 현재 단어가 긍정 사전 또는 부정 사전에 있는지 찾는다.
            pos_weight = self._lookup(token, POSITIVE_LEXICON)
            neg_weight = self._lookup(token, NEGATIVE_LEXICON)

            if pos_weight:
                # 긍정 단어 점수에 강조 부사 배율을 적용한다.
                value = pos_weight * multiplier

                if negated:
                    # 부정 표현이 붙으면 긍정 점수를 반대로 반영한다.
                    total -= value
                    negative_hits.append(token)
                else:
                    total += value
                    positive_hits.append(token)

            elif neg_weight:
                # 부정 단어에도 강조 부사 배율을 적용한다.
                value = neg_weight * multiplier

                if negated:
                    # 부정 표현이 붙으면 부정 효과를 일부 반대로 반영한다.
                    total += value * 0.6
                    positive_hits.append(token)
                else:
                    total -= value
                    negative_hits.append(token)

        # 점수 크기가 지나치게 커지지 않도록 -1부터 1 사이로 압축한다.
        normalized = math.tanh(total / 3.0)

        return (
            round(normalized, 4),
            positive_hits[:10],
            negative_hits[:10],
        )

    @staticmethod
    def _lookup(
        token: str,
        lexicon: Dict[str, float],
    ) -> float:
        """토큰이 감성 사전에 있는지 찾고 해당 점수를 반환한다."""

        # 완전히 같은 단어가 있으면 그 점수를 사용한다.
        if token in lexicon:
            return lexicon[token]

        # 활용형을 처리하기 위해 토큰이 사전 단어로 시작하는지도 확인한다.
        # 예: "좋았어요"가 사전의 "좋았"으로 시작하면 해당 점수를 사용한다.
        for key, weight in lexicon.items():
            if len(key) >= 2 and token.startswith(key):
                return weight

        # 일치하는 단어가 없으면 점수 0을 반환한다.
        return 0.0


# -----------------------------------------------------------------------------
# 지도학습 모델
# -----------------------------------------------------------------------------
class MlSentimentModel:
    """TF-IDF와 로지스틱 회귀를 이용해 감성을 분류한다."""

    def __init__(self) -> None:
        self.pipeline = None
        self.metrics: Dict = {}
        self.available = False

        # scikit-learn이 설치되어 있는지 확인한다.
        try:
            import sklearn  # noqa: F401

            self.sklearn_ready = True
        except ImportError:  # pragma: no cover
            # 라이브러리가 없으면 머신러닝 없이 사전 분석만 사용한다.
            self.sklearn_ready = False
            logger.warning(
                "scikit-learn 미설치: 사전 기반 감성분석만 사용합니다."
            )

    @property
    def artifact_path(self) -> str:
        """학습 모델 파일의 저장 경로를 반환한다."""

        return os.path.join(
            settings.AI_MODEL_DIR,
            ARTIFACT_NAME,
        )

    # ------------------------------------------------------------------ 모델 학습
    def train(
        self,
        texts: List[str],
        labels: List[int],
    ) -> Dict:
        """리뷰 문장과 라벨을 사용해 머신러닝 모델을 학습한다.

        labels에서 1은 긍정, 0은 부정이다.
        """

        # scikit-learn이 없으면 학습할 수 없다.
        if not self.sklearn_ready:
            return {
                "trained": False,
                "reason": "scikit-learn not installed",
            }

        # 긍정·부정 중 한 종류만 있거나 데이터가 너무 적으면 학습하지 않는다.
        if len(set(labels)) < 2 or len(texts) < 20:
            return {
                "trained": False,
                "reason": "insufficient labeled data",
                "rows": len(texts),
            }

        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import (
            accuracy_score,
            f1_score,
            roc_auc_score,
        )
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline

        # 데이터를 학습용 80%, 평가용 20%로 나눈다.
        # stratify는 학습·평가 데이터의 긍정/부정 비율을 비슷하게 유지한다.
        x_train, x_test, y_train, y_test = train_test_split(
            texts,
            labels,
            test_size=0.2,
            random_state=42,
            stratify=labels,
        )

        # 문장을 숫자 벡터로 바꾼 다음 로지스틱 회귀 분류기를 연결한다.
        pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        # 단어 대신 문자 조각을 사용해 한국어 어미 변화를 다룬다.
                        analyzer="char_wb",
                        ngram_range=(2, 4),
                        min_df=2,
                        max_features=50000,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=1000,
                        C=4.0,
                        class_weight="balanced",
                    ),
                ),
            ]
        )

        # 학습용 문장과 라벨로 모델을 학습한다.
        pipeline.fit(x_train, y_train)

        # 평가용 문장을 예측해 모델 품질을 계산한다.
        pred = pipeline.predict(x_test)
        proba = pipeline.predict_proba(x_test)[:, 1]

        metrics = {
            "trained": True,
            "rows": len(texts),
            "accuracy": round(
                float(accuracy_score(y_test, pred)),
                4,
            ),
            "f1": round(
                float(f1_score(y_test, pred)),
                4,
            ),
            # 평가 데이터에 라벨이 한 종류만 있으면 AUC를 계산할 수 없다.
            "auc": (
                round(float(roc_auc_score(y_test, proba)), 4)
                if len(set(y_test)) > 1
                else None
            ),
            "positive_ratio": round(
                sum(labels) / len(labels),
                4,
            ),
        }

        # 학습된 모델과 평가 결과를 객체에 보관하고 파일로 저장한다.
        self.pipeline = pipeline
        self.metrics = metrics
        self.available = True
        self.save()

        logger.info("감성분석 모델 학습 완료: %s", metrics)
        return metrics

    def save(self) -> str:
        """학습된 모델과 평가 정보를 파일로 저장한다."""

        import pickle

        # 모델 저장 폴더가 없으면 만든다.
        os.makedirs(settings.AI_MODEL_DIR, exist_ok=True)

        # 나중에 다시 사용할 수 있도록 pickle 파일로 저장한다.
        with open(self.artifact_path, "wb") as fp:
            pickle.dump(
                {
                    "pipeline": self.pipeline,
                    "metrics": self.metrics,
                },
                fp,
            )

        return self.artifact_path

    def load(self) -> bool:
        """저장된 머신러닝 모델을 불러온다."""

        # 라이브러리나 모델 파일이 없으면 불러올 수 없다.
        if (
            not self.sklearn_ready
            or not os.path.exists(self.artifact_path)
        ):
            return False

        import pickle

        try:
            with open(self.artifact_path, "rb") as fp:
                data = pickle.load(fp)

            self.pipeline = data.get("pipeline")
            self.metrics = data.get("metrics", {})
            self.available = self.pipeline is not None

            return self.available

        except Exception as exc:  # pragma: no cover
            logger.error("감성분석 모델 로드 실패: %s", exc)
            return False

    def predict_proba(self, text: str) -> Optional[float]:
        """문장이 긍정일 확률을 반환한다. 모델이 없으면 None을 반환한다."""

        if not self.available or self.pipeline is None:
            return None

        try:
            # predict_proba 결과 중 긍정(라벨 1)일 확률만 가져온다.
            return float(self.pipeline.predict_proba([text])[0][1])
        except Exception:  # pragma: no cover
            # 추론 실패 시 사전 분석 결과를 사용할 수 있도록 None을 반환한다.
            return None


class HuggingFaceSentimentModel:
    def __init__(self):
        self.available = False
        self.tokenizer = None
        self.model = None

        model_path = Path(settings.MODEL_PATH)
        if not model_path.exists():
            logger.warning("Hugging Face 모델 폴더를 찾을 수 없습니다: %s", model_path)
            return

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            str(model_path), local_files_only=True
        )
        self.model.to(self.device)
        self.model.eval()

        # 모델 설정(id2label)에서 부정·중립·긍정이 몇 번째 출력인지 찾는다.
        # 설정에 이름이 없으면 학습 때 쓴 순서(0 부정, 1 중립, 2 긍정)로 본다.
        id2label = {
            int(k): str(v).lower()
            for k, v in (self.model.config.id2label or {}).items()
        }
        name_to_idx = {v: k for k, v in id2label.items()}
        self.label_index = {
            "negative": name_to_idx.get("negative", 0),
            "neutral": name_to_idx.get("neutral", 1),
            "positive": name_to_idx.get("positive", 2),
        }
        self.available = True

    def predict_probs(self, text: str) -> Optional[Dict[str, float]]:
        """부정·중립·긍정 확률을 {"negative":.., "neutral":.., "positive":..} 로 반환한다.

        세 값의 합은 1이다. 모델을 쓸 수 없으면 None 을 반환한다.
        """
        if not self.available:
            return None

        inputs = self.tokenizer(
            text or "",
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=128,
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        with torch.inference_mode():
            logits = self.model(**inputs).logits
            probabilities = torch.softmax(logits, dim=-1)[0]

        return {
            name: float(probabilities[idx].item())
            for name, idx in self.label_index.items()
        }

    def predict_proba(self, text: str) -> Optional[float]:
        """긍정 확률만 필요할 때 쓰는 기존 함수 (predict_probs 의 긍정 값)."""
        probs = self.predict_probs(text)
        return None if probs is None else probs["positive"]


# -----------------------------------------------------------------------------
# 사전 분석과 머신러닝 결과를 합치는 분석기
# -----------------------------------------------------------------------------
class SentimentAnalyzer:
    """사전 분석과 머신러닝 예측을 조합해 최종 감성을 판단한다."""

    # 이 점수 이상이면 긍정, 이 점수 이하면 부정으로 분류한다.
    POSITIVE_THRESHOLD = 0.15
    NEGATIVE_THRESHOLD = -0.15

    # 두 분석 결과를 최종 점수에 반영할 비율
    LEXICON_WEIGHT = 0.4
    MODEL_WEIGHT = 0.6

    def __init__(self) -> None:
        self.lexicon = LexiconSentimentAnalyzer()
        self.model = MlSentimentModel()
        
        # 저장된 학습 모델이 있으면 불러온다.
        self.model.load()

        self.hf_model = HuggingFaceSentimentModel()
        
    def analyze(self, text: str) -> Dict:
        """문장을 분석해 감성 라벨, 점수, 확률, 키워드를 반환한다.

        - Hugging Face 3클래스 모델이 있으면: 부정·중립·긍정 확률을 모두 구하고,
          라벨은 세 확률 중 가장 높은 것, 점수는 (긍정 - 부정) 확률로 정한다.
        - 모델이 없으면: 기존 방식(사전 점수 + 2클래스 모델)을 쓰고 neutral_prob 는 None 이다.
        """

        # 어휘 사전으로 분석한 점수와 긍정·부정 단어를 가져온다.
        lex_score, pos_kw, neg_kw = self.lexicon.score(text)

        hf_probs = self.hf_model.predict_probs(text)

        if hf_probs is not None:
            positive_prob = hf_probs["positive"]
            neutral_prob = hf_probs["neutral"]
            negative_prob = hf_probs["negative"]

            # 세 확률 중 가장 높은 것이 최종 라벨이다.
            label = max(hf_probs, key=hf_probs.get).upper()

            # 점수 -1~1: 긍정이 확실하면 +1, 부정이 확실하면 -1, 중립이면 0 근처.
            score = positive_prob - negative_prob
            used_ml = True
            model_version = HF_MODEL_VERSION

        else:
            # 모델이 없으면 기존 2클래스 모델 또는 사전 분석 결과를 쓴다.
            model_proba = self.model.predict_proba(text)

            if model_proba is not None:
                # 긍정 확률 0~1을 감성 점수 -1~1로 변환한다.
                model_score = (model_proba - 0.5) * 2

                # 사전 점수와 머신러닝 점수의 가중 평균을 구한다.
                score = (
                    self.LEXICON_WEIGHT * lex_score
                    + self.MODEL_WEIGHT * model_score
                )
                positive_prob = model_proba
            else:
                # 사전 점수 -1~1을 확률처럼 표시할 수 있도록 0~1로 바꾼다.
                score = lex_score
                positive_prob = (lex_score + 1) / 2

            negative_prob = 1 - positive_prob
            neutral_prob = None  # 2클래스 방식에서는 중립 확률을 알 수 없다.

            # 점수 구간에 따라 긍정·중립·부정 라벨을 정한다.
            score = max(-1.0, min(1.0, score))
            if score >= self.POSITIVE_THRESHOLD:
                label = "POSITIVE"
            elif score <= self.NEGATIVE_THRESHOLD:
                label = "NEGATIVE"
            else:
                label = "NEUTRAL"

            used_ml = model_proba is not None
            model_version = (
                MODEL_VERSION
                if self.model.available
                else f"{MODEL_VERSION}-lexicon"
            )

        # 최종 점수가 -1보다 작거나 1보다 커지지 않게 제한한다.
        score = max(-1.0, min(1.0, score))

        return {
            "label": label,
            "score": round(score, 4),
            "positive_prob": round(positive_prob, 4),
            "neutral_prob": None if neutral_prob is None else round(neutral_prob, 4),
            "negative_prob": round(negative_prob, 4),
            "positive_keywords": pos_kw,
            "negative_keywords": neg_kw,
            # 어떤 모델로 분석했는지 구분하는 이름.
            "model_version": model_version,
            "used_ml_model": used_ml,
        }

    def analyze_batch(
        self,
        texts: List[str],
    ) -> List[Dict]:
        """여러 문장을 차례대로 분석해 결과 목록을 반환한다."""

        return [
            self.analyze(text)
            for text in texts
        ]

    def train_from_reviews(self, db) -> Dict:
        """DB에 저장된 리뷰와 별점을 사용해 머신러닝 모델을 학습한다."""

        from sqlalchemy import text as sql_text

        # 블라인드되지 않았고, 중립 평점이 아니며, 내용이 충분한 리뷰만 가져온다.
        rows = db.execute(
            sql_text(
                """
                SELECT content, rating
                FROM shop.reviews
                WHERE is_blinded = false
                  AND rating <> 3
                  AND length(content) >= 10
                """
            )
        ).all()

        texts = [row[0] for row in rows]

        # 별점 4~5점은 긍정(1), 1~2점은 부정(0) 라벨로 바꾼다.
        labels = [
            1 if int(row[1]) >= 4 else 0
            for row in rows
        ]

        return self.model.train(texts, labels)

    def reanalyze_all(
        self,
        db,
        batch_size: int = 500,
    ) -> int:
        """기존 리뷰 전체를 다시 분석하고 결과를 DB에 저장한다."""

        from sqlalchemy import text as sql_text

        # 블라인드되지 않은 모든 리뷰의 번호, 도서 번호, 내용을 가져온다.
        rows = db.execute(
            sql_text(
                """
                SELECT review_id, book_id, content
                FROM shop.reviews
                WHERE is_blinded = false
                """
            )
        ).all()

        # 기존 감성 분석 결과를 지운 뒤 최신 결과로 다시 만든다.
        db.execute(
            sql_text("DELETE FROM ai.review_sentiments")
        )

        payloads = []

        for review_id, book_id, content in rows:
            result = self.analyze(content)

            # 각 분석 결과를 DB 입력용 딕셔너리로 바꾼다.
            payloads.append(
                {
                    "rid": review_id,
                    "bid": book_id,
                    "label": result["label"],
                    "score": result["score"],
                    "pp": result["positive_prob"],
                    "np": result["negative_prob"],
                    "nu": result["neutral_prob"],
                    # 키워드는 JSON 문자열로 바꿔 DB JSONB 칼럼에 넣는다.
                    "kw": __import__("json").dumps(
                        {
                            "positive": result["positive_keywords"],
                            "negative": result["negative_keywords"],
                        },
                        ensure_ascii=False,
                    ),
                    "ver": result["model_version"],
                }
            )

        # 한 번에 너무 많은 데이터를 보내지 않도록 batch_size만큼 나눠 저장한다.
        for i in range(0, len(payloads), batch_size):
            batch = payloads[i : i + batch_size]

            db.execute(
                sql_text(
                    """
                    INSERT INTO ai.review_sentiments(
                        review_id,
                        book_id,
                        label,
                        score,
                        positive_prob,
                        negative_prob,
                        neutral_prob,
                        keywords,
                        model_version
                    )
                    VALUES (
                        :rid,
                        :bid,
                        CAST(:label AS shop.sentiment_label),
                        :score,
                        :pp,
                        :np,
                        :nu,
                        CAST(:kw AS jsonb),
                        :ver
                    )
                    ON CONFLICT (review_id)
                    DO UPDATE SET
                        label = EXCLUDED.label,
                        score = EXCLUDED.score,
                        positive_prob = EXCLUDED.positive_prob,
                        negative_prob = EXCLUDED.negative_prob,
                        neutral_prob = EXCLUDED.neutral_prob,
                        keywords = EXCLUDED.keywords,
                        model_version = EXCLUDED.model_version,
                        analyzed_at = now()
                    """
                ),
                batch,
            )

        # 새로 저장한 감성 점수의 도서별 평균으로 책 정보를 갱신한다.
        db.execute(
            sql_text(
                """
                UPDATE shop.books b
                SET sentiment_score = s.avg_score
                FROM (
                    SELECT book_id, AVG(score) AS avg_score
                    FROM ai.review_sentiments
                    GROUP BY book_id
                ) s
                WHERE b.book_id = s.book_id
                """
            )
        )

        db.commit()

        logger.info(
            "리뷰 감성분석 재생성 완료: %d건",
            len(payloads),
        )
        return len(payloads)


# 분석기를 매번 새로 만들지 않도록 전역 변수에 한 번 저장한다.
_analyzer: Optional[SentimentAnalyzer] = None


def get_analyzer() -> SentimentAnalyzer:
    """전역 감성 분석기 객체를 가져오거나 처음 한 번 생성한다."""

    global _analyzer

    if _analyzer is None:
        _analyzer = SentimentAnalyzer()

    return _analyzer


def reload_analyzer() -> SentimentAnalyzer:
    """새로 학습한 모델을 적용할 수 있도록 분석기를 다시 만든다."""

    global _analyzer
    _analyzer = SentimentAnalyzer()
    return _analyzer