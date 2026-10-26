# Runbook de despliegue para agentes de IA

Instrucciones para que un agente de IA (Claude Code u otro) despliegue
`semanticClassification` en AWS desde la Mac de Tania, donde están los datos. La
explicación para personas está en [`README.md`](README.md); este archivo define el
orden, las confirmaciones obligatorias y las comprobaciones.

Los comandos del AWS CLI se validaron con `--dry-run` en el project el 2026-10-26.

## Reglas para el agente

1. **Confirma antes de crear, modificar o borrar** cualquier recurso de AWS. Muestra
   qué vas a crear y cuánto cuesta por hora y por mes, y espera un «sí» explícito de
   Tania. Una aprobación vale solo para el paso que describiste.
2. **Nunca borres ni sobrescribas datos.** No ejecutes `DROP`, `pg_restore --clean`,
   `docker compose down -v`, ni borres la base o `s3/` de la Mac. El script de
   importación ya se niega a restaurar sobre una base con tablas: no lo modifiques
   para saltarte esa protección.
3. **Nunca subas secretos ni datos a Git.** `.env`, la contraseña de RDS, la clave
   `.pem`, `export/` y `deploy/aws/.state.env` quedan fuera del repo (ya están en
   `.gitignore`). No pegues la `ANTHROPIC_API_KEY` en el chat ni en logs.
4. **Todo en `us-east-2`.** El project no puede crear recursos regionales en otra
   región. Usa siempre `--profile "$AWS_PROFILE" --region us-east-2`.
5. **Guarda el estado** (IDs, IP, endpoint) en `deploy/aws/.state.env` a medida que
   creas recursos, para poder retomar si la sesión se corta. Antes de crear un recurso,
   comprueba si ya existe (por nombre o etiqueta) para no duplicarlo.
6. **Verifica cada paso** con la comprobación indicada antes de seguir. Si algo falla,
   detente, muestra el error completo y propón una solución; no improvises cambios de
   arquitectura.
7. **Cada comando corre en una shell nueva.** Las variables, funciones y `export` de un
   comando anterior no existen en el siguiente. Por eso:
   - Ejecuta cada bloque de este runbook **como un solo comando**.
   - Usa siempre los scripts de `deploy/aws/bin/`, que leen el perfil, la región y la IP
     de `deploy/aws/.state.env` en cada llamada: `aws-project` en lugar de `aws`,
     `ec2-ssh` en lugar de `ssh` y `ec2-scp` en lugar de `scp`. Así nunca se usa por
     error el perfil `default`.
   - Los bloques funcionan en zsh (macOS) y en bash: no guardes opciones de comandos
     dentro de variables de texto como `R="--profile ..."`.
8. Sigue también las reglas de AWS del `CLAUDE.md` del repositorio (terminología
   *project*, *team member*, *AWS Settings*).

## Paso 0 — Comprobaciones y decisiones

Comprueba, sin crear nada:

```bash
git rev-parse --abbrev-ref HEAD            # debe ser feat/explorador-entidades
docker ps --format '{{.Names}}' | grep sc_database   # base local levantada
aws --version
aws configure get region --profile tania-semantic    # us-east-2
```

Si falta el AWS CLI o la sesión, configúralo con las instrucciones oficiales del
Agent Toolkit (`aws login --profile <perfil>`). Nunca pidas claves de acceso.

Luego haz a Tania **estas preguntas, en un solo mensaje**, y anota las respuestas en
`deploy/aws/.state.env`:

1. Nivel de guía (bajo, medio o alto), según `CLAUDE.md`.
2. ¿El servidor estará encendido 24/7 o con horario de apagado? Con 24/7, los créditos
   del plan gratuito (USD 100) alcanzan aproximadamente un mes. Ver costos en `README.md`.
3. ¿Base en **RDS** (`db.t4g.micro`, ~USD 12 al mes, backups automáticos) o
   **PostgreSQL dentro del EC2** (sin costo extra, sin backups automáticos)?
4. ¿Qué perfil del AWS CLI usar? Guárdalo en `deploy/aws/.state.env` (bloque siguiente).

### Archivo de estado

Guarda el perfil elegido en el archivo de estado. Los scripts de `deploy/aws/bin/` lo
leen en cada llamada:

```bash
touch deploy/aws/.state.env && chmod 600 deploy/aws/.state.env
grep -q '^AWS_PROFILE=' deploy/aws/.state.env || echo 'AWS_PROFILE=tania-semantic' >> deploy/aws/.state.env
deploy/aws/bin/aws-project sts get-caller-identity --query Account --output text
deploy/aws/bin/aws-project freetier get-account-plan-state
```

Si `aws-project` falla por la sesión, renuévala con `aws login --profile tania-semantic`.

