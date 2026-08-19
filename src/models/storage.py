from pathlib import Path
from uuid import uuid4


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
    def guardar(content: bytes, filename: str, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        path.write_bytes(content)
        return path

    @staticmethod
    def eliminar(file_path: str | None) -> None:
        if not file_path:
            return
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def eliminar_directorio(dir_path: str | None) -> None:
        if not dir_path:
            return
        try:
            import shutil

            shutil.rmtree(dir_path, ignore_errors=True)
        except OSError:
            pass

    @staticmethod
    def leer(file_path: str) -> str | None:
        p = Path(file_path)
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8")
