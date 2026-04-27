# Technical Debt

## Deuda técnica conocida

### Pendientes de decisión

- [ ] **Objetivo 2:** Librerías específicas para conversión (PDF, Word, OCR, audio, video)
- [ ] **Objetivo 3:** Qué tipo de ruido eliminar, qué conservar, revisión humana
- [ ] **Objetivo 4:** Lista completa de entidades, categorías, clasificación
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
*(ninguno por ahora)*

### Mejoras futuras

- [ ] Migrar almacenamiento local a S3
- [ ] Agregar autenticación a la API
- [ ] Dashboard para visualización
- [ ] CI/CD pipeline
- [ ] Documentación de API más allá de OpenAPI
