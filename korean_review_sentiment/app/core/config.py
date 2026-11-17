from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    APP_NAME: str = "한국어 리뷰 감정 분석 시스템"

    DEBUG: bool = True

    DATABASE_URL: str = "sqlite:///./sentiment.db"

    MODEL_PATH: str = "./models/sentiment_model"

    MAX_LENGTH: int = 256

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()