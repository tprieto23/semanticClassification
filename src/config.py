from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    STORAGE_RAW: Path = Path("s3/archivosCrudos")
    STORAGE_CONVERTED: Path = Path("s3/archivosConvertidos")
    DATA_CLEANED: Path = Path("s3/archivosLimpiados")
    STORAGE_IMAGES: Path = Path("s3/imagenesExtraidas")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
