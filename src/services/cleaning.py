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

    @staticmethod
    def structuralCleaning(texto_md: str) -> str:
        texto = fix_text(texto_md)

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
