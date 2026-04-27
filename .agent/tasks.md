# Tasks

## Roadmap - Objetivos del proyecto

### Objetivo 1: Organizar archivos no estructurados ✅ DECIDIDO
- [x] Definir estructura de carpetas (`data/raw/`, `data/processed/`, `data/output/`)
- [x] Decidir DB para metadata (PostgreSQL)
- [ ] Implementar sistema de almacenamiento local
- [ ] Definir convención de nombres para archivos

### Objetivo 2: Convertir documentos a archivos planos ⏳ PENDIENTE
- [x] Decidir enfoque (Agente de IA)
- [ ] Seleccionar librerías/herramientas específicas
- [ ] Implementar conversión para PDF
- [ ] Implementar conversión para Word
- [ ] Implementar OCR para imágenes
- [ ] Implementar transcripción para audio/video
- [ ] Guardar metadata en DB

### Objetivo 3: Filtrar, limpiar y depurar textos ⏳ TBD
- [ ] Definir tipos de ruido a eliminar
- [ ] Definir qué conservar sí o sí
- [ ] Decidir si hay revisión humana
- [ ] Implementar limpieza con IA

### Objetivo 4: Clasificar entidades relevantes ⏳ TBD
- [ ] Definir lista completa de categorías
- [ ] Decidir si entidad puede tener múltiples categorías
- [ ] Decidir si clasificación es por documento o global
- [ ] Implementar clasificación (IA/reglas)
- [ ] Definir metadata de cada entidad

### Objetivo 5: Representar entidades mediante vectores ⏳ TBD
- [ ] Seleccionar modelo de embeddings
- [ ] Definir dimensiones del vector
- [ ] Decidir si embedding es por entidad o por aparición
- [ ] Implementar vectorización
- [ ] Guardar vectores en DB (pgvector)

### Objetivo 6: Construir matrices de adyacencia ⏳ TBD
- [ ] Definir qué es una "relación"
- [ ] Decidir si matriz es binaria o con pesos
- [ ] Decidir si matriz es por documento o global
- [ ] Definir tipos de relaciones
- [ ] Implementar generación de matrices

### Objetivo 7: Generar grafos de conocimiento ⏳ TBD
- [ ] Seleccionar librería (networkx, igraph, etc.)
- [ ] Decidir si grafo es dirigido o no
- [ ] Decidir si un solo grafo o múltiples
- [ ] Definir formato de exportación
- [ ] Implementar generación de grafos

### Objetivo 8: Calcular medidas de análisis de grafos ⏳ TBD
- [ ] Definir métricas a calcular
- [ ] Decidir si métricas son globales o por nodo
- [ ] Decidir frecuencia de cálculo
- [ ] Decidir si guardar historial
- [ ] Implementar cálculo de métricas

### Objetivo 9: Diseñar API ✅ DECIDIDO
- [x] Seleccionar framework (FastAPI)
- [x] Definir endpoints iniciales (/documents)
- [x] Decidir sin autenticación por ahora
- [x] Decidir Docker para local
- [x] OpenAPI para documentación
- [ ] Implementar endpoints de documents
- [ ] Implementar endpoints de entities (futuro)
- [ ] Implementar endpoints de graphs (futuro)
- [ ] Implementar endpoints de metrics (futuro)

### Objetivo 10: Base de datos ✅ DECIDIDO
- [x] PostgreSQL + pgvector
- [x] SQLAlchemy como ORM
- [x] Alembic para migraciones
- [x] Docker para DB
- [x] Backup manual
- [ ] Definir schema completo
- [ ] Crear migraciones iniciales
- [ ] Configurar conexión desde API

## En progreso

<!-- Tareas que se están trabajando actualmente -->

## Completadas

- [x] Definir estructura de documentación (.agent/)
- [x] Documentar objetivos del proyecto
- [x] Decidir stack tecnológico principal

## Próximos pasos

1. Definir schema de la base de datos
2. Configurar Docker (PostgreSQL + API)
3. Implementar endpoint POST /documents
4. Implementar conversión de documentos (Objetivo 2)
