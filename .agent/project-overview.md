# Project Overview

## Descripción

El proyecto busca construir un proceso ordenado para analizar documentos no estructurados y convertirlos en información útil para la interpretación crítica de territorios, actores, acciones y relaciones socioambientales.

Parte de un corpus documental que debe ser revisado, limpiado y organizado para extraer elementos relevantes como:
- Comunidades
- Instituciones
- Lugares
- Prácticas
- Infraestructuras
- Valores ecológicos
- Narrativas

Luego, esa información se estructura para identificar conexiones entre los elementos encontrados y comprender cómo se relacionan dentro de un sistema territorial.

## Objetivos

1. **Procesar documentos no estructurados** - Revisar, limpiar y organizar el corpus documental
2. **Extraer elementos relevantes** - Identificar comunidades, instituciones, lugares, prácticas, infraestructuras, valores ecológicos y narrativas
3. **Estructurar información** - Organizar los elementos extraídos de manera sistemática
4. **Identificar conexiones** - Mapear relaciones entre los elementos dentro del sistema territorial
5. **Generar lectura interpretativa** - Pasar de documentos dispersos a una comprensión relacional del territorio

## Propósito central

Pasar de documentos dispersos a una lectura más clara, relacional e interpretativa, que permita analizar dinámicas sociales, ambientales y territoriales desde una perspectiva:
- **Situada**
- **Crítica**
- **Feminista**
- **De género**

## Alcance

### Incluye
- Procesamiento de documentos no estructurados
- Extracción y clasificación de entidades territoriales y socioambientales
- Identificación de relaciones entre actores y elementos del territorio
- Análisis crítico con perspectiva de género y feminista

### No incluye
<!-- Qué queda fuera del proyecto -->

## Estado actual

**Fase activa:** Migración del motor de extracción de entidades (Objetivo 4).

- ✅ Pipeline de limpieza (4 capas) completado y validado sobre 28 documentos
- ✅ Dataset de entidades corregido manualmente (13,681 entidades, primera iteración)
- 🚧 Reemplazo del motor NER: spaCy + reglas → XLM-RoBERTa fine-tuned
  - Dataset BIO generado (3,679 oraciones)
  - 1 época de prueba entrenada (test F1: 0.511)
  - Pendiente: 3-5 épocas de entrenamiento + integración en API
- ⏳ Objetivos 5-8 (vectores, matrices, grafos, métricas) aún no iniciados
