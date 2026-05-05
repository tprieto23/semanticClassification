# Technical Debt

## Deuda técnica conocida

### Pendientes de decisión

- [ ] **Objetivo 2:** Librerías específicas para conversión (PDF, Word, OCR, audio, video)
- [ ] **Objetivo 3:** Qué tipo de ruido eliminar, qué conservar, revisión humana
  - ✅ Pipeline de 4 capas + sub-reglas 4e/4f implementado y corpus re-procesado (avg 5.49% reducción)
  - ⚠️ Revisión humana parcial: 3/28 documentos validados a fondo; resto por revisar
  - ⚠️ Trade-off aceptado: headers largos repetidos (>10 palabras) ya no se eliminan
  - ⚠️ Líneas de contacto residuales menores (prefijos vacíos, direcciones parciales)
- [ ] **Objetivo 4:** Lista completa de entidades, categorías, clasificación
  - ✅ Fase 1 (NER genérico con spaCy) implementada
  - ✅ Fase 2 (mapeo a 9 categorías con reglas deterministas) implementada
  - ⏳ Fase 3 (modelo BERT/RoBERTa + extracción de NARRATIVA/PRÁCTICA) pendiente
  - ⏳ Revisión manual de ~150 entidades MISC_Spacy por documento
- [ ] **Objetivo 5:** Modelo de embeddings, dimensiones, normalización
- [ ] **Objetivo 6:** Definición de relación, pesos, tipos, matriz por documento o global
- [ ] **Objetivo 7:** Librería de grafos, dirigido/no dirigido, formatos
- [ ] **Objetivo 8:** Métricas específicas, globales o por nodo, historial

### Pendientes de implementación

- [ ] **Autenticación en API** - Por ahora no se necesita (local), pero será necesario para producción
- [ ] **Tests** - No definido framework ni estructura
- [ ] **Logging** - No definido estrategia
- [ ] **Manejo de errores** - No definido estándares
- [ ] **Variables de entorno** - No definido estructura de .env
- [ ] **Formato de código** - No definido linter/formatter (Black, ruff?)
- [ ] **Convenciones de commits** - No definido

### Workarounds temporales

<!-- Soluciones temporales que deben refactorizarse -->
- **Capa 2b — Regla de >10 palabras:** workaround para evitar que oraciones narrativas en brochures/dípticos sean eliminadas como headers. Los headers reales con >10 palabras ya no se eliminan (trade-off aceptado). Una solución más elegante sería detectar el formato brochure/díptico y aplicar una heurística diferente.
- **Capa 4e — Residuales de contacto:** líneas como `E:` (prefijo de email sin dirección) pueden quedar residuales cuando el email fue eliminado por 4a. Direcciones parciales sin patrón postal explícito (ej. `Campestre Towers |Cali| Colombia`) no se eliminan.

### Mejoras futuras

- [ ] Migrar almacenamiento local a S3
- [ ] Agregar autenticación a la API
- [ ] Dashboard para visualización
- [ ] CI/CD pipeline
- [ ] Documentación de API más allá de OpenAPI
