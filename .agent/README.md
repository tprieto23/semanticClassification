# .agent - Documentación del Proyecto

Este directorio contiene **toda la información centralizada** del proyecto. Su propósito es permitir que cualquier modelo o sesión nueva pueda ponerse al día rápidamente.

## Orden de lectura para iniciar sesión

Cada vez que se inicie una sesión nueva, **leer en este orden**:

1. `README.md` (este archivo) - Guía de uso
2. `project-overview.md` - Contexto general del proyecto
3. `methodology.md` - Metodología técnica y métricas
4. `architecture.md` - Arquitectura y estructura
5. `tech-stack.md` - Tecnologías utilizadas
6. `conventions.md` - Convenciones de código
7. `tasks.md` - Estado actual de tareas
8. `decisions.md` - Decisiones técnicas tomadas
9. `session.md` - Última sesión trabajada

## Archivos de la documentación

| Archivo | Propósito |
|---------|-----------|
| `README.md` | Esta guía |
| `project-overview.md` | Visión general, objetivos y alcance |
| `methodology.md` | Metodología técnica, etapas, métricas e interpretación |
| `architecture.md` | Arquitectura, patrones y estructura |
| `tech-stack.md` | Tecnologías, librerías y dependencias |
| `conventions.md` | Convenciones de código, naming, estilo |
| `tasks.md` | Estado de tareas, roadmap y próximos pasos |
| `decisions.md` | Decisiones técnicas importantes (ADRs) |
| `session.md` | Contexto de la sesión actual |

## Qué documentar

**Siempre** registrar en los archivos correspondientes:

- ✅ **Cosas nuevas que se aprenden** durante el desarrollo
- ✅ **Decisiones que se toman** (arquitectura, librerías, patrones)
- ✅ **Planes que se hacen** (features futuros, refactorizaciones)
- ✅ **Problemas a solucionar después** → ver `tech-debt.md`

## 🔄 Flujo de trabajo

### Al empezar una sesión:
1. Leer todos los archivos en el orden especificado
2. Revisar `session.md` para ver en qué se quedó
3. Actualizar `session.md` con lo que se va a trabajar
4. **Preguntar:** "Tengo todo el contexto, ¿en qué vamos a trabajar hoy?"
5. **Ofrecer opciones** basadas en el estado actual del proyecto (ver `tasks.md`)

### Al terminar una sesión:
1. Actualizar `session.md` con lo realizado
2. Mover decisiones importantes a `decisions.md`
3. Actualizar `tasks.md` con el progreso
4. Registrar deuda técnica en `tech-debt.md` si aplica

## Deuda técnica

Los problemas conocidos, workarounds temporales y mejoras pendientes se documentan en `tech-debt.md`.

---

**Importante:** Esta documentación debe mantenerse **actualizada en cada sesión**. Es la única fuente de verdad del proyecto.
