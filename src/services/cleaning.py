import re

from bs4 import BeautifulSoup
from ftfy import fix_text
from markdown_it import MarkdownIt


class CleaningService:

    _URL_PATTERN = re.compile(r"https?://\S+|ftp://\S+|www\.\S+")
    _EMAIL_PATTERN = re.compile(r"[\w.\-]+@[\w.\-]+\.\w{2,}")
    _PHONE_PATTERN = re.compile(
        r"\+?\d{1,4}?[\s.\-]?(?:\(?\d{1,4}?\)?)[\s.\-]?\d{1,4}[\s.\-]?\d{1,4}[\s.\-]?\d{1,9}"
    )
    _MULTISPACE = re.compile(r"\n{3,}")
    _SPACES = re.compile(r"[ \t]+")
    _SOLO_NUMERO = re.compile(r"^\s*\d{1,4}\s*\.?\s*$")

    # Bloque de placeholder que pymupdf4llm inserta alrededor de imágenes.
    _IMG_BLOCK = re.compile(
        r"<!--\s*Start of picture text\s*-->.*?<!--\s*End of picture text\s*-->",
        re.IGNORECASE | re.DOTALL,
    )

    # Palabras clave que indican dirección postal o ubicación institucional.
    _DIRECCION_PALABRAS = {
        "jr.", "jiron", "av.", "avenida", "cra.", "carrera", "cl.", "calle",
        "urb.", "urbanizacion", "urbanización", "n°", "nro.", "no.", "numero",
        "número", "piso", "of.", "oficina", "magdalena", "lima", "bogotá",
        "bogota", "medellín", "medellin", "cali", "perú", "peru", "colombia",
    }

    # Palabras clave que indican instituciones académicas o de investigación.
    _INSTITUCION_PALABRAS = {
        "universidad", "instituto", "departamento", "facultad", "escuela",
        "centro", "programa", "grupo", "investigación", "investigacion",
        "corporación", "corporacion", "fundación", "fundacion", "asociación",
        "asociacion", "convención", "convencion",
    }

    # Headers que introducen listas de autores, directores o participantes.
    _HEADERS_AUTORIA = {
        "autores", "autor", "autoras", "autora", "investigadores",
        "investigadoras", "equipo", "consejo directivo", "directores",
        "directora", "director", "participantes", "elaborado por",
        "preparado por", "coordinadores", "coordinadoras", "coordinador",
        "facilitadores", "facilitador", "facilitadoras", "facilitadora",
        "diseño y diagramacion", "diseño y diagramación", "diagramacion",
        "diagramación", "nota aclaratoria", "publicado por", "editado por",
        "copyright", "creditos", "créditos", "fotografia", "fotografía",
        "foto", "elaboracion", "elaboración", "preparacion", "preparación",
        "revision tecnica", "revisión técnica", "revisado por", "revisor",
        "revisora", "revisores", "asesor", "asesora", "asesores", "asesoras",
    }

    # Prefijos editoriales que identifican metadata de publicación.
    _PREFIJOS_EDITORIAL = (
        "titulo:", "título:", "publicado por", "editado por",
        "nota aclaratoria", "esta permitida la reproduccion",
        "está permitida la reproducción", "todos los derechos reservados",
    )

    # Patrones de metadata editorial/copyright.
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

    # Headers de anexos (generalmente tablas al final del documento).
    _ANEXO_PATTERN = re.compile(r"^(anexo|annex)\s+[IVXivx0-9]+", re.IGNORECASE)

    # Prefijos de numeración de secciones, subsecciones e items.
    _SECCION_PREFIX = re.compile(
        r"^(?:[IVXÁÉÍÓÚÑA-Z]+|\d+)(?:\.\d+)*\s*[\.\)\-]\s+",
        re.MULTILINE,
    )

    # Línea que solo contiene un item (viñeta o numeración).
    _ITEM_SOLO = re.compile(r"^\s*(?:\d+[\.\)]|[a-zA-Z][\.\)]|[-•◦○▪►])\s*$")

    @staticmethod
    def _eliminar_tablas(texto: str) -> str:
        """Elimina bloques de líneas consecutivas que contengan tablas Markdown (|)."""
        lineas = texto.split("\n")
        resultado: list[str] = []
        en_tabla = False

        for ln in lineas:
            es_linea_tabla = "|" in ln
            if es_linea_tabla:
                en_tabla = True
                continue
            if en_tabla:
                # Una línea vacía después de la tabla se salta también para no dejar huecos.
                if ln.strip() == "":
                    continue
                en_tabla = False
            resultado.append(ln)

        return "\n".join(resultado)

    @staticmethod
    def _markdown_a_texto(texto_md: str) -> str:
        """Convierte Markdown a texto plano."""
        md = MarkdownIt("commonmark")
        html = md.render(texto_md)
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text()

    @staticmethod
    def _limpiar_placeholders_imagenes(texto: str) -> str:
        """Elimina bloques <!-- Start/End of picture text --> con su contenido."""
        return CleaningService._IMG_BLOCK.sub("", texto)

    @staticmethod
    def _limpiar_contacto(texto: str) -> str:
        """Elimina URLs, emails y teléfonos."""
        texto = CleaningService._URL_PATTERN.sub(" ", texto)
        texto = CleaningService._EMAIL_PATTERN.sub(" ", texto)
        texto = CleaningService._PHONE_PATTERN.sub(" ", texto)
        return texto

    @staticmethod
    def _es_direccion(linea: str) -> bool:
        """Detecta si una línea parece una dirección postal."""
        palabras = set(linea.lower().replace(",", " ").replace(".", " ").split())
        return len(palabras & CleaningService._DIRECCION_PALABRAS) >= 2

    @staticmethod
    def _es_lista_nombres(linea: str) -> bool:
        """Detecta si una línea es principalmente una lista de nombres propios."""
        palabras = re.findall(r"\b\w+\b", linea)
        if len(palabras) < 3:
            return False
        capitalizadas = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\b", linea)
        # Si la mitad o más de las palabras son nombres propios, es una lista de nombres.
        return len(capitalizadas) >= 3 and len(capitalizadas) / len(palabras) >= 0.5

    @staticmethod
    def _es_linea_autoria(linea: str, linea_anterior: str) -> bool:
        """Detecta líneas que son listas de autores/participantes o instituciones."""
        linea_lower = linea.lower()
        anterior_lower = linea_anterior.lower()

        # Copyright o símbolo © → metadata de autoría.
        if CleaningService._COPYRIGHT_PATTERN.search(linea):
            return True

        # Dos o más emails en la misma línea → casi siempre metadata de autores.
        if len(CleaningService._EMAIL_PATTERN.findall(linea)) >= 2:
            return True

        # Múltiples instituciones en la misma línea.
        palabras = set(re.findall(r"\b\w+\b", linea_lower))
        instituciones = palabras & CleaningService._INSTITUCION_PALABRAS
        if len(instituciones) >= 2:
            return True

        # La línea anterior era un header de autoria y esta línea parece una lista.
        if any(header in anterior_lower for header in CleaningService._HEADERS_AUTORIA):
            # Si la línea es una lista de nombres, es metadata.
            if CleaningService._es_lista_nombres(linea):
                return True

        return False

    @staticmethod
    def _es_header_autoria(linea: str) -> bool:
        """Detecta headers tipo 'Autores:', 'Consejo directivo:', etc."""
        linea_limpia = linea.lower().strip().rstrip(":")
        if linea_limpia in CleaningService._HEADERS_AUTORIA:
            return True
        # También detecta cuando el header aparece al inicio de una línea más larga.
        return any(
            linea_limpia.startswith(header + " ") or linea_limpia.startswith(header + ":")
            for header in CleaningService._HEADERS_AUTORIA
        )

    @staticmethod
    def _es_anexo(linea: str) -> bool:
        """Detecta headers de anexos."""
        return bool(CleaningService._ANEXO_PATTERN.match(linea.strip()))

    @staticmethod
    def _limpiar_numeracion(texto: str) -> str:
        """Elimina prefijos de numeración de secciones, subsecciones e items."""
        lineas = texto.split("\n")
        resultado: list[str] = []

        for ln in lineas:
            clave = ln.strip()

            # Línea vacía → conservar.
            if not clave:
                resultado.append(ln)
                continue

            # Línea que solo es un item → descartar.
            if CleaningService._ITEM_SOLO.match(clave):
                continue

            # Quitar prefijo de numeración al inicio.
            limpia = CleaningService._SECCION_PREFIX.sub("", ln)
            resultado.append(limpia)

        return "\n".join(resultado)

    @staticmethod
    def _eliminar_lineas_repetidas(texto: str, min_repeticiones: int = 3) -> str:
        """Elimina headers/footers recurrentes y números de página."""
        lineas = texto.split("\n")

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
    def _es_prefijo_editorial(linea: str) -> bool:
        """Detecta líneas que empiezan con metadata editorial (título, publicado, etc.)."""
        linea_lower = linea.lower().strip()
        return any(linea_lower.startswith(prefijo) for prefijo in CleaningService._PREFIJOS_EDITORIAL)

    @staticmethod
    def _es_linea_legal(linea: str) -> bool:
        """Detecta notas legales de reproducción o derechos reservados."""
        return bool(CleaningService._LEGAL_PATTERN.search(linea))

    @staticmethod
    def _es_indice(linea: str) -> bool:
        """Detecta líneas de índice o tabla de contenido."""
        return bool(CleaningService._INDICE_PATTERN.match(linea))

    @staticmethod
    def _es_credito_foto(linea: str) -> bool:
        """Detecta créditos de fotografía tipo '© Nombre / WWF - Perú'."""
        return bool(CleaningService._FOTO_CREDITO_PATTERN.search(linea))

    @staticmethod
    def _eliminar_lineas_ruido(texto: str) -> str:
        """Elimina direcciones, metadata de autoria y líneas muy cortas."""
        lineas = texto.split("\n")
        resultado: list[str] = []
        anterior = ""
        anterior_fue_autoria = False

        for ln in lineas:
            clave = ln.strip()

            # Línea vacía → conservar para mantener párrafos.
            # No reseteamos anterior_fue_autoria porque los bloques de autoria
            # suelen venir con saltos de línea entre nombres.
            if not clave:
                resultado.append(ln)
                anterior = ""
                continue

            # Número de página suelto.
            if CleaningService._SOLO_NUMERO.match(clave):
                anterior = clave
                anterior_fue_autoria = False
                continue

            # Header de autoria → descartar, pero marcar la anterior para la siguiente línea.
            if CleaningService._es_header_autoria(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue

            # Header de anexo → descartar.
            if CleaningService._es_anexo(clave):
                anterior = clave
                anterior_fue_autoria = False
                continue

            # Prefijos editoriales: Título:, Publicado por, Nota aclaratoria, etc.
            if CleaningService._es_prefijo_editorial(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue

            # Notas legales de reproducción/derechos.
            if CleaningService._es_linea_legal(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue

            # Líneas de índice o tabla de contenido.
            if CleaningService._es_indice(clave):
                anterior = clave
                anterior_fue_autoria = False
                continue

            # Créditos de fotografía.
            if CleaningService._es_credito_foto(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue

            # Línea de autoria (lista de nombres, emails, instituciones, copyright).
            if CleaningService._es_linea_autoria(clave, anterior):
                anterior = clave
                anterior_fue_autoria = True
                continue

            # Si la línea anterior fue autoria y esta es una lista de nombres, también es autoria.
            if anterior_fue_autoria and CleaningService._es_lista_nombres(clave):
                anterior = clave
                anterior_fue_autoria = True
                continue

            # Dirección postal.
            if CleaningService._es_direccion(clave):
                anterior = clave
                anterior_fue_autoria = False
                continue

            # Línea muy corta sin sentido completo (< 4 palabras).
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
        """Elimina párrafos consecutivos idénticos (ignorando espacios)."""
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
        """Normaliza espacios en blanco sin convertir a minúsculas."""
        texto = CleaningService._MULTISPACE.sub("\n\n", texto)
        texto = CleaningService._SPACES.sub(" ", texto)
        return texto.strip()

    @staticmethod
    def structuralCleaning(texto_md: str) -> str:
        """Limpieza estructural: convierte MD a texto plano y quita ruido común."""
        texto = fix_text(texto_md)
        texto = CleaningService._limpiar_placeholders_imagenes(texto)
        texto = CleaningService._eliminar_lineas_repetidas(texto)
        texto = CleaningService._eliminar_tablas(texto)
        texto = CleaningService._markdown_a_texto(texto)
        texto = CleaningService._limpiar_contacto(texto)
        texto = CleaningService._eliminar_lineas_ruido(texto)
        texto = CleaningService._limpiar_numeracion(texto)
        texto = CleaningService._deduplicar_parrafos(texto)
        texto = CleaningService._normalizar_espacios(texto)
        return texto

    @staticmethod
    def linguisticCleaning(texto: str) -> str:
        pass
