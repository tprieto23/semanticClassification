import re

from bs4 import BeautifulSoup
from ftfy import fix_text
from markdown_it import MarkdownIt


class CleaningService:

    _URL_PATTERN = re.compile(r"https?://\S+|ftp://\S+|www\.\S+")
    _EMAIL_PATTERN = re.compile(r"[\w.\-]+@[\w\-]+\.\w{2,}")
    _PHONE_PATTERN = re.compile(
        r"\+?\d{1,4}?[\s.\-]?\(?\d{1,4}?\)?[\s.\-]?\d{1,4}[\s.\-]?\d{1,4}[\s.\-]?\d{1,9}"
    )
    _MULTISPACE = re.compile(r"\n{3,}")
    _SPACES = re.compile(r"[ \t]+")
    _SOLO_NUMERO = re.compile(r"^\d{1,4}$")

    @staticmethod
    def _eliminar_lineas_repetidas(texto: str, min_repeticiones: int = 3) -> str:
        """Elimina headers/footers recurrentes (Paso 3, fix #1).

        Una línea idéntica que se repite muchas veces a lo largo del documento
        suele ser un encabezado/pie de página que PyMuPDF extrae una vez por
        página (p. ej. el título del documento ×N páginas). Se conserva solo la
        primera aparición. Además se descartan líneas que son solo número de
        página (pies de página numéricos).
        """
        lineas = texto.split("\n")

        # Cuenta líneas no vacías normalizadas → candidatas a recurrentes.
        conteo: dict[str, int] = {}
        for ln in lineas:
            clave = ln.strip().lower()
            if clave:
                conteo[clave] = conteo.get(clave, 0) + 1
        recurrentes = {k for k, c in conteo.items() if c >= min_repeticiones}

        resultado: list[str] = []
        vistos: set[str] = set()
        for ln in lineas:
            clave = ln.strip().lower()
            # Pie de página numérico → descartar.
            if CleaningService._SOLO_NUMERO.match(clave):
                continue
            # Header/footer recurrente → conservar solo la 1ª aparición.
            if clave in recurrentes:
                if clave in vistos:
                    continue
                vistos.add(clave)
            resultado.append(ln)

        return "\n".join(resultado)

    @staticmethod
    def structuralCleaning(texto_md: str) -> str:
        texto = fix_text(texto_md)

        # Fix #1: quitar headers/footers repetidos por página antes del render.
        texto = CleaningService._eliminar_lineas_repetidas(texto)

        md = MarkdownIt("commonmark")
        html = md.render(texto)
        soup = BeautifulSoup(html, "html.parser")
        texto = soup.get_text()

        texto = CleaningService._URL_PATTERN.sub(" ", texto)
        texto = CleaningService._EMAIL_PATTERN.sub(" ", texto)
        texto = CleaningService._PHONE_PATTERN.sub(" ", texto)

        texto = CleaningService._MULTISPACE.sub("\n\n", texto)
        texto = CleaningService._SPACES.sub(" ", texto)
        texto = texto.strip()

        return texto.lower()

    @staticmethod
    def linguisticCleaning(texto: str) -> str:
        pass
