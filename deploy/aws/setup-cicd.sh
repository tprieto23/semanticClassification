#!/usr/bin/env bash
# Configuración única del despliegue automático (GitHub Actions → AWS Systems Manager).
# Se ejecuta desde la Mac, en la raíz del repo, con la sesión del AWS CLI activa.
# Es idempotente: si algo ya existe, lo reutiliza. Ver deploy/aws/CI-CD.md.
#   bash deploy/aws/setup-cicd.sh          # pide confirmación
#   bash deploy/aws/setup-cicd.sh --yes
set -euo pipefail

cd "$(dirname "$0")/../.."
source deploy/aws/bin/_state.sh
: "${INSTANCE_ID:?Falta INSTANCE_ID en deploy/aws/.state.env}"
: "${EIP:?Falta EIP en deploy/aws/.state.env}"
AWS=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")

GITHUB_REPO="${GITHUB_REPO:-tprieto23/semanticClassification}"
GITHUB_ENVIRONMENT=production
EC2_ROLE=semantic-ec2-ssm
DEPLOY_ROLE=github-deploy-semantic
OIDC_HOST=token.actions.githubusercontent.com
GATEWAY_URL="https://${GATEWAY_HOST:-${EIP//./-}.sslip.io}"

ACCOUNT_ID=$("${AWS[@]}" sts get-caller-identity --query Account --output text)
OIDC_ARN="arn:aws:iam::$ACCOUNT_ID:oidc-provider/$OIDC_HOST"

cat <<EOF
Se configurará el despliegue automático para $GITHUB_REPO (environment "$GITHUB_ENVIRONMENT").
Project $ACCOUNT_ID, región $AWS_REGION, servidor $INSTANCE_ID.

Recursos (todos sin costo: IAM, STS y Systems Manager Run Command son gratuitos):
  1. Rol de IAM "$EC2_ROLE" para el EC2, con la política administrada
     AmazonSSMManagedInstanceCore (o se agrega esa política al rol que ya tenga).
  2. Proveedor OIDC de GitHub ($OIDC_HOST), si no existe.
  3. Rol de IAM "$DEPLOY_ROLE" que solo puede asumir GitHub Actions desde
     $GITHUB_REPO en el environment "$GITHUB_ENVIRONMENT". Solo puede ejecutar
     AWS-RunShellScript en $INSTANCE_ID y leer el resultado.
No se abren puertos ni se guardan claves en GitHub.
EOF
if [ "${1:-}" != "--yes" ]; then
  printf '¿Crear estos recursos? Escribe "si": '
  read -r answer
  [ "$answer" = "si" ] || { echo "Cancelado."; exit 1; }
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "==> 1/4 Permiso de Systems Manager para el EC2"
association=$("${AWS[@]}" ec2 describe-iam-instance-profile-associations \
  --filters "Name=instance-id,Values=$INSTANCE_ID" "Name=state,Values=associated" \
  --query 'IamInstanceProfileAssociations[0].IamInstanceProfile.Arn' --output text)
if [ "$association" != None ]; then
  profile_name=${association##*/}
  role_name=$("${AWS[@]}" iam get-instance-profile --instance-profile-name "$profile_name" \
    --query 'InstanceProfile.Roles[0].RoleName' --output text)
  echo "El EC2 ya tiene el perfil $profile_name (rol $role_name); se le agrega la política."
else
  role_name=$EC2_ROLE
  if ! "${AWS[@]}" iam get-role --role-name "$role_name" >/dev/null 2>&1; then
    cat >"$tmp/ec2-trust.json" <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Principal": { "Service": "ec2.amazonaws.com" }, "Action": "sts:AssumeRole" }
  ]
}
EOF
    "${AWS[@]}" iam create-role --role-name "$role_name" \
      --description "Permite al EC2 semantic-api recibir comandos de Systems Manager" \
      --assume-role-policy-document "file://$tmp/ec2-trust.json" >/dev/null
  fi
  if ! "${AWS[@]}" iam get-instance-profile --instance-profile-name "$EC2_ROLE" >/dev/null 2>&1; then
    "${AWS[@]}" iam create-instance-profile --instance-profile-name "$EC2_ROLE" >/dev/null
    "${AWS[@]}" iam add-role-to-instance-profile --instance-profile-name "$EC2_ROLE" --role-name "$role_name"
    # IAM tarda unos segundos en propagar el perfil nuevo.
    sleep 10
  fi
  "${AWS[@]}" ec2 associate-iam-instance-profile --instance-id "$INSTANCE_ID" \
    --iam-instance-profile "Name=$EC2_ROLE" >/dev/null
