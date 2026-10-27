#!/usr/bin/env bash
# Despliega un commit concreto en el EC2: actualiza el código, reconstruye solo la
# API y espera a que responda. No toca la base de datos (la resincronización desde la
# Mac sigue siendo resync-from-mac.sh).
#
# Lo ejecuta el despliegue automático (deploy/aws/autodeploy/autodeploy.sh) como el
# usuario ubuntu. También sirve a mano:  bash deploy/aws/deploy-on-ec2.sh <commit>
# Variables: DEPLOY_BRANCH (feat/explorador-entidades), DB_MODE (local-db o vacío).
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/semanticClassification}"
BRANCH="${DEPLOY_BRANCH:-feat/explorador-entidades}"
EXPECTED="${1:?Uso: deploy-on-ec2.sh <commit>}"
cd "$APP_DIR"

COMPOSE=(docker compose -f docker-compose.prod.yml)
[ "${DB_MODE:-local-db}" = local-db ] && COMPOSE+=(--profile local-db)

echo "==> 1/4 Actualizando el código a $EXPECTED ($BRANCH)"
git fetch --quiet origin "$BRANCH"
git checkout --quiet "$BRANCH"
if [ "$(git rev-parse HEAD)" != "$EXPECTED" ] && git merge-base --is-ancestor "$EXPECTED" HEAD; then
  # Otro despliegue ya dejó una versión más nueva: no se retrocede.
  echo "El servidor ya tiene una versión posterior ($(git rev-parse --short HEAD)); nada que hacer."
  exit 0
fi
# Solo avanza (fast-forward) hasta el commit probado; nunca descarta trabajo local.
git merge --ff-only --quiet "$EXPECTED"
echo "Código en $(git log -1 --format='%h %s')"

echo "==> 2/4 Reconstruyendo la API"
"${COMPOSE[@]}" up -d --build api

echo "==> 3/4 Esperando a que la API responda"
for attempt in $(seq 1 30); do
  if curl -fsS -o /dev/null http://localhost:8000/health; then
    echo "API lista (intento $attempt)"
    break
  fi
  if [ "$attempt" = 30 ]; then
    echo "La API no respondió en 150 s. Últimos logs:" >&2
    "${COMPOSE[@]}" logs --tail 60 api >&2
    exit 1
  fi
  sleep 5
done

echo "==> 4/4 Migraciones y limpieza"
"${COMPOSE[@]}" exec -T api alembic upgrade head
# Las imágenes viejas de cada build se acumulan; el disco del EC2 es de 30 GB.
docker image prune -f >/dev/null
echo "DEPLOY_OK $(git rev-parse HEAD)"