Decisiones ya tomadas, que **no** debes volver a preguntar: API completa en AWS;
dashboard en Vercel (cuenta de Tania); región `us-east-2`; servidor `m7i-flex.large`;
el explorador solo usa documentos Agroforestry; la autenticación queda para más adelante.

## Paso 1 — Exportar desde la Mac (sin costo)

```bash
bash deploy/aws/export-from-mac.sh
```

**Comprobación**: existen `export/semantic_db.dump` y `export/s3.tar.gz`. Guarda la
tabla de conteos que imprime el script; la usarás en el paso 5.

## Paso 2 — Red y servidor EC2

Antes de ejecutar, confirma con Tania: EC2 `m7i-flex.large` USD 0,0958/h
(~USD 70 al mes 24/7) + disco de 30 GB (~USD 2,4 al mes) + Elastic IP (~USD 3,6 al mes).

```bash
STATE=deploy/aws/.state.env; source "$STATE"
MYIP=$(curl -fsS https://checkip.amazonaws.com)
VPC_ID=$(deploy/aws/bin/aws-project ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)

# Security group del servidor
EC2_SG=$(deploy/aws/bin/aws-project ec2 create-security-group --group-name semantic-ec2-sg \
  --description "semanticClassification API" --vpc-id "$VPC_ID" --query GroupId --output text)
deploy/aws/bin/aws-project ec2 authorize-security-group-ingress --group-id "$EC2_SG" --protocol tcp --port 22   --cidr "$MYIP/32"
deploy/aws/bin/aws-project ec2 authorize-security-group-ingress --group-id "$EC2_SG" --protocol tcp --port 8000 --cidr "$MYIP/32"
deploy/aws/bin/aws-project ec2 authorize-security-group-ingress --group-id "$EC2_SG" --protocol tcp --port 80   --cidr 0.0.0.0/0
deploy/aws/bin/aws-project ec2 authorize-security-group-ingress --group-id "$EC2_SG" --protocol tcp --port 443  --cidr 0.0.0.0/0

# Llave SSH (solo se puede descargar una vez)
deploy/aws/bin/aws-project ec2 create-key-pair --key-name semantic-ec2 --key-type rsa --key-format pem \
  --query KeyMaterial --output text > ~/.ssh/semantic-ec2.pem
chmod 400 ~/.ssh/semantic-ec2.pem

# Ubuntu 24.04 LTS oficial
AMI_ID=$(deploy/aws/bin/aws-project ssm get-parameters \
  --names /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --query 'Parameters[0].Value' --output text)

INSTANCE_ID=$(deploy/aws/bin/aws-project ec2 run-instances --image-id "$AMI_ID" --instance-type m7i-flex.large \
  --key-name semantic-ec2 --security-group-ids "$EC2_SG" --count 1 \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3,Encrypted=true}' \
  --metadata-options HttpTokens=required \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=semantic-api}]' \
  --query 'Instances[0].InstanceId' --output text)
deploy/aws/bin/aws-project ec2 wait instance-running --instance-ids "$INSTANCE_ID"

# IP fija
ALLOC_ID=$(deploy/aws/bin/aws-project ec2 allocate-address --domain vpc \
  --tag-specifications 'ResourceType=elastic-ip,Tags=[{Key=Name,Value=semantic-api}]' \
  --query AllocationId --output text)
deploy/aws/bin/aws-project ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC_ID"
EIP=$(deploy/aws/bin/aws-project ec2 describe-addresses --allocation-ids "$ALLOC_ID" --query 'Addresses[0].PublicIp' --output text)
GATEWAY_HOST="${EIP//./-}.sslip.io"

cat >> "$STATE" <<EOF
VPC_ID=$VPC_ID
EC2_SG=$EC2_SG
INSTANCE_ID=$INSTANCE_ID
ALLOC_ID=$ALLOC_ID
EIP=$EIP
GATEWAY_HOST=$GATEWAY_HOST
EOF
```

**Comprobación**: `deploy/aws/bin/ec2-ssh echo ok`
responde `ok`. Puede tardar uno o dos minutos después de arrancar.

## Paso 3A — Base en RDS (si Tania eligió RDS)

Confirma con Tania: `db.t4g.micro` USD 0,016/h (~USD 12 al mes) + 20 GB gp3 (~USD 2,3 al mes).

