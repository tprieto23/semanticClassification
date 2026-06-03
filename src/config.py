from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    POSTGRES_DB: str = "semantic_db"
    POSTGRES_USER: str = "sc_user"
    POSTGRES_PASSWORD: str = "sc_password"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: str | None = None

    DATA_RAW: Path = Path("data/raw")
    DATA_TXT: Path = Path("data/processed/txt")
    DATA_CLEANED: Path = Path("data/processed/cleaned")

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
