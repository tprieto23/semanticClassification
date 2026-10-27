# Sesión de trabajo — 26 Oct 2026: explorador de entidades

## Objetivo

Exponer una API de lectura para un dashboard interactivo que visualice la red de
coocurrencia de entidades con filtros que reduzcan el ruido y permitan comparar
la centralidad entre períodos.

## Decisiones de la usuaria

- Las diez categorías se enlazan; la proyección PRAC/INFRA/RUL fue exploratoria.
- Un nodo es importante por recurrencia documental y por centralidad.
- La evolución temporal usa dos períodos: 2021–2023 y 2024–2026.
- La prioridad es la red de entidades. La meta-red queda en espera: no está definido
  si los clusters serán por categoría o mixtos.
- El frontend vive en un repositorio aparte, por escalabilidad.

## Implementación

Rama `feat/explorador-entidades`, creada desde `feat/endpoints-red-coocurrencia`.
Ver la sección «Explorador de entidades» en `../context/architecture.md`.

- Las métricas se calculan en el backend para que la metodología viva en un solo
  lugar; el navegador solo dibuja la red filtrada.
- Los rangos se calculan sobre la red filtrada completa antes del recorte `top_n`.
- La comparación entre períodos se construye siempre sin `top_n`.

## Verificación

- `tests/test_explorer.py`: 20 pruebas (incluye validación del contrato de respuesta y del filtro de sector).
- Suite local: 127 pruebas exitosas; 3 fallas previas en
  `test_semantic_relationships.py` porque el entorno local usa SQLite para tipos UUID
  de PostgreSQL. No están relacionadas con este cambio.
- PostgreSQL 16 temporal con migraciones hasta `c6d7e8f9a0b1` y un corpus
  sintético de 12 documentos: `meta`, `network`, `compare` y `evidence` responden
  correctamente. El total de la evidencia coincide con `sentence_count`.
- No se tocó la DB real ni `s3/`.

## Filtro de sector productivo

Decisión de la usuaria: no usar en el análisis los documentos que no tengan
`productive_sector = Agroforestry`. El explorador aplica ese sector por defecto en
`meta`, `network`, `compare` y `evidence`. `productive_sector: "all"` los incluye
explícitamente, y `meta.documents_excluded_by_sector` informa cuántos documentos listos
quedan fuera. `/analysis/network`, las proyecciones y Leiden no cambiaron.

## Despliegue en AWS (us-east-2)

- `docker-compose.prod.yml`: API sin `--reload`, `s3/` y `data/` montados, y gateway
  Caddy con HTTPS automático (dominio `sslip.io`) que solo expone
  `/analysis/explorer/v1/*` y `/health`. La API completa queda en el puerto 8000,
  limitado a la IP de la usuaria por el security group.
- La base va en RDS PostgreSQL 16. El perfil `local-db` permite una base en el mismo EC2.
- `.dockerignore` ahora excluye `s3/`: antes la imagen copiaba los documentos.
- Scripts `deploy/aws/{setup-ec2,export-from-mac,import-on-ec2}.sh` y guía
  `deploy/aws/README.md`. La importación se niega a restaurar sobre una base con tablas.
- Verificado localmente: imagen de producción, gateway (explorador 200; `/documents`,
  `/docs`, `DELETE` 404), preflight CORS y migración `pg_dump` → `pg_restore` con conteos
  idénticos y pgvector restaurado.
- El dashboard se publica en Vercel con `VITE_API_BASE_URL` apuntando al gateway.

### Project de AWS y runbook para agentes

- El project usa la nueva experiencia de AWS y solo permite recursos en `us-east-2`;
  se descartó `sa-east-1`. Plan FREE con USD 100 de créditos (vence el 2027-04-26).
- Tipos de EC2 permitidos por el plan: hasta `m7i-flex.large` (8 GB), el elegido para
  docling. RDS: `db.t4g.micro`. Precios on-demand consultados en la API de precios:
  ~USD 90 al mes con todo encendido 24/7.
