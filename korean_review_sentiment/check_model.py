
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification
)

MODEL_DIR = "./models/sentiment_model"

print("토크나이저 로딩")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_DIR,
    local_files_only=True
)

print("모델 로딩")

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_DIR,
    local_files_only=True
)

print("모델 로딩 성공!")

print("모델 클래스:", model.__class__.__name__)
print("분류 클래스 수:", model.config.num_labels)
print("레이블 정보:", model.config.id2label)