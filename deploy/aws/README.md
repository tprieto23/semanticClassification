# Despliegue en AWS (us-east-2)

Guía paso a paso para llevar la API y la base PostgreSQL a AWS. El dashboard
(`semantic-network-explorer`) se publica en Vercel y consume la API por HTTPS.

> **Si eres un agente de IA**, sigue [`AGENT-RUNBOOK.md`](AGENT-RUNBOOK.md): define el
> orden, las confirmaciones obligatorias y las comprobaciones de cada paso.

```
Vercel (dashboard) ──HTTPS──▶ EC2 :443 Caddy ── solo /analysis/explorer/v1/* ──▶ API :8000
Tania (su IP) ─────HTTP─────▶ EC2 :8000 API completa (Postman)                      │
                                                                                  ▼
                                                      RDS PostgreSQL 16, sin acceso público
```

- **Público**: solo los endpoints de lectura del explorador, a través del gateway.
- **Solo desde la IP de Tania**: la API completa (subir, procesar, borrar) y SSH.
- **Nunca público**: la base de datos.

No hay autenticación todavía. Cualquiera que tenga la URL del gateway puede leer los
resultados del explorador, pero no modificarlos.

## Datos del project

| Dato | Valor |
|---|---|
| Experiencia | Nueva experiencia de AWS (*project*, inicio de sesión social) |
| Región | **us-east-2 (Ohio)**. Obligatoria: el project no puede crear recursos en otras regiones |
| Plan | FREE, USD 100 de créditos, vence el 2027-04-26 (consultado el 2026-10-26) |
| Tipos de EC2 permitidos | t3/t4g/t8i micro y small, `c7i-flex.large` (4 GB), `m7i-flex.large` (8 GB) |
| Clases de RDS permitidas | `db.t3.micro`, `db.t4g.micro` |

Comprueba el estado del plan con:

```bash
aws freetier get-account-plan-state --profile <perfil> --region us-east-2
```

## Costo (on-demand, us-east-2, precios del 2026-10-26)

| Recurso | Tipo | USD/hora | USD/mes 24/7 |
|---|---|---|---|
| EC2 | `m7i-flex.large` (2 vCPU, 8 GB) | 0,0958 | 69,9 |
| RDS | `db.t4g.micro` | 0,0160 | 11,7 |
| Discos | EBS 30 GB gp3 + RDS 20 GB | — | ~5 |
| IP pública | Elastic IP | 0,005 | ~3,6 |
| **Total** | | | **~90** |

Con todo encendido las 24 horas, **los USD 100 de créditos alcanzan para un mes**.
Formas de estirarlos:

- **Apagar el EC2 cuando no se use.** Encendido 10 h en días hábiles cuesta ~USD 21 al
  mes de cómputo. Mientras está detenido solo se pagan los discos y la IP.
- **PostgreSQL dentro del EC2** en lugar de RDS ahorra ~USD 14 al mes, pero se pierden
  los backups automáticos (perfil `local-db` en `docker-compose.prod.yml`).
- `c7i-flex.large` (4 GB) cuesta ~USD 8 menos al mes, con menos margen para docling.

Antes de que se acaben los créditos o venza el plan, hay que pasar al plan pago en
AWS Settings para no perder los recursos.

---

## Paso 1 — Preparar el project (una sola vez)

