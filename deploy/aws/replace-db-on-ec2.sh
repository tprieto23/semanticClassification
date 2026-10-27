#!/usr/bin/env bash
# Reemplaza la base del servidor por un dump nuevo y actualiza s3/.
# resync-from-mac.sh lo sube junto con el dump y lo ejecuta, así que no depende de
# la versión del repositorio clonado en el EC2. No se envía por stdin (bash -s):
# docker compose exec leería el resto del script como su propia entrada.
# Variables: DB_MODE (local-db o vacío para RDS), COUNTS_QUERY, ENTITIES_QUERY.
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/semanticClassification}"
DUMP="$APP_DIR/semantic_db.dump"
S3_TAR="$APP_DIR/s3.tar.gz"
cd "$APP_DIR"
[ -f "$DUMP" ] || { echo "No está $DUMP" >&2; exit 1; }

COMPOSE=(docker compose -f docker-compose.prod.yml)
[ "${DB_MODE:-}" = local-db ] && COMPOSE+=(--profile local-db)

set -a
# shellcheck disable=SC1091
source .env
set +a
: "${DATABASE_URL:?Falta DATABASE_URL en .env}"

trap 'echo "La resincronización falló. La API quedó detenida; revisa el error y vuelve a ejecutar resync-from-mac.sh." >&2' ERR

echo "==> Deteniendo la API"
"${COMPOSE[@]}" stop api

echo "==> Recreando la base vacía"
if [ "${DB_MODE:-}" = local-db ]; then
  DB_USER="${POSTGRES_USER:-sc_user}"
  DB_NAME="${POSTGRES_DB:-semantic_db}"
  "${COMPOSE[@]}" exec -T db dropdb -U "$DB_USER" --if-exists "$DB_NAME"
  "${COMPOSE[@]}" exec -T db createdb -U "$DB_USER" "$DB_NAME"
  PG_CLIENT=(docker run --rm --network "${COMPOSE_PROJECT_NAME:-semanticclassification}_default")
else
  ADMIN_URL="${DATABASE_URL%%\?*}"
  ADMIN_URL="${ADMIN_URL%/*}/postgres?sslmode=require"
  docker run --rm postgres:16 psql "$ADMIN_URL" -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS semantic_db WITH (FORCE);" -c "CREATE DATABASE semantic_db;"
  PG_CLIENT=(docker run --rm)
fi

echo "==> Restaurando la base"
"${PG_CLIENT[@]}" -v "$DUMP":/backup/semantic_db.dump:ro postgres:16 \
  pg_restore --no-owner --no-acl --exit-on-error -d "$DATABASE_URL" /backup/semantic_db.dump

if [ -f "$S3_TAR" ]; then
  echo "==> Actualizando s3/"
  # La API corre como root y crea carpetas dentro de s3/: hace falta sudo para sobrescribirlas.
  if sudo -n true 2>/dev/null; then
    sudo tar -xzf "$S3_TAR" -C "$APP_DIR"
  else
    tar -xzf "$S3_TAR" -C "$APP_DIR"
  fi
fi

echo "==> Levantando la API"
"${COMPOSE[@]}" start api
rm -f "$DUMP" "$S3_TAR" "$APP_DIR/replace-db-on-ec2.sh"
trap - ERR

echo "COUNTS_BEGIN"
"${PG_CLIENT[@]}" postgres:16 psql "$DATABASE_URL" -tA -F '|' \
  -c "${COUNTS_QUERY:?}" -c "${ENTITIES_QUERY:?}"
echo "COUNTS_END"