fi
"${AWS[@]}" iam attach-role-policy --role-name "$role_name" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore

echo "==> 2/4 Proveedor OIDC de GitHub"
if "${AWS[@]}" iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
  echo "Ya existe."
else
  # AWS valida el certificado de GitHub con autoridades de confianza: no hace falta thumbprint.
  "${AWS[@]}" iam create-open-id-connect-provider --url "https://$OIDC_HOST" \
    --client-id-list sts.amazonaws.com >/dev/null
fi

echo "==> 3/4 Rol de despliegue para GitHub Actions"
cat >"$tmp/deploy-trust.json" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "$OIDC_ARN" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "$OIDC_HOST:aud": "sts.amazonaws.com",
          "$OIDC_HOST:sub": "repo:$GITHUB_REPO:environment:$GITHUB_ENVIRONMENT"
        }
      }
    }
  ]
}
EOF
cat >"$tmp/deploy-policy.json" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RunDeployScriptOnTheApiServer",
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ec2:$AWS_REGION:$ACCOUNT_ID:instance/$INSTANCE_ID",
        "arn:aws:ssm:$AWS_REGION::document/AWS-RunShellScript"
      ]
    },
    {
      "Sid": "ReadDeployStatus",
      "Effect": "Allow",
      "Action": ["ssm:GetCommandInvocation", "ssm:DescribeInstanceInformation", "ec2:DescribeInstances"],
      "Resource": "*"
    }
  ]
}
EOF
if "${AWS[@]}" iam get-role --role-name "$DEPLOY_ROLE" >/dev/null 2>&1; then
  "${AWS[@]}" iam update-assume-role-policy --role-name "$DEPLOY_ROLE" \
    --policy-document "file://$tmp/deploy-trust.json"
else
  "${AWS[@]}" iam create-role --role-name "$DEPLOY_ROLE" \
    --description "GitHub Actions ($GITHUB_REPO) despliega la API en el EC2 vía Systems Manager" \
    --max-session-duration 3600 \
    --assume-role-policy-document "file://$tmp/deploy-trust.json" >/dev/null
fi
"${AWS[@]}" iam put-role-policy --role-name "$DEPLOY_ROLE" --policy-name deploy-via-ssm \
  --policy-document "file://$tmp/deploy-policy.json"
DEPLOY_ROLE_ARN=$("${AWS[@]}" iam get-role --role-name "$DEPLOY_ROLE" --query Role.Arn --output text)

echo "==> 4/4 Conectando el agente de Systems Manager del EC2"
# El agente viene instalado en Ubuntu; se reinicia para que tome el permiso nuevo.
deploy/aws/bin/ec2-ssh 'sudo snap restart amazon-ssm-agent 2>/dev/null || sudo systemctl restart amazon-ssm-agent' </dev/null
ping=None
for _ in $(seq 1 24); do
  ping=$("${AWS[@]}" ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[0].PingStatus' --output text)
  [ "$ping" = Online ] && break
  sleep 10
done
if [ "$ping" != Online ]; then
  echo "El agente aún no aparece conectado ($ping). Espera unos minutos y revisa" >&2
  echo "  Systems Manager → Fleet Manager en la consola, o vuelve a ejecutar este script." >&2
  exit 1
fi
echo "Agente conectado."

cat <<EOF

Listo. Faltan los valores en GitHub ($GITHUB_REPO → Settings → Secrets and variables →
Actions → pestaña Variables → New repository variable):

  AWS_DEPLOY_ROLE_ARN = $DEPLOY_ROLE_ARN
  EC2_INSTANCE_ID     = $INSTANCE_ID
  GATEWAY_URL         = $GATEWAY_URL

Y el environment "$GITHUB_ENVIRONMENT" (Settings → Environments → New environment).
Si usas la CLI de GitHub (gh), esto lo hace por ti:

  gh api -X PUT repos/$GITHUB_REPO/environments/$GITHUB_ENVIRONMENT >/dev/null
  gh variable set AWS_DEPLOY_ROLE_ARN --repo $GITHUB_REPO --body "$DEPLOY_ROLE_ARN"
  gh variable set EC2_INSTANCE_ID --repo $GITHUB_REPO --body "$INSTANCE_ID"
  gh variable set GATEWAY_URL --repo $GITHUB_REPO --body "$GATEWAY_URL"
EOF
