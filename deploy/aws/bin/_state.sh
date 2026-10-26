# Carga deploy/aws/.state.env. Cada script lo usa para no depender de la shell
# anterior: los agentes ejecutan cada comando en una shell nueva.
STATE_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.state.env"
if [ -f "$STATE_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$STATE_FILE"
  set +a
fi
: "${AWS_PROFILE:?Falta AWS_PROFILE en deploy/aws/.state.env (paso 0)}"
export AWS_REGION=us-east-2 AWS_PAGER=""
SSH_KEY="${SSH_KEY:-$HOME/.ssh/semantic-ec2.pem}"