En la nueva experiencia, la administración se hace en **AWS Settings**
(<https://settings.aws.com>), no en IAM:

1. **Región**: confirma que sea `us-east-2` en *AWS Settings → View all projects →
   Overview → Additional info → Region*.
2. **Límite de gasto**: si el project pasa al plan pago, configura un *spend limit* en
   *AWS Settings → Billing*. Al superarlo, el project se pausa.
3. **Alerta de gastos**: *Billing and Cost Management → Budgets → Create budget* →
   *Monthly cost budget*, por ejemplo USD 50, con aviso por correo.
4. **Colaboradores**: se invitan como *team members* por correo desde AWS Settings.
   No se crean usuarios IAM.
5. En la consola (<https://console.aws.amazon.com>), selecciona arriba a la derecha la
   región **US East (Ohio) us-east-2**.

## Paso 2 — Crear el servidor EC2

**EC2 → Instances → Launch instances**

| Campo | Valor |
|---|---|
| Name | `semantic-api` |
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Instance type | `m7i-flex.large` |
| Key pair | *Create new key pair* → `semantic-ec2`, tipo RSA, `.pem`. Guárdala en `~/.ssh/` y ejecuta `chmod 400 ~/.ssh/semantic-ec2.pem` |
| Storage | 30 GiB gp3 |

En *Network settings* → *Edit*, crea el security group `semantic-ec2-sg` con estas
reglas de entrada:

| Tipo | Puerto | Origen | Para qué |
|---|---|---|---|
| SSH | 22 | My IP | Administrar el servidor |
| Custom TCP | 8000 | My IP | API completa para Tania |
| HTTP | 80 | Anywhere (0.0.0.0/0) | Certificado HTTPS (Let's Encrypt) |
| HTTPS | 443 | Anywhere (0.0.0.0/0) | Explorador para Vercel |

*Launch instance*.

**IP fija**: *EC2 → Elastic IPs → Allocate Elastic IP address* → *Actions → Associate*
con la instancia `semantic-api`. Anota la IP, por ejemplo `3.141.20.7`.

El dominio del gateway se forma con esa IP: `3-141-20-7.sslip.io`. Es un servicio
gratuito que resuelve a la IP y permite obtener el certificado HTTPS sin comprar un
dominio. Más adelante se puede cambiar por un dominio propio.

> Si la IP de Tania cambia (pasa en conexiones domésticas), actualiza las reglas
> 22 y 8000 del security group con *My IP*.

## Paso 3 — Crear la base RDS

**RDS → Databases → Create database**

| Campo | Valor |
|---|---|
| Creation method | Standard create |
| Engine | PostgreSQL, versión 16.x |
| Templates | Free tier (o Dev/Test) |
| Deployment | Single-AZ |
| DB instance identifier | `semantic-db` |
| Master username | `sc_admin` |
| Credentials | *Self managed*, con una contraseña larga (guárdala en un gestor) |
| Instance class | `db.t4g.micro` |
| Storage | gp3, 20 GiB, sin autoscaling |
| Connectivity | **Connect to an EC2 compute resource** → `semantic-api` |
| Public access | **No** |
| Additional configuration → Initial database name | `semantic_db` |
| Backup | Automated backups, retención de 7 días |
| Encryption | Activada (viene por defecto) |

Al elegir *Connect to an EC2 compute resource*, AWS crea los security groups para
que solo el EC2 pueda conectarse a la base. Cuando el estado sea *Available*, copia el
**Endpoint** (*Connectivity & security*).

pgvector ya viene disponible en RDS. La restauración crea la extensión automáticamente.

## Paso 4 — Preparar el servidor

Desde la Mac de Tania:

```bash
ssh -i ~/.ssh/semantic-ec2.pem ubuntu@3.141.20.7
```

En el EC2:

```bash
curl -fsSL https://raw.githubusercontent.com/tprieto23/semanticClassification/feat/explorador-entidades/deploy/aws/setup-ec2.sh | bash
exit   # vuelve a entrar para usar docker sin sudo
```

El script instala Docker, crea 4 GB de swap, clona la rama y crea
`~/semanticClassification/.env`. Complétalo con `nano ~/semanticClassification/.env`:

```bash
DATABASE_URL=postgresql://sc_admin:<password>@<endpoint-rds>:5432/semantic_db?sslmode=require
ANTHROPIC_API_KEY=<la clave actual>
GATEWAY_HOST=3-141-20-7.sslip.io
API_WORKERS=2
```

Si la contraseña tiene caracteres como `@`, `:` o `/`, codifícalos en la URL
(por ejemplo, `@` → `%40`).

## Paso 5 — Migrar los datos desde la Mac

En la Mac, desde la raíz de `semanticClassification` y con `docker compose up -d`
corriendo:

```bash
bash deploy/aws/export-from-mac.sh
scp -i ~/.ssh/semantic-ec2.pem export/semantic_db.dump export/s3.tar.gz \
    ubuntu@3.141.20.7:~/semanticClassification/
```

El script muestra cuántos documentos hay por estado y sector, para comparar después.

En el EC2:

```bash
cd ~/semanticClassification
bash deploy/aws/import-on-ec2.sh semantic_db.dump s3.tar.gz
```

El script se niega a restaurar si la base de destino ya tiene tablas, para no pisar
datos por error. Al terminar muestra los mismos conteos: deben coincidir con los de la
Mac.

La Mac conserva su copia: la migración no borra nada en el origen. El archivo
`export/` contiene datos de investigación; no lo subas a Git y bórralo cuando la
migración esté verificada.

## Paso 6 — Levantar los servicios

```bash
cd ~/semanticClassification
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec api alembic upgrade head   # no hace nada si ya está al día
```

La primera construcción tarda entre 10 y 15 minutos (torch y docling). Para verificar:

```bash
curl https://3-141-20-7.sslip.io/health                       # {"status":"ok"}, público
curl https://3-141-20-7.sslip.io/analysis/explorer/v1/meta    # explorador, público
curl https://3-141-20-7.sslip.io/documents                    # 404: no expuesto
curl http://3.141.20.7:8000/docs                              # API completa, solo desde la IP de Tania
```

En Postman, Tania cambia la URL base de `http://localhost:8000` a
`http://3.141.20.7:8000`.

## Paso 7 — Publicar el dashboard en Vercel

1. En Vercel (cuenta de Tania): *Add New → Project* → importar
   `tprieto23/semantic-network-explorer`.
2. Framework: **Vite** (lo detecta solo por `vercel.json`).
3. *Environment Variables*: `VITE_API_BASE_URL` = `https://3-141-20-7.sslip.io`
4. *Deploy*.

`VITE_API_BASE_URL` se fija al construir. Si cambia el gateway, actualiza la variable y
vuelve a desplegar.

## Resincronizar el servidor con la Mac

Mientras la Mac sea la base principal (se procesan documentos ahí), el servidor es una
copia que hay que actualizar después de procesar documentos nuevos. Desde la raíz del
repo, en la **Terminal** (no dentro del sandbox del agente, que bloquea SSH):

```bash
bash deploy/aws/resync-from-mac.sh
```

El script pide confirmación, exporta la base y `s3/`, los sube, detiene la API,
reemplaza la base del servidor, actualiza `s3/`, vuelve a levantar la API y compara los
conteos de documentos y entidades. Si no coinciden, termina con error y muestra las
diferencias. El dashboard queda sin datos un par de minutos mientras corre.

`s3/` se actualiza agregando y sobrescribiendo archivos; los que se borren en la Mac no
se borran en el servidor.

## Operación diaria

| Tarea | Comando o acción |
|---|---|
| Actualizar a la última versión de la rama | Automático con cada push, si está configurado [`CI-CD.md`](CI-CD.md). A mano, en el EC2: `bash deploy/aws/deploy-on-ec2.sh $(git rev-parse origin/feat/explorador-entidades)` |
| Ver logs | `docker compose -f docker-compose.prod.yml logs -f api` |
| Reiniciar | `docker compose -f docker-compose.prod.yml restart` |
| Aplicar migraciones | `docker compose -f docker-compose.prod.yml exec api alembic upgrade head` |
| Apagar el servidor | `aws ec2 stop-instances --instance-ids <id> --profile <perfil> --region us-east-2` |
| Encenderlo | `aws ec2 start-instances --instance-ids <id> --profile <perfil> --region us-east-2` |
| Consultar créditos | `aws freetier get-account-plan-state --profile <perfil> --region us-east-2` |

Los servicios se levantan solos al encender el EC2 (`restart: unless-stopped`). La IP
elástica no cambia al apagar y encender.

Los backups automáticos de RDS se restauran desde *RDS → Automated backups*. La
carpeta `s3/` vive en el disco del EC2; antes de usar el servidor como única fuente de
documentos, conviene programar snapshots del volumen (*EC2 → Lifecycle Manager*) o
moverla a un bucket S3.

## Pendientes conocidos

- Autenticación de la API (planificada).
- Restringir el CORS de la API al dominio de Vercel.
- Dominio propio en lugar de `sslip.io`.
- Pasar al plan pago antes de que se agoten los créditos.
