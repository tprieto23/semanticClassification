#!/usr/bin/env bash
# Instala en el EC2 el servicio y el temporizador de systemd del despliegue automático.
# Se ejecuta con sudo desde la raíz del repo clonado; lo llama install-autodeploy.sh.
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/semanticClassification}"
APP_USER="${APP_USER:-ubuntu}"
GITHUB_REPO="${GITHUB_REPO:-tprieto23/semanticClassification}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-feat/explorador-entidades}"
DB_MODE="${DB_MODE:-local-db}"

cat >/etc/systemd/system/semantic-autodeploy.service <<UNIT
[Unit]
Description=Despliegue automático de la API de semanticClassification
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
User=$APP_USER
Environment=HOME=/home/$APP_USER
Environment=APP_DIR=$APP_DIR
Environment=GITHUB_REPO=$GITHUB_REPO
Environment=DEPLOY_BRANCH=$DEPLOY_BRANCH
Environment=DB_MODE=$DB_MODE
ExecStart=/bin/bash $APP_DIR/deploy/aws/autodeploy/autodeploy.sh
# La primera reconstrucción de la imagen puede tardar más de 15 minutos.
TimeoutStartSec=45min
UNIT

cat >/etc/systemd/system/semantic-autodeploy.timer <<UNIT
[Unit]
Description=Revisa cada 5 minutos si hay una versión nueva con los tests en verde

[Timer]
OnCalendar=*:0/5
RandomizedDelaySec=30
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now semantic-autodeploy.timer
systemctl list-timers semantic-autodeploy.timer --no-pager
