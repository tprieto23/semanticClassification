from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    STORAGE_RAW: Path = Path("s3/archivosCrudos")
    STORAGE_CONVERTED: Path = Path("s3/archivosConvertidos")
    DATA_CLEANED: Path = Path("s3/archivosLimpiados")
    STORAGE_IMAGES: Path = Path("s3/imagenesExtraidas")
    STORAGE_NER: Path = Path("s3/archivosNER")

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"
    NER_MAX_CHUNK_LEN: int = 48_000
    NER_ANNOTATIONS_PATH: Path = Path("data/ner/annotations/a251048a.json")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
