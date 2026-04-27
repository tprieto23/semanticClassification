# Conventions

## Estilo de código

- **Python:** PEP 8
- **Type hints:** TBD
- **Formato:** TBD (Black, ruff?)

## Naming

### Archivos y carpetas
- **Carpetas:** `snake_case`
- **Archivos:** `snake_case.py`
- **Documentos en raw:** mantener nombre original

### Código
- **Variables:** `snake_case`
- **Clases:** `PascalCase`
- **Constantes:** `UPPER_CASE`
- **Funciones:** `snake_case`

### Base de datos
- **Tablas:** `snake_case` (plural)
- **Columnas:** `snake_case`
- **IDs:** `id` (primary key), `{tabla}_id` (foreign key)

## Estructura de archivos

```
src/
├── api/            # Endpoints de FastAPI
├── core/           # Lógica de negocio
├── models/         # Modelos SQLAlchemy
├── services/       # Servicios de procesamiento
└── utils/          # Funciones utilitarias
```

## Buenas prácticas

- **Documentación:** Todo cambio importante va a `.agent/`
- **Migraciones:** Cada cambio en DB tiene su migration en Alembic
- **Tests:** TBD
- **Logging:** TBD
- **Errores:** TBD

## TBD (Por definir)

- Linter/formatter específico
- Convenciones de commits
- Estructura de tests
- Logging y manejo de errores
- Variables de entorno (.env)
