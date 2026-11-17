
import pandas as pd
import torch

from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification
)
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, f1_score


# =====================================
# 1. 기본 경로 및 설정
# =====================================

BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "data" / "review.csv"
PRETRAINED_MODEL_PATH = BASE_DIR / "models" / "sentiment_model"
SAVE_MODEL_PATH = BASE_DIR / "models" / "sentiment_model_trained"

DEVICE = torch.device("cpu")

MAX_LENGTH = 128
BATCH_SIZE = 4
EPOCHS = 1
LEARNING_RATE = 2e-5

LABEL2ID = {
    "negative": 0,
    "neutral": 1,
    "positive": 2
}

ID2LABEL = {
    0: "negative",
    1: "neutral",
    2: "positive"
}


# =====================================
# 2. 데이터 불러오기 및 확인
# =====================================

print("\n===== 데이터 불러오기 =====")

df = pd.read_csv(DATA_PATH)

df = df.dropna(subset=["text", "label"])

df["label"] = df["label"].str.strip().str.lower()
df["label_id"] = df["label"].map(LABEL2ID)

df = df.dropna(subset=["label_id"])

df["label_id"] = df["label_id"].astype(int)

print("전체 데이터:", len(df))
print("\n감정별 데이터 개수:")
print(df["label"].value_counts())


# =====================================
# 3. 학습 / 검증 / 테스트 데이터 분리
# =====================================

print("\n===== 데이터 분리 =====")

train_df, temp_df = train_test_split(
    df,
    test_size=0.2,
    random_state=42,
    stratify=df["label_id"]
)

valid_df, test_df = train_test_split(
    temp_df,
    test_size=0.5,
    random_state=42,
    stratify=temp_df["label_id"]
)

print("학습 데이터:", len(train_df))
print("검증 데이터:", len(valid_df))
print("테스트 데이터:", len(test_df))


# =====================================
# 4. 토크나이저 불러오기
# =====================================

print("\n===== 토크나이저 불러오기 =====")

tokenizer = AutoTokenizer.from_pretrained(
    str(PRETRAINED_MODEL_PATH)
)


# =====================================
# 5. 데이터셋 클래스 정의
# =====================================

class ReviewDataset(Dataset):

    def __init__(self, dataframe):
        self.texts = dataframe["text"].astype(str).tolist()
        self.labels = dataframe["label_id"].tolist()

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, index):

        encoding = tokenizer(
            self.texts[index],
            max_length=MAX_LENGTH,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(
                self.labels[index],
                dtype=torch.long
            )
        }


train_dataset = ReviewDataset(train_df)
valid_dataset = ReviewDataset(valid_df)
test_dataset = ReviewDataset(test_df)

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True
)

valid_loader = DataLoader(
    valid_dataset,
    batch_size=BATCH_SIZE
)

test_loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE
)


# =====================================
# 6. 3개 클래스 BERT 모델 불러오기
# =====================================

print("\n===== 3개 클래스 모델 불러오기 =====")

model = AutoModelForSequenceClassification.from_pretrained(
    str(PRETRAINED_MODEL_PATH),
    num_labels=3,
    id2label=ID2LABEL,
    label2id=LABEL2ID,
    ignore_mismatched_sizes=True
)

model.to(DEVICE)

print("모델 출력 클래스:", model.config.num_labels)


# =====================================
# 7. 손실 함수와 최적화 도구
# =====================================

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=LEARNING_RATE
)


# =====================================
# 8. 모델 학습
# =====================================

print("\n===== 모델 학습 시작 =====")

for epoch in range(EPOCHS):

    model.train()

    total_loss = 0

    for step, batch in enumerate(train_loader):

        input_ids = batch["input_ids"].to(DEVICE)
        attention_mask = batch["attention_mask"].to(DEVICE)
        labels = batch["labels"].to(DEVICE)

        optimizer.zero_grad()

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels
        )

        loss = outputs.loss

        loss.backward()

        optimizer.step()

        total_loss += loss.item()

        if (step + 1) % 50 == 0:
            print(
                f"Epoch {epoch + 1}/{EPOCHS} "
                f"| Step {step + 1}/{len(train_loader)} "
                f"| Loss: {loss.item():.4f}"
            )

    average_loss = total_loss / len(train_loader)

    print(
        f"\nEpoch {epoch + 1} 학습 완료 "
        f"| 평균 Loss: {average_loss:.4f}"
    )


# =====================================
# 9. 검증 데이터 평가
# =====================================

def evaluate(model, data_loader):

    model.eval()

    predictions = []
    actual_labels = []

    with torch.no_grad():

        for batch in data_loader:

            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            labels = batch["labels"].to(DEVICE)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )

            predicted = torch.argmax(
                outputs.logits,
                dim=1
            )

            predictions.extend(predicted.cpu().tolist())
            actual_labels.extend(labels.cpu().tolist())

    accuracy = accuracy_score(actual_labels, predictions)

    macro_f1 = f1_score(
        actual_labels,
        predictions,
        average="macro"
    )

    return accuracy, macro_f1, actual_labels, predictions


print("\n===== 검증 데이터 평가 =====")

valid_accuracy, valid_f1, _, _ = evaluate(
    model,
    valid_loader
)

print("검증 정확도:", round(valid_accuracy, 4))
print("검증 Macro F1:", round(valid_f1, 4))


# =====================================
# 10. 테스트 데이터 최종 평가
# =====================================

print("\n===== 테스트 데이터 최종 평가 =====")

test_accuracy, test_f1, actual, predicted = evaluate(
    model,
    test_loader
)

print("테스트 정확도:", round(test_accuracy, 4))
print("테스트 Macro F1:", round(test_f1, 4))

print("\n감정별 평가 결과:")

print(
    classification_report(
        actual,
        predicted,
        labels=[0, 1, 2],
        target_names=["negative", "neutral", "positive"],
        zero_division=0
    )
)


# =====================================
# 11. 학습된 모델 저장
# =====================================

print("\n===== 모델 저장 =====")

SAVE_MODEL_PATH.mkdir(
    parents=True,
    exist_ok=True
)

model.save_pretrained(str(SAVE_MODEL_PATH))
tokenizer.save_pretrained(str(SAVE_MODEL_PATH))

print("모델 저장 완료!")
print("저장 위치:", SAVE_MODEL_PATH)