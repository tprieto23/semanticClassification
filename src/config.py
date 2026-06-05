from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    STORAGE_RAW: Path = Path("s3/archivosCrudos")
    DATA_TXT: Path = Path("data/processed/txt")
    DATA_CLEANED: Path = Path("data/processed/cleaned")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
