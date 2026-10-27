#!/usr/bin/env bash
# Corre en GitHub Actions, ya con credenciales temporales de AWS (OIDC). Ordena al EC2
# desplegar el commit probado mediante Systems Manager (sin SSH ni puertos abiertos),
# espera el resultado y comprueba el gateway público.
#
# Variables: INSTANCE_ID, COMMIT_SHA, DEPLOY_BRANCH, GATEWAY_URL, DB_MODE (local-db).
set -euo pipefail

: "${INSTANCE_ID:?Falta INSTANCE_ID}"
: "${COMMIT_SHA:?Falta COMMIT_SHA}"
: "${DEPLOY_BRANCH:?Falta DEPLOY_BRANCH}"
: "${GATEWAY_URL:?Falta GATEWAY_URL}"
DB_MODE="${DB_MODE:-local-db}"
export AWS_REGION="${AWS_REGION:-us-east-2}" AWS_PAGER=""

echo "==> Comprobando el servidor $INSTANCE_ID"
state=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].State.Name' --output text)
if [ "$state" != running ]; then
  echo "::error::El EC2 está '$state'. Enciéndelo (aws ec2 start-instances) y vuelve a ejecutar el workflow."
  exit 1
fi
ping=$(aws ssm describe-instance-information \
  --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
  --query 'InstanceInformationList[0].PingStatus' --output text)
if [ "$ping" != Online ]; then
  echo "::error::El agente de Systems Manager del EC2 no está conectado ($ping). Revisa deploy/aws/CI-CD.md, paso 1."
  exit 1
fi

# El script de despliegue se toma del propio commit que se despliega.
remote="set -euo pipefail
cd ~/semanticClassification
git fetch --quiet origin '$DEPLOY_BRANCH'
git show '$COMMIT_SHA:deploy/aws/deploy-on-ec2.sh' > /tmp/deploy-on-ec2.sh
DEPLOY_BRANCH='$DEPLOY_BRANCH' DB_MODE='$DB_MODE' bash /tmp/deploy-on-ec2.sh '$COMMIT_SHA'"
params=$(jq -n --arg script "$remote" \
  '{commands: ["sudo -u ubuntu -H bash -c " + ($script | @sh)], executionTimeout: ["1800"]}')

echo "==> Enviando el despliegue de ${COMMIT_SHA:0:7}"
command_id=$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "deploy ${COMMIT_SHA:0:7} desde GitHub Actions" \
  --parameters "$params" \
  --query 'Command.CommandId' --output text)
echo "Comando $command_id"

status=Pending
for _ in $(seq 1 120); do
  sleep 15
  status=$(aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" \
    --query Status --output text 2>/dev/null || echo Pending)
  case "$status" in
    Pending | InProgress | Delayed) echo "… $status" ;;
    *) break ;;
  esac
done

aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" \
  --query StandardOutputContent --output text
errors=$(aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" \
  --query StandardErrorContent --output text)
[ -n "$errors" ] && [ "$errors" != None ] && echo "--- stderr ---" && echo "$errors"
if [ "$status" != Success ]; then
  echo "::error::El despliegue terminó con estado $status."
  exit 1
fi

echo "==> Comprobando el gateway público"
for attempt in $(seq 1 12); do
  if curl -fsS -o /dev/null "$GATEWAY_URL/health" && curl -fsS -o /tmp/meta.json "$GATEWAY_URL/analysis/explorer/v1/meta"; then
    jq -r '"Gateway OK: \(.documents | length) documentos; períodos: \([.periods[] | "\(.label) (\(.document_count))"] | join(", "))"' /tmp/meta.json
    exit 0
  fi
  sleep 5
done
echo "::error::La API se desplegó, pero el gateway no responde en $GATEWAY_URL."
exit 1