```bash
STATE=deploy/aws/.state.env; source "$STATE"
RDS_SG=$(deploy/aws/bin/aws-project ec2 create-security-group --group-name semantic-rds-sg \
  --description "semanticClassification RDS" --vpc-id "$VPC_ID" --query GroupId --output text)
deploy/aws/bin/aws-project ec2 authorize-security-group-ingress --group-id "$RDS_SG" --protocol tcp --port 5432 \
  --source-group "$EC2_SG"

PG_VERSION=$(deploy/aws/bin/aws-project rds describe-db-engine-versions --engine postgres --engine-version 16 \
  --query 'DBEngineVersions[-1].EngineVersion' --output text)
DB_PASSWORD=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32)

deploy/aws/bin/aws-project rds create-db-instance --db-instance-identifier semantic-db \
  --engine postgres --engine-version "$PG_VERSION" --db-instance-class db.t4g.micro \
  --allocated-storage 20 --storage-type gp3 --storage-encrypted \
  --master-username sc_admin --master-user-password "$DB_PASSWORD" --db-name semantic_db \
  --vpc-security-group-ids "$RDS_SG" --no-publicly-accessible --no-multi-az \
  --backup-retention-period 7 --deletion-protection \
  --tags Key=Name,Value=semantic-db >/dev/null
deploy/aws/bin/aws-project rds wait db-instance-available --db-instance-identifier semantic-db   # ~10 minutos
DB_HOST=$(deploy/aws/bin/aws-project rds describe-db-instances --db-instance-identifier semantic-db \
  --query 'DBInstances[0].Endpoint.Address' --output text)

cat >> "$STATE" <<EOF
RDS_SG=$RDS_SG
DB_HOST=$DB_HOST
DB_PASSWORD=$DB_PASSWORD
DATABASE_URL=postgresql://sc_admin:$DB_PASSWORD@$DB_HOST:5432/semantic_db?sslmode=require
EOF
```

La contraseña solo usa letras y números, así que no hay que codificarla en la URL.
Pídele a Tania que la guarde en su gestor de contraseñas.

**Comprobación**: `DB_HOST` termina en `.us-east-2.rds.amazonaws.com`.

## Paso 3B — PostgreSQL dentro del EC2 (si Tania eligió la opción sin RDS)

No crea recursos en AWS. Genera la contraseña y la URL interna:

```bash
STATE=deploy/aws/.state.env; source "$STATE"
DB_PASSWORD=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32)
cat >> "$STATE" <<EOF
DB_MODE=local-db
POSTGRES_PASSWORD=$DB_PASSWORD
DATABASE_URL=postgresql://sc_user:$DB_PASSWORD@db:5432/semantic_db
EOF
```

En este modo, los comandos `docker compose` de los pasos 5 y 6 llevan
`--profile local-db`, y la importación usa
`IMPORT_DOCKER_NETWORK=semanticclassification_default`.

## Paso 4 — Preparar el servidor

```bash
STATE=deploy/aws/.state.env; source "$STATE"
deploy/aws/bin/ec2-ssh 'curl -fsSL https://raw.githubusercontent.com/tprieto23/semanticClassification/feat/explorador-entidades/deploy/aws/setup-ec2.sh | bash'
```

Construye el `.env` de producción **en un archivo temporal local** y súbelo, sin
mostrar su contenido. Toma la clave de Anthropic del `.env` local; si no está, pídele a
Tania que la agregue ahí (no la escribas en el chat):

```bash
STATE=deploy/aws/.state.env; source "$STATE"
grep -Eq '^ANTHROPIC_API_KEY=.+' .env || { echo "Falta ANTHROPIC_API_KEY en .env"; false; }
ENV_TMP=$(mktemp); chmod 600 "$ENV_TMP"
{
  echo "DATABASE_URL=$DATABASE_URL"
  grep '^ANTHROPIC_API_KEY=' .env
  echo "GATEWAY_HOST=$GATEWAY_HOST"
  echo "API_WORKERS=2"
  [ "${DB_MODE:-}" = local-db ] && echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
} > "$ENV_TMP"
deploy/aws/bin/ec2-scp "$ENV_TMP" semanticClassification/.env
deploy/aws/bin/ec2-ssh 'chmod 600 ~/semanticClassification/.env'
rm -f "$ENV_TMP"
```

**Comprobación**: `deploy/aws/bin/ec2-ssh 'docker --version && grep -c = ~/semanticClassification/.env'`
muestra la versión de Docker y al menos cuatro variables.

## Paso 5 — Migrar los datos

```bash
deploy/aws/bin/ec2-scp export/semantic_db.dump export/s3.tar.gz semanticClassification/
```

Con RDS:

```bash
deploy/aws/bin/ec2-ssh 'cd ~/semanticClassification && bash deploy/aws/import-on-ec2.sh semantic_db.dump s3.tar.gz'
```

Con PostgreSQL dentro del EC2:

```bash
deploy/aws/bin/ec2-ssh 'cd ~/semanticClassification && docker compose -f docker-compose.prod.yml --profile local-db up -d db \
  && sleep 10 && IMPORT_DOCKER_NETWORK=semanticclassification_default \
     bash deploy/aws/import-on-ec2.sh semantic_db.dump s3.tar.gz'
```

