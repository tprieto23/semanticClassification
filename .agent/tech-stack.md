# Tech Stack

## Lenguajes

- **Python 3.x** - Lenguaje principal

## Frameworks y librerías

### API
- **FastAPI** - Framework para API
- **OpenAPI/Swagger** - Documentación automática

### Base de datos
- **PostgreSQL** - Base de datos principal
- **pgvector** - Extensión para vectores
- **SQLAlchemy** - ORM
- **Alembic** - Migraciones de DB

### Procesamiento
- **Conversión PDF:** PyMuPDF (`fitz`) — rápido, robusto con layouts complejos
- **Conversión DOCX:** python-docx — estándar para .docx
- **Conversión imágenes/OCR:** TBD (sugerido: pytesseract con `tesseract-ocr-spa`) — diferido a 2da iteración
- **Conversión audio:** TBD (sugerido: faster-whisper) — diferido a 2da iteración
- **Conversión video:** TBD (sugerido: ffmpeg-python + faster-whisper) — diferido a 2da iteración
- **Limpieza:** ftfy (encoding) + `unicodedata` (NFC) + `re` (stdlib) — enfoque determinista por capas. Capas 1-4 implementadas.
- **NER/Extracción de entidades (ANTERIOR):** spaCy (`es_core_news_sm`, `en_core_web_sm`) + langdetect + reglas deterministas en `entity_classifier.py` — **DEPRECADO** por alta tasa de error.
- **NER/Extracción de entidades (NUEVO):** XLM-RoBERTa (`xlm-roberta-base`) fine-tuned para Token Classification. Un solo modelo multilingüe (es+en), sin `langdetect`. Fase 3 en progreso.
- **Clasificación de entidades:** El modelo XLM-R predice directamente las 9 categorías del proyecto (BIO tagging). Ya no se usan reglas deterministas ni keywords.
- **Embeddings:** TBD (sentence-transformers, OpenAI, etc.)
- **Grafos:** TBD (networkx, igraph)

### Contenerización
- **Docker** - Contenedores
- **docker-compose** - Orquestación local

## Herramientas

- **Git** - Control de versiones
- **OpenAPI** - Documentación de API

## Versiones

| Herramienta | Versión |
|-------------|---------|
| Python | 3.11 |
| PostgreSQL | 16 |
| pgvector | 0.2.4 |
| FastAPI | 0.109.0 |
| SQLAlchemy | 2.0.25 |
| Alembic | 1.13.1 |
| Uvicorn | 0.27.0 |
| Pydantic | 2.5.3 |
| PyMuPDF | 1.24.0 |
| python-docx | 1.1.0 |
| ftfy | 6.2.3 |
| spacy | >=3.7.0 |
| langdetect | 1.0.9 |
| torch | 2.11.0 |
| transformers | 5.8.0 |
| datasets | 4.8.5 |
| seqeval | 1.2.2 |
| evaluate | 0.4.6 |
| accelerate | 1.13.0 |

## TBD (Por definir)

- Modelo de embeddings
- Librería de grafos
- Librerías de conversión OCR/audio/video (diferidas a 2da iteración)
- Librerías de limpieza de texto
- Versiones específicas
