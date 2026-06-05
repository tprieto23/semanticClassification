from pathlib import Path
from uuid import uuid4

from src.config import settings


class Storage:

    @staticmethod
    def _nombre_seguro(filename: str) -> str:
        return Path(filename).name

    @staticmethod
    def _extension(filename: str) -> str:
        return Path(filename).suffix.lower().lstrip(".")

    @staticmethod
    def preparar_nombre(original_filename: str) -> tuple[str, str, str, str]:
        nombreInicial = Storage._nombre_seguro(original_filename)
        ext = Storage._extension(nombreInicial)
        doc_id = str(uuid4())
        nombreParaAlmacenar = f"{doc_id}.{ext}"
        return nombreInicial, ext, doc_id, nombreParaAlmacenar

    @staticmethod
    def guardar(content: bytes, filename: str) -> Path:
        settings.STORAGE_RAW.mkdir(parents=True, exist_ok=True)
        path = settings.STORAGE_RAW / filename
        path.write_bytes(content)
        return path

    @staticmethod
    def eliminar(file_path: str) -> None:
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError:
            pass
