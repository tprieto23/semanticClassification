#!/usr/bin/env bash
# Prepara un EC2 Ubuntu 24.04 recién creado: Docker, swap y el repositorio.
# Uso (en el EC2): curl -fsSL <url-raw-de-este-archivo> | bash
#             o:  bash deploy/aws/setup-ec2.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/tprieto23/semanticClassification.git}"
BRANCH="${BRANCH:-feat/explorador-entidades}"
APP_DIR="${APP_DIR:-$HOME/semanticClassification}"

echo "==> Instalando Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "==> Swap de 4 GB (la imagen trae torch y docling)"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
fi

echo "==> Código en $APP_DIR (rama $BRANCH)"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
fi
mkdir -p "$APP_DIR/s3"

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/deploy/aws/env.production.example" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "==> Creado $APP_DIR/.env: complétalo antes de levantar los servicios."
fi

cat <<NEXT

Listo. Próximos pasos:
  1. Cierra la sesión SSH y vuelve a entrar (para usar docker sin sudo).
  2. Completa $APP_DIR/.env (DATABASE_URL, ANTHROPIC_API_KEY, GATEWAY_HOST).
  3. Importa los datos: bash deploy/aws/import-on-ec2.sh <archivo.dump> [s3.tar.gz]
  4. Levanta todo:   cd $APP_DIR && docker compose -f docker-compose.prod.yml up -d --build
NEXT
