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
- **Limpieza:** TBD
- **Clasificación:** TBD
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

## TBD (Por definir)

- Modelo de embeddings
- Librería de grafos
- Librerías de conversión OCR/audio/video (diferidas a 2da iteración)
- Librerías de limpieza de texto
- Versiones específicas
