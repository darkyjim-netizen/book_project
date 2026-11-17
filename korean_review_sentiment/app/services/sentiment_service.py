import torch

from pathlib import Path

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification
)

from app.core.config import settings


class SentimentAnalyzer:

    def __init__(self):

        self.model_path = Path(settings.MODEL_PATH)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"모델 경로를 찾을 수 없습니다: {self.model_path}"
            )

        # GPU 사용 가능 여부 확인
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        print("사용 장치:", self.device)

        # Tokenizer 로딩
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_path),
            local_files_only=True
        )

        # Transformer 모델 로딩
        self.model = AutoModelForSequenceClassification.from_pretrained(
            str(self.model_path),
            local_files_only=True
        )

        # GPU 또는 CPU로 모델 이동
        self.model.to(self.device)

        # 추론 모드 설정
        self.model.eval()

        # 모델의 클래스 수 검증
        if self.model.config.num_labels != 2:
            raise ValueError(
                "이번 프로젝트는 긍정/부정 2개 클래스 모델을 요구합니다."
            )

        # 이 모델 카드의 레이블 순서
        self.label_map = {
            0: "부정",
            1: "긍정"
        }

        print("한국어 감정 분석 모델 로딩 완료!")

    def predict(self, text: str):

        # 1. Tokenizer
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=settings.MAX_LENGTH
        )

        # 2. 입력 데이터를 장치로 이동
        inputs = {
            key: value.to(self.device)
            for key, value in inputs.items()
        }

        # 3. 모델 추론
        with torch.inference_mode():

            outputs = self.model(**inputs)

            logits = outputs.logits

            # 4. Softmax 확률 계산
            probabilities = torch.softmax(
                logits,
                dim=-1
            )[0]

        # 5. 가장 높은 확률의 클래스 선택
        predicted_index = int(
            torch.argmax(probabilities).item()
        )

        sentiment = self.label_map[predicted_index]

        negative_score = float(probabilities[0].item())

        positive_score = float(probabilities[1].item())

        confidence = float(
            probabilities[predicted_index].item()
        )

        return {
            "review_text": text,
            "sentiment": sentiment,
            "confidence": confidence,
            "negative_score": negative_score,
            "positive_score": positive_score
        }


# 프로그램에서 공통으로 사용하는 모델 객체
sentiment_analyzer = None


def get_sentiment_analyzer():

    global sentiment_analyzer

    if sentiment_analyzer is None:
        sentiment_analyzer = SentimentAnalyzer()

    return sentiment_analyzer