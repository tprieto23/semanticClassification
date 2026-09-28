# Clasificación documental durante la ingesta

**Fecha:** 28 Sep 2026

## Decisión

Las cargas individuales y por lote incorporan tres atributos opcionales:

- `year`: entero de cuatro dígitos entre 1000 y 9999;
- `productive_sector`: vocabulario controlado, inicialmente `Agroforestry`;
- `document_type`: `academic`, `technical_report`, `project_report`,
  `policy_document`, `manual_or_guide`, `institutional_document` u `other`.

Se eligió `document_type` en lugar de `class` para expresar claramente el
significado del atributo y evitar el término reservado de Python. En una carga
por lote, los tres valores son comunes para todos los archivos de la petición.
Si todavía no se conocen, se guardan como `NULL`.

## Implementación y compatibilidad

La migración `a4b5c6d7e8f9` añade los campos a `documents`, sus restricciones e
índices para año y tipo documental. Las columnas aceptan `NULL` para permitir
enriquecimiento posterior y conservar los documentos históricos.

`PATCH /documents/{document_id}/classification` recibe `form-data` con uno o
más de los tres campos. Solo cambia los valores enviados y no modifica el estado
ni los artefactos ya generados.

La colección `postman_collection.json` incluye los campos en las solicitudes
individual y batch. El encabezado multipart no se fija manualmente, de modo que
Postman pueda generar el boundary correcto.

## Verificación

- 9 pruebas de ingesta y actualización con `unittest`: correctas.
- Validación JSON de la colección de Postman: correcta.
- Migración aplicada en PostgreSQL.
- Contrato de carga: solo archivo e incubadora son obligatorios; la clasificación
  puede completarse después.
- La API respondió `{"status":"ok"}` al cierre de la sesión.
- Se verificó que un POST con solo `incubator_number` únicamente reclama el
  archivo faltante; no reclama año, sector ni tipo documental.
- Se verificó que el PATCH interpreta correctamente `form-data` usando un UUID
  inexistente, sin modificar documentos reales.

## Punto de control para retomar

La implementación está terminada y lista para uso manual. No hay que ejecutar
otra migración antes de cargar archivos.

### Próximo paso exacto

1. En Postman usar `POST {{apiUrl}}/documents`, sin query parameters.
2. Seleccionar **Body → form-data**.
3. Enviar `file` como tipo **File** e `incubator_number` como **Text**.
4. Añadir `language` si se conoce.
5. Para cualquier clasificación desconocida, desmarcar la fila en lugar de
   enviar una cadena vacía.
6. Enviar la petición, esperar `201 Created` y copiar el `id` de la respuesta.
7. Revisar conjuntamente la primera respuesta antes de continuar con el lote.

Para enriquecer un documento ya cargado:

```text
PATCH {{apiUrl}}/documents/{{document_id}}/classification
Body → form-data
year=2021
productive_sector=Agroforestry
document_type=technical_report
```

Se puede enviar solo uno de esos campos. Los no enviados conservan su valor y
el documento no repite conversión, limpieza ni NER.

### Observación de Postman

La captura compartida mostraba `incubator_number` repetido en la URL. Debe
retirarse: la URL termina en `/documents` y la incubadora vive únicamente en el
cuerpo `form-data`. La colección vigente está en `postman_collection.json` y
puede reimportarse para obtener la petición PATCH preparada.
