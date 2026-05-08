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
  - ✅ Fase 1 (NER genérico con spaCy) implementada — **DEPRECADO**
  - ✅ Fase 2 (mapeo a 9 categorías con reglas deterministas) implementada — **DEPRECADO**
  - 🚧 Fase 3 (XLM-RoBERTa fine-tuned para Token Classification) en progreso
    - ✅ Dataset BIO generado desde `_all_entities_corrected.json`
    - ✅ Script de entrenamiento `train_ner_xlm.py` funcional
    - ✅ 1 época de prueba entrenada (test F1: 0.511)
    - ⏳ Entrenar 3-5 épocas para convergencia
    - ⏳ Integrar modelo al endpoint `/extract-entities` (reemplazar spaCy)
    - ⏳ Evaluar calidad vs. spaCy en corpus completo
  - ⏳ Revisión manual de entidades del dataset BIO para corregir errores residuales
  - ⏳ Extracción de NARRATIVA y PRÁCTICA (método alternativo a NER)
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
- **Entrenamiento en CPU:** XLM-RoBERTa `base` (270M parámetros) no cabe en MPS de 9GB ni siquiera con BS=1 + gradient checkpointing. Se entrena en CPU, lo cual es muy lento (~22 min/época). Solución a futuro: usar Google Colab (GPU gratuita T4) o reducir a `xlm-roberta-large` solo en inference (no para fine-tuning).
- **Dataset BIO con errores residuales:** el ground truth proviene de `_all_entities_corrected.json` que tiene errores de la primera iteración (spaCy cortó mal, reglas clasificaron mal). El modelo aprenderá a replicar esos errores hasta que se corrijan manualmente.
- **Modelo XLM-R aún no integrado en API:** el endpoint `/extract-entities` sigue usando spaCy. La integración requiere reescribir `src/services/ner.py` para usar el modelo entrenado.

### Mejoras futuras

- [ ] Migrar almacenamiento local a S3
- [ ] Agregar autenticación a la API
- [ ] Dashboard para visualización
- [ ] CI/CD pipeline
- [ ] Documentación de API más allá de OpenAPI
