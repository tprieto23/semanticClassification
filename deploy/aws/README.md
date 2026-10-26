# Despliegue en AWS (sa-east-1)

Guía paso a paso para llevar la API y la base PostgreSQL a AWS. El dashboard
(`semantic-network-explorer`) se publica en Vercel y consume la API por HTTPS.

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

## Costo aproximado (on-demand, sa-east-1)

| Recurso | Tipo | USD/mes aprox. |
|---|---|---|
| EC2 | t3.medium (2 vCPU, 4 GB) + 30 GB gp3 | 50–55 |
| RDS | db.t4g.micro + 20 GB | 25–30 |
| IP pública | Elastic IP | ~4 |
| **Total** | | **~80–90** |

Son valores de referencia: confírmalos en la
[AWS Pricing Calculator](https://calculator.aws/). Si la cuenta tiene créditos de la
capa gratuita, cubren parte de los primeros meses. Para ahorrar, `t4g.medium` (ARM)
cuesta ~20 % menos; la imagen ya funciona en ARM porque se usa en una Mac con Apple
Silicon.

---

## Paso 1 — Asegurar la cuenta (una sola vez)

1. Inicia sesión como **root** y activa **MFA**: menú de la cuenta → *Security
   credentials* → *Assign MFA device*.
2. Crea un usuario para el trabajo diario: **IAM → Users → Create user**, con acceso a la
   consola y la política `AdministratorAccess`. Activa MFA también para ese usuario. A
   partir de aquí, no uses root.
3. **Alerta de gastos**: *Billing and Cost Management → Budgets → Create budget* →
   plantilla *Monthly cost budget*, por ejemplo USD 100, con aviso a tu correo.
4. Arriba a la derecha, selecciona la región **South America (São Paulo) sa-east-1**.
   Todos los recursos van en esa región.

## Paso 2 — Crear el servidor EC2

**EC2 → Instances → Launch instances**

| Campo | Valor |
|---|---|
| Name | `semantic-api` |
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Instance type | `t3.medium` |
| Key pair | *Create new key pair* → `semantic-ec2`, tipo RSA, `.pem`. Guárdala en `~/.ssh/` y ejecuta `chmod 400 ~/.ssh/semantic-ec2.pem` |
| Storage | 30 GiB gp3 |

En *Network settings* → *Edit* → crea el security group `semantic-ec2-sg` con estas
reglas de entrada:

| Tipo | Puerto | Origen | Para qué |
|---|---|---|---|
| SSH | 22 | My IP | Administrar el servidor |
| Custom TCP | 8000 | My IP | API completa para Tania |
| HTTP | 80 | Anywhere (0.0.0.0/0) | Certificado HTTPS (Let's Encrypt) |
| HTTPS | 443 | Anywhere (0.0.0.0/0) | Explorador para Vercel |

*Launch instance*.

**IP fija**: *EC2 → Elastic IPs → Allocate Elastic IP address* → *Actions → Associate*
con la instancia `semantic-api`. Anota la IP, por ejemplo `18.228.10.5`.

El dominio del gateway se forma con esa IP: `18-228-10-5.sslip.io`. Es un servicio
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
ssh -i ~/.ssh/semantic-ec2.pem ubuntu@18.228.10.5
```

En el EC2:

```bash
curl -fsSL https://raw.githubusercontent.com/tprieto23/semanticClassification/feat/explorador-entidades/deploy/aws/setup-ec2.sh | bash
exit   # vuelve a entrar para usar docker sin sudo
```

El script instala Docker, crea 4 GB de swap, clona la rama y crea `~/semanticClassification/.env`.
Complétalo con `nano ~/semanticClassification/.env`:

```bash
DATABASE_URL=postgresql://sc_admin:<password>@<endpoint-rds>:5432/semantic_db?sslmode=require
ANTHROPIC_API_KEY=<la clave actual>
GATEWAY_HOST=18-228-10-5.sslip.io
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
    ubuntu@18.228.10.5:~/semanticClassification/
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

La Mac sigue teniendo su copia: la migración no borra nada en origen.

## Paso 6 — Levantar los servicios

```bash
cd ~/semanticClassification
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec api alembic upgrade head   # no-op si ya está al día
```

La primera construcción tarda 10–15 minutos (torch y docling). Para verificar:

```bash
curl https://18-228-10-5.sslip.io/health                       # {"status":"ok"} público
curl https://18-228-10-5.sslip.io/analysis/explorer/v1/meta    # explorador público
curl https://18-228-10-5.sslip.io/documents                    # 404: no expuesto
curl http://18.228.10.5:8000/docs                              # API completa, solo desde la IP de Tania
```

En Postman, Tania cambia la URL base de `http://localhost:8000` a
`http://18.228.10.5:8000`.

## Paso 7 — Publicar el dashboard en Vercel

1. En Vercel (cuenta de Tania): *Add New → Project* → importar
   `tprieto23/semantic-network-explorer`.
2. Framework: **Vite** (lo detecta solo por `vercel.json`).
3. *Environment Variables*: `VITE_API_BASE_URL` = `https://18-228-10-5.sslip.io`
4. *Deploy*.

`VITE_API_BASE_URL` se fija al construir. Si cambia el gateway, actualiza la variable y
vuelve a desplegar.

## Operación diaria

| Tarea | Comando (en el EC2, dentro de `~/semanticClassification`) |
|---|---|
| Actualizar a la última versión de la rama | `git pull && docker compose -f docker-compose.prod.yml up -d --build` |
| Ver logs | `docker compose -f docker-compose.prod.yml logs -f api` |
| Reiniciar | `docker compose -f docker-compose.prod.yml restart` |
| Aplicar migraciones | `docker compose -f docker-compose.prod.yml exec api alembic upgrade head` |
| Pausar gastos de cómputo | Detener la instancia EC2 desde la consola (RDS se detiene hasta 7 días) |

Los backups automáticos de RDS se restauran desde *RDS → Automated backups*. La
carpeta `s3/` vive en el disco del EC2; antes de usar el servidor como única fuente de
documentos, conviene programar snapshots del volumen (*EC2 → Lifecycle Manager*) o
moverla a un bucket S3.

## Pendientes conocidos

- Autenticación de la API (planificada).
- Restringir el CORS de la API al dominio de Vercel.
- Dominio propio en lugar de `sslip.io`.
