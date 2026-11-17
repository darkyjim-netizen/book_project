
from pathlib import Path

from huggingface_hub import snapshot_download


# Hugging Face 모델 ID
MODEL_ID = "WhitePeak/bert-base-cased-Korean-sentiment"

# 다운로드할 로컬 디렉터리
MODEL_DIR = Path("models/sentiment_model")

MODEL_DIR.mkdir(parents=True, exist_ok=True)

print("한국어 감정 분석 모델 다운로드 시작")

download_path = snapshot_download(
    repo_id=MODEL_ID,
    local_dir=str(MODEL_DIR)
)

print("모델 다운로드 완료!")
print(f"저장 위치: {download_path}")