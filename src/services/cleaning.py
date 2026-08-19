import logging
import re

from bs4 import BeautifulSoup
from ftfy import fix_text
from markdown_it import MarkdownIt

from src.config import settings
from src.services.llm_client import get_anthropic_client

logger = logging.getLogger(__name__)

LIMPIEZA_LINGUISTICA_SYSTEM_PROMPT = """Eres un editor experto en textos académicos e institucionales sobre temas territoriales, socioambientales y de gobernanza en la Amazonía peruana.

Recibes un texto que ya fue limpiado estructuralmente. Realiza una limpieza lingüística conservadora:

1. Elimina la sección completa de "Referencias", "Bibliografía", "Fuentes consultadas" o cualquier sección similar, junto con todo su contenido desde ese punto en adelante.
2. Elimina citas entre paréntesis de tipo académico: (Apellido, 2020), (Apellido y Otro, 2015), (Apellido et al., 2018), etc.
3. Elimina notas al pie numeradas.
4. Elimina líneas sueltas que sean referencias bibliográficas.
5. NO elimines normas, leyes, decretos, resoluciones, ni citas institucionales.
6. NO cambies el contenido semántico del texto. NO resumas, NO parafrasees, NO agregues información.
7. Conserva los párrafos originales separados por doble salto de línea (\\n\\n).
8. Conserva mayúsculas, puntuación y números.
9. Devuelve SOLO el texto limpio, sin explicaciones ni comentarios adicionales."""


