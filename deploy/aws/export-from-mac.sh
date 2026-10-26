#!/usr/bin/env bash
# Exporta la base y los archivos desde la máquina local (la Mac de Tania).
# Uso, desde la raíz del repo y con docker compose levantado:
#   bash deploy/aws/export-from-mac.sh
# Genera en ./export/: semantic_db.dump y s3.tar.gz
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-sc_database}"
DB_NAME="${POSTGRES_DB:-semantic_db}"
DB_USER="${POSTGRES_USER:-sc_user}"
OUT_DIR="${OUT_DIR:-export}"

mkdir -p "$OUT_DIR"

echo "==> Exportando la base $DB_NAME desde el contenedor $DB_CONTAINER"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner --no-acl \
  > "$OUT_DIR/semantic_db.dump"

echo "==> Empaquetando s3/ (documentos originales y procesados)"
tar -czf "$OUT_DIR/s3.tar.gz" s3

echo "==> Resumen de lo exportado"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
  "SELECT status, productive_sector, count(*) FROM documents GROUP BY 1, 2 ORDER BY 1, 2;"
ls -lh "$OUT_DIR"

cat <<NEXT

Sube los archivos al EC2 (reemplaza la llave y la IP):
  scp -i ~/.ssh/semantic-ec2.pem $OUT_DIR/semantic_db.dump $OUT_DIR/s3.tar.gz \\
      ubuntu@<IP-ELASTICA>:~/semanticClassification/
NEXT