**Comprobación obligatoria**: la tabla de conteos por `status` y `productive_sector`
coincide exactamente con la del paso 1. Si no coincide, detente e informa a Tania.

Cuando coincida, borra los archivos temporales del servidor:
`deploy/aws/bin/ec2-ssh 'rm ~/semanticClassification/semantic_db.dump ~/semanticClassification/s3.tar.gz'`.

## Paso 6 — Levantar los servicios

```bash
STATE=deploy/aws/.state.env; source "$STATE"
PROFILE_FLAG=""; [ "${DB_MODE:-}" = local-db ] && PROFILE_FLAG="--profile local-db"
deploy/aws/bin/ec2-ssh "cd ~/semanticClassification && docker compose -f docker-compose.prod.yml $PROFILE_FLAG up -d --build"
deploy/aws/bin/ec2-ssh "cd ~/semanticClassification && docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head"
```

La primera construcción tarda entre 10 y 15 minutos.

**Comprobación** (todas deben cumplirse):

```bash
STATE=deploy/aws/.state.env; source "$STATE"
curl -fsS "https://$GATEWAY_HOST/health"; echo                             # {"status":"ok"}
curl -fsS "https://$GATEWAY_HOST/analysis/explorer/v1/meta" -o /tmp/semantic-meta.json \
  && echo "documentos Agroforestry: $(grep -o '"document_type"' /tmp/semantic-meta.json | wc -l)"
curl -s -o /dev/null -w '%{http_code}\n' "https://$GATEWAY_HOST/documents"  # 404
curl -s -o /dev/null -w '%{http_code}\n' "http://$EIP:8000/health"          # 200 desde la IP de Tania
```

Si el HTTPS falla los primeros minutos, revisa
`deploy/aws/bin/ec2-ssh 'cd ~/semanticClassification && docker compose -f docker-compose.prod.yml logs gateway'`:
Caddy necesita el puerto 80 abierto para obtener el certificado.

## Paso 7 — Dashboard en Vercel

Requiere que exista el repo `tprieto23/semantic-network-explorer` en GitHub. Si no
existe, avisa a Tania y detente en este paso.

El valor de `GATEWAY_HOST` está en `deploy/aws/.state.env`.

Opción con el panel de Vercel (recomendada): *Add New → Project* → importar
`tprieto23/semantic-network-explorer` → variable `VITE_API_BASE_URL=https://<GATEWAY_HOST>`
→ *Deploy*.

Opción con la CLI, desde el repo del frontend:

```bash
npx vercel login
npx vercel link
npx vercel env add VITE_API_BASE_URL production   # valor: https://<GATEWAY_HOST>
npx vercel --prod
```

**Comprobación**: la URL de Vercel carga la red, el selector «Sector productivo»
muestra Agroforestería y no hay errores en la consola del navegador.

## Paso 8 — Cierre

1. Informa a Tania, sin mostrar secretos:
   - URL del dashboard en Vercel y del gateway.
   - URL de la API completa para Postman: `http://$EIP:8000`.
   - Costo mensual estimado y créditos restantes (`deploy/aws/bin/aws-project freetier get-account-plan-state`).
   - Cómo apagar y encender el servidor (tabla «Operación diaria» del `README.md`).
2. Si eligió horario de apagado, propón el comando o una regla programada y créala solo
   si lo confirma.
3. Pregunta si quiere borrar `export/` de la Mac. Contiene una copia de los datos.
4. Pregunta si quiere conservar todos los recursos creados o limpiar alguno (regla de
   `CLAUDE.md`).
5. Agrega en `.agent/sessions/` una bitácora con lo desplegado. Usa IDs, nunca secretos.

## Deshacer (solo con confirmación explícita de Tania)

Borrar recursos es irreversible. Muestra la lista exacta de lo que se borrará y pide
confirmación para cada recurso.

```bash
STATE=deploy/aws/.state.env; source "$STATE"
deploy/aws/bin/aws-project ec2 terminate-instances --instance-ids "$INSTANCE_ID"
deploy/aws/bin/aws-project ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
deploy/aws/bin/aws-project ec2 release-address --allocation-id "$ALLOC_ID"
# RDS: primero quitar la protección; se conserva un snapshot final
deploy/aws/bin/aws-project rds modify-db-instance --db-instance-identifier semantic-db --no-deletion-protection --apply-immediately
deploy/aws/bin/aws-project rds delete-db-instance --db-instance-identifier semantic-db \
  --final-db-snapshot-identifier semantic-db-final-$(date +%Y%m%d)
deploy/aws/bin/aws-project ec2 delete-security-group --group-id "$RDS_SG"
deploy/aws/bin/aws-project ec2 delete-security-group --group-id "$EC2_SG"
deploy/aws/bin/aws-project ec2 delete-key-pair --key-name semantic-ec2
```
