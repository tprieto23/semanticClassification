#!/usr/bin/env bash
# Despliegue automático por sondeo: corre en el EC2 cada 5 minutos (temporizador de
# systemd). Si la rama tiene un commit nuevo y su job «Tests» de GitHub Actions
# terminó bien, lo despliega con deploy-on-ec2.sh. No necesita credenciales: el repo
# es público y solo se lee la API de GitHub.
#
# Variables (las fija el servicio de systemd): GITHUB_REPO, DEPLOY_BRANCH, APP_DIR,
# DB_MODE, STATE_DIR.
set -euo pipefail

# Todo vive dentro de main: bash lee la función completa antes de ejecutarla, así que
# el git merge del despliegue puede cambiar este mismo archivo sin romper la ejecución.
main() {
  local repo="${GITHUB_REPO:-tprieto23/semanticClassification}"
  local branch="${DEPLOY_BRANCH:-feat/explorador-entidades}"
  local app_dir="${APP_DIR:-$HOME/semanticClassification}"
  local state_dir="${STATE_DIR:-$HOME/.semantic-autodeploy}"
  local api="https://api.github.com/repos/$repo"
  mkdir -p "$state_dir"

  # Un despliegue a la vez, aunque systemd ya evita solapamientos.
  exec 9>"$state_dir/lock"
  flock -n 9 || { echo "Otro despliegue en curso; se omite este ciclo."; return 0; }

  # Se compara con el último commit que este script desplegó con éxito, no con la
  # carpeta del repo: un git pull a mano en el servidor cambia la carpeta sin
  # reconstruir la API. Sin registro (primera vez), se despliega una vez.
  local latest deployed
  latest=$(github "$api/commits/$branch" | json '["sha"]')
  deployed=$(cat "$state_dir/deployed" 2>/dev/null || echo none)
  if [ "$latest" = "$deployed" ]; then
    return 0
  fi

  # Estado del job «Tests» del workflow para ese commit.
  local check status conclusion
  check=$(github "$api/commits/$latest/check-runs?check_name=Tests&per_page=1")
  status=$(json '["check_runs"][0]["status"]' <<<"$check" || echo none)
  conclusion=$(json '["check_runs"][0]["conclusion"]' <<<"$check" || echo none)

  if [ "$status" != completed ]; then
    note "$state_dir" "$latest" "Commit ${latest:0:7}: tests aún no terminan ($status); se reintenta en el próximo ciclo."
    return 0
  fi
  if [ "$conclusion" != success ]; then
    note "$state_dir" "$latest" "Commit ${latest:0:7}: los tests no pasaron ($conclusion); no se despliega."
    return 0
  fi

  # Si el mismo commit ya falló 3 veces, no se insiste hasta que llegue otro.
  local failures
  failures=$(grep -c " error $latest\$" "$state_dir/history" 2>/dev/null || true)
  if [ "${failures:-0}" -ge 3 ]; then
    note "$state_dir" "$latest" "Commit ${latest:0:7}: falló 3 veces; se espera un commit nuevo."
    return 0
  fi

  echo "Desplegando ${latest:0:7} (antes ${deployed:0:7})"
  git -C "$app_dir" fetch --quiet origin "$branch"
  # El script de despliegue se toma del commit que se despliega.
  git -C "$app_dir" show "$latest:deploy/aws/deploy-on-ec2.sh" >"$state_dir/deploy-on-ec2.sh"
  if DEPLOY_BRANCH="$branch" DB_MODE="${DB_MODE:-local-db}" APP_DIR="$app_dir" \
    bash "$state_dir/deploy-on-ec2.sh" "$latest"; then
    printf '%s ok %s\n' "$(date -Is)" "$latest" >>"$state_dir/history"
    printf '%s\n' "$latest" >"$state_dir/deployed"
    echo "Despliegue de ${latest:0:7} terminado."
  else
    printf '%s error %s\n' "$(date -Is)" "$latest" >>"$state_dir/history"
    echo "El despliegue de ${latest:0:7} falló; se reintentará en el próximo ciclo." >&2
    return 1
  fi
}

# GET a la API pública de GitHub (60 consultas por hora sin token; el sondeo usa ~24).
github() {
  curl -fsS --max-time 20 -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" "$1"
}

# Lee un campo del JSON de stdin con la ruta dada, p. ej. '["sha"]'.
json() {
  python3 -c "import json, sys; print(json.load(sys.stdin)$1)"
}

# Informa una sola vez por commit, para no llenar el log cada 5 minutos.
note() {
  local state_dir=$1 sha=$2 message=$3
  if [ "$(cat "$state_dir/last-note" 2>/dev/null)" != "$sha $message" ]; then
    echo "$message"
    printf '%s %s' "$sha" "$message" >"$state_dir/last-note"
  fi
}

main "$@"
exit