- `deploy/aws/AGENT-RUNBOOK.md`: despliegue por AWS CLI pensado para que lo ejecute el
  agente de la Mac de Tania, con confirmaciones de costo, estado en
  `deploy/aws/.state.env` (ignorado por Git) y comprobaciones por paso. Los comandos
  de EC2 se validaron con `--dry-run` en el project.
- `export/` y `deploy/aws/.state.env` agregados a `.gitignore`: el repo es público y
  esos archivos contienen datos o secretos.
- `import-on-ec2.sh` admite `IMPORT_DOCKER_NETWORK` para la base dentro del EC2;
  probado con RDS simulado y con red Docker.
- `CLAUDE.md` con instrucciones del proyecto y las reglas del Agent Toolkit de AWS.

### Corrección del runbook para zsh (macOS)

El primer intento en la Mac se detuvo en el paso 2, sin crear recursos:
`aws: [ERROR]: Unknown options: --profile ... --region ...`. Causa: zsh no separa en
palabras una variable sin comillas, y el runbook guardaba las opciones en `R="..."`. Se
reprodujo el error con zsh 5.9. Corrección: `AWS_PROFILE`/`AWS_REGION` como variables
de entorno, funciones `ec2_ssh`/`ec2_scp`, `grep -E` y la versión de Postgres
consultada sin `sort -V`. Todos los bloques se validaron con `bash -n` y `zsh -n`, y el
entorno y las consultas de solo lectura del paso 2 se ejecutaron en ambos shells. Se
auditó el project: no quedó ningún recurso del intento fallido.

### Corrección del runbook: un comando, una shell

El agente de la Mac se detuvo en el paso 5 con `zsh:1: command not found: ec2_ssh`:
su herramienta ejecuta cada comando en una shell nueva, así que las funciones y
variables de un bloque anterior no existen. Corrección: scripts sin estado en
`deploy/aws/bin/` (`aws-project`, `ec2-ssh`, `ec2-scp`), que leen el perfil, la región
y la IP de `deploy/aws/.state.env` en cada llamada y fallan si falta `AWS_PROFILE`, en
lugar de usar el perfil `default`. Cada bloque carga el estado por sí mismo. Se probó
ejecutando cada bloque en una shell zsh nueva (lectura real de AWS y del gateway;
ssh/scp simulados).

Estado auditado en el project antes de corregir: EC2 `m7i-flex.large` en ejecución con
Elastic IP, PostgreSQL dentro del EC2 (sin RDS), puertos 22/8000 limitados a la IP de
la usuaria, IMDSv2 obligatorio. El gateway responde con 83 documentos Agroforestry
(78 excluidos por sector) y `/documents` da 404.

### Migración verificada y resincronización

- Conteos idénticos Mac/servidor después de migrar: 83 Agroforestry y 78 sin sector en
  `fuzzyMatching`, 34 en `ner`, 108.602 entidades. Alembic al día; `/health` 200 y
  `/documents` 404 en el gateway.
- El sandbox de Claude Code en macOS bloquea SSH (`Operation not permitted`) y no dejó
  pasar los endpoints de AWS aunque se agregaron a `allowedDomains`. Los pasos que
  necesitan SSH o el AWS CLI se ejecutan desde la Terminal.
- Decisión de la usuaria (opción A): la Mac sigue siendo la base principal. Los 34
  documentos en `ner` se procesaron en la Mac después de migrar.
- `deploy/aws/resync-from-mac.sh` + `replace-db-on-ec2.sh`: reemplazan la copia del
  servidor y comparan conteos. Probado con un servidor simulado (compose de producción,
  base local-db con datos distintos y ssh/scp simulados). El primer intento enviaba el
  script por `bash -s` y `docker compose exec` consumía el resto como entrada; ahora se
  sube y se ejecuta en el servidor. `s3/` se extrae con `sudo` porque la API crea
  carpetas como root.
- Datos reales: los 83 documentos no tienen año, idioma ni tipo documental, así que la
  vista de Evolución queda vacía. La red por defecto tardó ~52 s (36.873 nodos y 122.131
  aristas de coocurrencia); con recurrencia 1 no terminó en 5 minutos. Pendiente:
  optimizar el rendimiento y cargar los metadatos.
