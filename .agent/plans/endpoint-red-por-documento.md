# Plan — Endpoint de red por documento (por id)

## Objetivo

Igual que el endpoint de corpus, pero para **un solo documento**. Útil para
inspeccionar o depurar un texto puntual. Es el equivalente-endpoint de lo que hoy
se corre a mano por CLI con `--ner-json`.

## Ruta

```
POST /documents/{id}/network
```

Mismos query params: `minimum_weight`, `include_isolates`.

## Flujo

Idéntico al de corpus (ver `endpoint-red-corpus.md`), con tres diferencias:

1. **Validar documento:** existe y `status = 'fuzzyMatching'`; si no, 404/409,
   coherente con el resto de `DocumentService`.
2. **Menciones:** usar `load_db_mentions(document_id)` — la función que **ya existe**
   (filtra por un documento). No hay que tocar nada del build.
3. **Guardar** en `s3/archivosRed/{document_id}/`.
4. `coverage = { documents_included: 1, documents_total: 1 }`.

## Diseño clave: un solo servicio con "scope"

`src/services/network.py` recibe un **scope** y arma la lista de `MentionRecord`
en consecuencia:

| scope | menciones |
|---|---|
| `corpus` | todas las de documentos en `fuzzyMatching` |
| `incubadora N` | idem, filtradas por `incubator_number` |
| `document_id` | `load_db_mentions(document_id)` |

De ahí en adelante (build → export → visualize) el pipeline es **idéntico**. Los
dos endpoints comparten ~95% del código. No agregar lógica nueva salvo el filtro
de alcance y la validación del documento.

## Reutiliza

Todo el build/export/visualize del plan de corpus. Este endpoint es, en la práctica,
el mismo servicio invocado con `scope = document_id`.

## Prioridad

Secundario / "por si lo necesito". Conviene construir el servicio de corpus primero
con el scope ya parametrizado, y este endpoint queda casi gratis.
