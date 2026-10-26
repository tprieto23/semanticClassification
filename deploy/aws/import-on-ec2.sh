#!/usr/bin/env bash
# Restaura en RDS la base exportada y descomprime s3/. Se ejecuta en el EC2.
# Uso: bash deploy/aws/import-on-ec2.sh semantic_db.dump [s3.tar.gz]
set -euo pipefail

DUMP="${1:?Indica el archivo .dump}"
S3_TAR="${2:-}"
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

set -a
# shellcheck disable=SC1091
source "$APP_DIR/.env"
set +a
: "${DATABASE_URL:?Falta DATABASE_URL en .env}"

echo "==> Comprobando que la base de destino está vacía"
TABLES=$(docker run --rm postgres:16 psql "$DATABASE_URL" -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
if [ "$TABLES" != "0" ]; then
  echo "La base ya tiene $TABLES tablas. No se restaura para no sobrescribir datos." >&2
  echo "Si de verdad quieres reemplazarla, bórrala desde la consola de RDS y vuelve a crearla." >&2
  exit 1
fi

echo "==> Restaurando $DUMP en RDS"
docker run --rm -v "$(realpath "$DUMP")":/backup/semantic_db.dump:ro postgres:16 \
  pg_restore --no-owner --no-acl --exit-on-error -d "$DATABASE_URL" /backup/semantic_db.dump

echo "==> Verificación"
docker run --rm postgres:16 psql "$DATABASE_URL" -c \
  "SELECT status, productive_sector, count(*) FROM documents GROUP BY 1, 2 ORDER BY 1, 2;" \
  -c "SELECT version_num AS migracion FROM alembic_version;"

if [ -n "$S3_TAR" ]; then
  echo "==> Descomprimiendo $S3_TAR en $APP_DIR"
  tar -xzf "$S3_TAR" -C "$APP_DIR"
fi
echo "Importación terminada."
