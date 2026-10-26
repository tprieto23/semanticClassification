from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    STORAGE_RAW: Path = Path("s3/archivosCrudos")
    STORAGE_CONVERTED: Path = Path("s3/archivosConvertidos")
    DATA_CLEANED: Path = Path("s3/archivosLimpiados")
    STORAGE_IMAGES: Path = Path("s3/imagenesExtraidas")
    STORAGE_NER: Path = Path("s3/archivosNER")
    STORAGE_GRAPHS: Path = Path("s3/graphs")
    STORAGE_NETWORK: Path = Path("s3/archivosRed")  # legado: preservado temporalmente

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_WORKSPACE_ID: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"
    NER_MAX_CHUNK_LEN: int = 12_000
    NER_CODEBOOK_PATH: Path = Path("data/codebooks/codebook_en_construccion_en.md")
    NER_PROMPT_PATH: Path = Path("data/prompts/ner_prompt.md")
    SEMANTIC_NODE_PROMPT_PATH: Path = Path("data/prompts/semantic_node_prompt.md")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
