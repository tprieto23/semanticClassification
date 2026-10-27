#!/usr/bin/env bash
# Activa el despliegue automático en el EC2 (opción de sondeo, ver deploy/aws/CI-CD.md).
# Se ejecuta una sola vez desde la Mac, en la raíz del repo y en la Terminal (usa SSH).
#   bash deploy/aws/install-autodeploy.sh          # pide confirmación
#   bash deploy/aws/install-autodeploy.sh --yes
set -euo pipefail
cd "$(dirname "$0")/../.."
source deploy/aws/bin/_state.sh
DB_MODE=$(grep -E '^DB_MODE=' deploy/aws/.state.env | tail -1 | cut -d= -f2- || true)
BRANCH=feat/explorador-entidades

cat <<MSG
Se instalará en el EC2 un temporizador de systemd que cada 5 minutos revisa la rama
$BRANCH en GitHub. Si hay un commit nuevo y su job «Tests» pasó, lo despliega con
deploy/aws/deploy-on-ec2.sh (reconstruye solo la API; no toca la base de datos).
No crea recursos en AWS ni credenciales: el repo es público y solo se lee GitHub.
MSG
if [ "${1:-}" != "--yes" ]; then
  printf '¿Instalar? Escribe "si": '
  read -r answer
  [ "$answer" = "si" ] || { echo "Cancelado."; exit 1; }
fi

deploy/aws/bin/ec2-ssh "set -euo pipefail
cd ~/semanticClassification
git fetch --quiet origin $BRANCH
git checkout --quiet $BRANCH
git merge --ff-only --quiet origin/$BRANCH
sudo DB_MODE='${DB_MODE:-local-db}' DEPLOY_BRANCH='$BRANCH' bash deploy/aws/autodeploy/install.sh
echo '==> Primera revisión (si el servidor ya está al día, no hace nada)'
sudo systemctl start semantic-autodeploy.service || true
journalctl -u semantic-autodeploy.service -n 20 --no-pager" </dev/null

echo
echo "Listo. Para ver el estado en cualquier momento: deploy/aws/bin/autodeploy-status"