class CleaningService:
    # --- Patrones de contacto ---
    _URL_PATTERN = re.compile(
        r"(?:https?|ftp)://[^\s<>\"')]+|www\.[^\s<>\"')]+|"
        r"(?<![@\w])[^\s<>\"'):/@]+\."
        r"(?:com|org|net|edu|gov|pe|co|mx|ar|cl|br|es|int|io|ai|info|biz|coop)"
        r"[^\s<>\"')]*",
        re.IGNORECASE,
    )
    _EMAIL_PATTERN = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w{2,}")
    _PHONE_PATTERN = re.compile(
        r"(?:\+\d{1,3}[\s.\-])?"
        r"(?:"
        r"\d{3}[\s.\-]\d{3}[\s.\-]\d{3}"
        r"|"
        r"\d{2}[\s.\-]\d{3}[\s.\-]\d{4}"
        r"|"
        r"\d{1}[\s.\-]\d{3}[\s.\-]\d{4}"
        r"|"
        r"\(\d{1,4}\)[\s.\-]?\d{3}[\s.\-]\d{4}"
        r"|"
        r"\(\d{3}\)[\s.\-]?\d{3}[\s.\-]\d{3}"
        r")"
    )

    _MULTISPACE = re.compile(r"\n{3,}")
    _SPACES = re.compile(r"[ \t]+")
    _SOLO_NUMERO = re.compile(r"^\s*\d{1,4}\s*\.?\s*$")

    _IMG_BLOCK = re.compile(
        r"<!--\s*Start of picture text\s*-->.*?<!--\s*End of picture text\s*-->",
        re.IGNORECASE | re.DOTALL,
    )

    _INDICADORES_POSTALES = {
        "jr.",
        "jiron",
        "av.",
        "avenida",
        "cra.",
        "carrera",
        "cl.",
        "calle",
        "urb.",
        "urbanizacion",
        "urbanización",
        "piso",
        "of.",
        "oficina",
        "departamento",
        "interior",
        "int.",
        "mz.",
        "manzana",
        "lote",
        "lt.",
        "km.",
        "kilometro",
        "kilómetro",
        "n°",
        "nro.",
        "nro",
        "numero",
        "número",
        "dirección",
        "direccion",
        "dir.",
        "direc.",
    }

    _INSTITUCION_PALABRAS = {
        "universidad",
        "instituto",
        "departamento",
        "facultad",
        "escuela",
        "centro",
        "programa",
        "grupo",
        "investigación",
        "investigacion",
        "corporación",
        "corporacion",
        "fundación",
        "fundacion",
        "asociación",
        "asociacion",
        "convención",
        "convencion",
    }

    _HEADERS_AUTORIA = {
        "autores",
        "autor",
        "autoras",
        "autora",
        "investigadores",
        "investigadoras",
        "equipo",
        "consejo directivo",
        "directores",
        "directora",
        "director",
        "participantes",
        "elaborado por",
        "preparado por",
        "coordinadores",
        "coordinadoras",
        "coordinador",
        "facilitadores",
        "facilitador",
        "facilitadoras",
        "facilitadora",
        "diseño y diagramacion",
        "diseño y diagramación",
        "diagramacion",
        "diagramación",
        "nota aclaratoria",
        "publicado por",
        "editado por",
        "copyright",
        "creditos",
        "créditos",
        "fotografia",
        "fotografía",
        "foto",
        "elaboracion",
        "elaboración",
        "preparacion",
        "preparación",
        "revision tecnica",
        "revisión técnica",
        "revisado por",
        "revisor",
        "revisora",
        "revisores",
        "asesor",
        "asesora",
        "asesores",
        "asesoras",
    }

    _TITULOS_ESTRUCTURALES = {
        "introducción",
        "introduccion",
        "resumen",
        "abstract",
        "conclusiones",
        "conclusión",
        "conclusion",
        "referencias",
        "bibliografía",
        "bibliografia",
        "índice",
        "indice",
        "contenido",
        "tabla de contenido",
        "anexo",
        "annex",
        "anexos",
        "resumen ejecutivo",
        "marco teórico",
        "marco teorico",
        "metodología",
        "metodologia",
        "resultados",
        "discusión",
        "discusion",
        "agradecimientos",
        "glosario",
        "siglas",
        "abreviaturas",
        "objetivos",
        "objetivo general",
        "objetivos específicos",
        "objetivos especificos",
        "antecedentes",
        "justificación",
        "justificacion",
        "hipótesis",
        "hipotesis",
        "preguntas de investigación",
        "preguntas de investigacion",
        "limitaciones",
        "alcance",
        "marco legal",
        "marco conceptual",
    }

    _PREFIJOS_EDITORIAL = (
        "titulo:",
        "título:",
        "publicado por",
        "editado por",
        "nota aclaratoria",
        "esta permitida la reproduccion",
        "está permitida la reproducción",
        "todos los derechos reservados",
    )

    _COPYRIGHT_PATTERN = re.compile(r"©")
    _INDICE_PATTERN = re.compile(
        r"^\s*\|+.*[IVXivx0-9]+[\.:\|].*\d+\s*\|*\s*$",
        re.IGNORECASE,
    )
    _LEGAL_PATTERN = re.compile(
        r"reproduccion|reproducción|derechos reservados|prohibida la reproduccion|prohibida la reproducción",
        re.IGNORECASE,
    )
    _FOTO_CREDITO_PATTERN = re.compile(r"©\s*.+\s*/\s*", re.IGNORECASE)
    _ANEXO_PATTERN = re.compile(r"^(anexo|annex)\s+[IVXivx0-9]+", re.IGNORECASE)

    _SECCION_PREFIX = re.compile(
        r"^(?:[IVX]{2,5}\.|\d+(?:\.\d+)*\s*[\.\)\-]|[a-zA-Z]\)\s+)",
        re.MULTILINE,
    )
    _ITEM_SOLO = re.compile(r"^\s*(?:\d+[\.\)]|[a-zA-Z][\.\)]|[-•◦○▪►])\s*$")

    # --- Métodos de utilidad ---

    @staticmethod
    def _contar_lineas_palabras(texto: str) -> tuple[int, int]:
        lineas = texto.split("\n") if texto else []
        palabras = len(texto.split()) if texto else 0
        return len(lineas), palabras

    @staticmethod
    def _log_paso(nombre: str, antes: str, despues: str) -> None:
        lineas_antes, palabras_antes = CleaningService._contar_lineas_palabras(antes)
        lineas_despues, palabras_despues = CleaningService._contar_lineas_palabras(
            despues
        )
        logger.info(
            "Paso '%s': lineas %d -> %d, palabras %d -> %d",
            nombre,
            lineas_antes,
            lineas_despues,
            palabras_antes,
            palabras_despues,
        )

    @staticmethod
    def _eliminar_tablas(texto: str) -> str:
        lineas = texto.split("\n")
        resultado: list[str] = []
        en_tabla = False

        for ln in lineas:
            es_linea_tabla = "|" in ln
            if es_linea_tabla:
                en_tabla = True
                continue
            if en_tabla:
                if ln.strip() == "":
                    continue
                en_tabla = False
            resultado.append(ln)

        return "\n".join(resultado)

    @staticmethod
    def _markdown_a_texto(texto_md: str) -> str:
        md = MarkdownIt("commonmark")
        html = md.render(texto_md)
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text()

    @staticmethod
    def _limpiar_placeholders_imagenes(texto: str) -> str:
        return CleaningService._IMG_BLOCK.sub("", texto)

    @staticmethod
    def _limpiar_contacto(texto: str) -> str:
        texto = CleaningService._EMAIL_PATTERN.sub(" ", texto)
        texto = CleaningService._URL_PATTERN.sub(" ", texto)
        texto = CleaningService._PHONE_PATTERN.sub(" ", texto)
        return texto

    @staticmethod
    def _tiene_numero(linea: str) -> bool:
        return any(ch.isdigit() for ch in linea)

    @staticmethod
    def _empieza_con_indicador_postal(linea: str) -> bool:
        inicio = linea.lower().strip()
        return any(
            inicio.startswith(ind) for ind in CleaningService._INDICADORES_POSTALES
        )

    @staticmethod
    def _es_direccion(linea: str) -> bool:
        tokens = linea.lower().replace(",", " ").replace(".", " ").split()
        if not tokens:
            return False
        palabras = set(tokens)
        indicadores = palabras & CleaningService._INDICADORES_POSTALES
        indicadores_sin_punto = {
            t for t in tokens if t + "." in CleaningService._INDICADORES_POSTALES
        }
        indicadores = indicadores | indicadores_sin_punto
        if not indicadores:
            return False
        tiene_numero = CleaningService._tiene_numero(linea)
        address_words = set(indicadores)
        for t in tokens:
            if t.isdigit():
                address_words.add(t)
        address_ratio = len(address_words) / len(tokens)
        empieza_con_postal = CleaningService._empieza_con_indicador_postal(linea)
        if len(indicadores) >= 2 and address_ratio >= 0.5:
            return True
        if (
            len(indicadores) >= 1
            and tiene_numero
            and (address_ratio >= 0.5 or empieza_con_postal)
        ):
            return True
        return False

    @staticmethod
    def _es_lista_nombres(linea: str) -> bool:
        palabras = re.findall(r"\b\w+\b", linea)
        if len(palabras) < 3:
            return False
        capitalizadas = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\b", linea)
        return len(capitalizadas) >= 3 and len(capitalizadas) / len(palabras) >= 0.5

    @staticmethod
    def _es_titulo_estructural(linea: str) -> bool:
        clave = linea.strip().rstrip(":").lower()
        if clave in CleaningService._TITULOS_ESTRUCTURALES:
            return True
        return any(
            clave.startswith(t + " ") or clave.startswith(t + ":")
            for t in CleaningService._TITULOS_ESTRUCTURALES
        )

    @staticmethod
    def _es_linea_autoria(linea: str, linea_anterior: str) -> bool:
        linea_lower = linea.lower()
        anterior_lower = linea_anterior.lower()
        if CleaningService._COPYRIGHT_PATTERN.search(linea):
            return True
        if len(CleaningService._EMAIL_PATTERN.findall(linea)) >= 2:
            return True
        palabras = set(re.findall(r"\b\w+\b", linea_lower))
        instituciones = palabras & CleaningService._INSTITUCION_PALABRAS
        if len(instituciones) >= 2:
            return True
        if any(header in anterior_lower for header in CleaningService._HEADERS_AUTORIA):
            if CleaningService._es_lista_nombres(linea):
                return True
        return False

    @staticmethod
    def _es_header_autoria(linea: str) -> bool:
        linea_limpia = linea.lower().strip().rstrip(":")
        if linea_limpia in CleaningService._HEADERS_AUTORIA:
            return True
        return any(
            linea_limpia.startswith(header + " ")
            or linea_limpia.startswith(header + ":")
            for header in CleaningService._HEADERS_AUTORIA
        )

    @staticmethod
    def _es_anexo(linea: str) -> bool:
        return bool(CleaningService._ANEXO_PATTERN.match(linea.strip()))

    @staticmethod
    def _limpiar_numeracion(texto: str) -> str:
        lineas = texto.split("\n")
        resultado: list[str] = []
        for ln in lineas:
            clave = ln.strip()
            if not clave:
                resultado.append(ln)
                continue
            if CleaningService._ITEM_SOLO.match(clave):
                continue
            limpia = CleaningService._SECCION_PREFIX.sub("", ln)
            resultado.append(limpia)
        return "\n".join(resultado)

    @staticmethod
    def _es_linea_mayusculas(linea: str) -> bool:
        letras = re.sub(r"[^a-zA-ZÁÉÍÓÚÑáéíóúñ]", "", linea)
        return bool(letras) and letras == letras.upper()

    @staticmethod
    def _eliminar_headers_footers_y_numeros(
        texto: str, min_repeticiones: int = 3
    ) -> str:
        lineas = texto.split("\n")
        conteo_cortos: dict[str, int] = {}
        conteo_mayusculas: dict[str, int] = {}
        for ln in lineas:
            clave = ln.strip().lower()
            if not clave:
                continue
            if len(clave.split()) <= 5 and not clave.endswith("."):
                conteo_cortos[clave] = conteo_cortos.get(clave, 0) + 1
            if CleaningService._es_linea_mayusculas(ln.strip()):
                conteo_mayusculas[clave] = conteo_mayusculas.get(clave, 0) + 1

        recurrentes_cortos = {
            k for k, c in conteo_cortos.items() if c >= min_repeticiones
        }
        recurrentes_mayusculas = {
            k for k, c in conteo_mayusculas.items() if c >= min_repeticiones
        }

        resultado: list[str] = []
        vistos_cortos: set[str] = set()
        vistos_mayusculas: set[str] = set()
        for ln in lineas:
            clave = ln.strip().lower()
            if CleaningService._SOLO_NUMERO.match(clave):
                continue
            if clave in recurrentes_cortos:
                if clave in vistos_cortos:
                    continue
                vistos_cortos.add(clave)
            if clave in recurrentes_mayusculas:
                if clave in vistos_mayusculas:
                    continue
                vistos_mayusculas.add(clave)
            if recurrentes_mayusculas:
                clave_sin_prefijo = re.sub(r"^\d+\s+", "", clave)
                if (
                    clave_sin_prefijo in recurrentes_mayusculas
                    and clave_sin_prefijo in vistos_mayusculas
                ):
                    continue
            resultado.append(ln)

        return "\n".join(resultado)

    @staticmethod
    def _es_prefijo_editorial(linea: str) -> bool:
        linea_lower = linea.lower().strip()
        return any(
            linea_lower.startswith(prefijo)
            for prefijo in CleaningService._PREFIJOS_EDITORIAL
        )

    @staticmethod
    def _es_linea_legal(linea: str) -> bool:
        return bool(CleaningService._LEGAL_PATTERN.search(linea))

    @staticmethod
    def _es_indice(linea: str) -> bool:
        return bool(CleaningService._INDICE_PATTERN.match(linea))

    @staticmethod
    def _es_credito_foto(linea: str) -> bool:
        return bool(CleaningService._FOTO_CREDITO_PATTERN.search(linea))

    @staticmethod
    def _eliminar_lineas_ruido(texto: str) -> str:
        lineas = texto.split("\n")
        resultado: list[str] = []
        anterior = ""
        anterior_fue_autoria = False

        for ln in lineas:
            clave = ln.strip()
            if not clave:
                resultado.append(ln)
                anterior = ""
                continue
            if CleaningService._SOLO_NUMERO.match(clave):
                anterior = clave
                anterior_fue_autoria = False
                continue
            if CleaningService._es_titulo_estructural(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue
            if CleaningService._es_header_autoria(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue
            if CleaningService._es_anexo(clave):
                anterior = clave
                anterior_fue_autoria = False
                continue
            if CleaningService._es_prefijo_editorial(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue
            if CleaningService._es_linea_legal(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue
            if CleaningService._es_indice(clave):
                anterior = clave
                anterior_fue_autoria = False
                continue
            if CleaningService._es_credito_foto(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue
            if CleaningService._es_linea_autoria(clave, anterior):
                anterior = clave
                anterior_fue_autoria = True
                continue
            if anterior_fue_autoria and CleaningService._es_lista_nombres(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue
            if CleaningService._es_direccion(clave):
                anterior = clave
                anterior_fue_autoria = False
                continue
            palabras = clave.split()
            if len(palabras) < 4 and not clave.endswith("."):
                anterior = clave
                anterior_fue_autoria = False
                continue
            resultado.append(ln)
            anterior = clave
            anterior_fue_autoria = False

        return "\n".join(resultado)

    @staticmethod
    def _deduplicar_parrafos(texto: str) -> str:
        parrafos = texto.split("\n\n")
        resultado: list[str] = []
        anterior_normalizado: str | None = None

        for p in parrafos:
            p_strip = p.strip()
            if not p_strip:
                continue
            normalizado = " ".join(p_strip.lower().split())
            if normalizado == anterior_normalizado:
                continue
            resultado.append(p_strip)
            anterior_normalizado = normalizado

        return "\n\n".join(resultado)

    @staticmethod
    def _normalizar_espacios(texto: str) -> str:
        texto = CleaningService._MULTISPACE.sub("\n\n", texto)
        texto = CleaningService._SPACES.sub(" ", texto)
        return texto.strip()

    # --- API pública: limpieza estructural ---

    @staticmethod
    def structuralCleaning(texto_md: str) -> str:
        """Limpieza estructural: convierte MD a texto plano y quita ruido común."""
        logger.info("Iniciando limpieza estructural")

        texto = fix_text(texto_md)
        CleaningService._log_paso("fix_text", texto_md, texto)

        texto = CleaningService._limpiar_placeholders_imagenes(texto)
        CleaningService._log_paso("limpiar_placeholders_imagenes", texto_md, texto)

        texto = CleaningService._eliminar_headers_footers_y_numeros(texto)
        CleaningService._log_paso("eliminar_headers_footers_y_numeros", texto_md, texto)

        texto = CleaningService._eliminar_tablas(texto)
        CleaningService._log_paso("eliminar_tablas", texto_md, texto)

        texto = CleaningService._markdown_a_texto(texto)
        CleaningService._log_paso("markdown_a_texto", texto_md, texto)

        texto = CleaningService._limpiar_contacto(texto)
        CleaningService._log_paso("limpiar_contacto", texto_md, texto)

        texto = CleaningService._eliminar_lineas_ruido(texto)
        CleaningService._log_paso("eliminar_lineas_ruido", texto_md, texto)

        texto = CleaningService._limpiar_numeracion(texto)
        CleaningService._log_paso("limpiar_numeracion", texto_md, texto)

        texto = CleaningService._deduplicar_parrafos(texto)
        CleaningService._log_paso("deduplicar_parrafos", texto_md, texto)

        texto = CleaningService._normalizar_espacios(texto)
        CleaningService._log_paso("normalizar_espacios", texto_md, texto)

        logger.info("Limpieza estructural finalizada")
        return texto

    # --- API pública: limpieza lingüística con Anthropic ---

    @staticmethod
    def _partir_por_parrafos(texto: str, max_chars: int) -> list[str]:
        """Divide texto en chunks por párrafos que quepan en max_chars."""
        parrafos = [p for p in texto.split("\n\n") if p.strip()]
        if not parrafos:
            return []
        if len(texto) <= max_chars:
            return [texto]

        chunks: list[str] = []
        chunk_actual: list[str] = []
        chars_actual = 0

        for p in parrafos:
            p_len = len(p) + 2
            if chars_actual + p_len > max_chars and chunk_actual:
                chunks.append("\n\n".join(chunk_actual))
                chunk_actual = []
                chars_actual = 0
            chunk_actual.append(p)
            chars_actual += p_len

        if chunk_actual:
            chunks.append("\n\n".join(chunk_actual))

        return chunks

    @staticmethod
    def linguisticCleaning(texto: str) -> str:
        """
        Limpieza lingüística con Anthropic Claude.
        - Elimina referencias bibliográficas
        - Elimina citas entre paréntesis
        - Elimina notas al pie
        - Conserva párrafos
        """
        logger.info("Iniciando limpieza lingüística con Anthropic")

        if not texto or not texto.strip():
            return ""

        max_chunk = getattr(settings, "NER_MAX_CHUNK_LEN", 48000)
        chunks = CleaningService._partir_por_parrafos(texto, max_chunk)

        if len(chunks) > 1:
            logger.info(
                "Texto dividido en %d chunks para limpieza lingüística", len(chunks)
            )

        client = get_anthropic_client()
        partes_limpias: list[str] = []

        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                logger.info(
                    "Limpiando chunk %d/%d (%d caracteres)",
                    i + 1,
                    len(chunks),
                    len(chunk),
                )

            response = client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=8192,
                system=LIMPIEZA_LINGUISTICA_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": chunk}],
            )

            parte_limpia = response.content[0].text if response.content else ""
            if parte_limpia:
                partes_limpias.append(parte_limpia)

        resultado = "\n\n".join(partes_limpias) if partes_limpias else texto
        CleaningService._log_paso("limpieza_linguistica_anthropic", texto, resultado)

        logger.info("Limpieza lingüística finalizada")
        return resultado
