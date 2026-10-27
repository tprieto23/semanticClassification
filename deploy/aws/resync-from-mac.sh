#!/usr/bin/env bash
# La Mac es la base principal: reemplaza la copia del servidor por la base actual
# de la Mac y comprueba que los conteos coincidan.
# Uso, desde la raíz del repo en la Terminal (no dentro del sandbox del agente):
#   bash deploy/aws/resync-from-mac.sh          # pide confirmación
#   bash deploy/aws/resync-from-mac.sh --yes    # sin confirmación
set -euo pipefail

cd "$(dirname "$0")/../.."
STATE=deploy/aws/.state.env
[ -f "$STATE" ] || { echo "Falta $STATE (ver deploy/aws/AGENT-RUNBOOK.md, paso 0)." >&2; exit 1; }
DB_MODE=$(grep -E '^DB_MODE=' "$STATE" | tail -1 | cut -d= -f2- || true)
DB_CONTAINER="${DB_CONTAINER:-sc_database}"
DB_USER="${POSTGRES_USER:-sc_user}"
DB_NAME="${POSTGRES_DB:-semantic_db}"
COUNTS_QUERY="SELECT status, productive_sector, count(1) FROM documents GROUP BY 1, 2 ORDER BY 1, 2;"
ENTITIES_QUERY="SELECT 'entidades', count(1) FROM entities;"

if [ "${1:-}" != "--yes" ]; then
  printf 'Esto REEMPLAZA la base del servidor por la de esta Mac. ¿Continuar? Escribe "si": '
  read -r answer
  [ "$answer" = "si" ] || { echo "Cancelado."; exit 1; }
fi

echo "==> 1/4 Exportando desde la Mac"
bash deploy/aws/export-from-mac.sh >/dev/null
local_counts=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tA -F '|' \
  -c "$COUNTS_QUERY" -c "$ENTITIES_QUERY")

echo "==> 2/4 Subiendo al servidor"
deploy/aws/bin/ec2-scp export/semantic_db.dump export/s3.tar.gz deploy/aws/replace-db-on-ec2.sh \
  semanticClassification/

echo "==> 3/4 Reemplazando la base del servidor (el dashboard queda sin datos un par de minutos)"
LOG=$(mktemp)
deploy/aws/bin/ec2-ssh \
  "cd ~/semanticClassification && DB_MODE='$DB_MODE' COUNTS_QUERY='$COUNTS_QUERY' ENTITIES_QUERY=\"$ENTITIES_QUERY\" bash replace-db-on-ec2.sh" \
  < /dev/null | tee "$LOG"
remote_counts=$(sed -n '/^COUNTS_BEGIN$/,/^COUNTS_END$/p' "$LOG" | sed '1d;$d')
rm -f "$LOG"

echo "==> 4/4 Verificando (estado | sector | cantidad)"
sed 's/^/  /' <<< "$local_counts"
if [ "$local_counts" = "$remote_counts" ]; then
  echo "OK: los conteos del servidor coinciden con los de la Mac."
else
  echo "DIFERENCIA entre la Mac y el servidor:" >&2
  diff <(echo "$local_counts") <(echo "$remote_counts") >&2 || true
  exit 1
fi
echo "Puedes borrar la copia local con: rm -rf export/"
