from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "充电平台调价中台"
    APP_VERSION: str = "1.0.0"
    DATABASE_URL: str = "sqlite:///./pricing_platform.db"
    API_PREFIX: str = "/api/v1"

    PUBLISH_MAX_RETRY: int = 3
    PUBLISH_RETRY_INTERVAL_SECONDS: int = 30
    GRAYSCALE_DEFAULT_RATIO: float = 0.1

    PRICE_UPPER_LIMIT_DEFAULT: float = 5.0
    PRICE_LOWER_LIMIT_DEFAULT: float = 0.1

    FREEZE_CHECK_ENABLED: bool = True
    CONFLICT_DETECTION_ENABLED: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
