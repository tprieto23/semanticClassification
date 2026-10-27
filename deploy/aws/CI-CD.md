# Despliegue automático de la API (GitHub Actions → AWS)

Cada push a `feat/explorador-entidades` corre los tests del backend en GitHub. Si
pasan, GitHub le ordena al EC2 que actualice el código y reconstruya la API, a través
de **AWS Systems Manager**. No hace falta entrar por SSH ni correr nada a mano.

```
push a feat/explorador-entidades
  → GitHub Actions: tests (pytest)
  → si pasan: credenciales temporales de AWS (OIDC, sin claves guardadas)
  → Systems Manager ejecuta deploy/aws/deploy-on-ec2.sh en el EC2
  → el workflow comprueba /health y /meta en el gateway y queda ✅ o ❌
```

- **No despliega código con tests rotos.** En pull requests solo corre los tests.
- **No toca la base de datos.** Los datos se siguen actualizando desde la Mac con
  `resync-from-mac.sh`, porque la base principal está ahí (opción A).
- **No abre puertos ni guarda llaves.** GitHub obtiene permisos temporales de AWS que
  solo sirven para enviar ese comando a ese servidor.
- **Costo: ninguno.** IAM, STS y Systems Manager Run Command son gratuitos y están
  incluidos en el plan Free de la nueva experiencia de AWS. GitHub Actions es gratis
  para repositorios públicos.

Archivos:

| Archivo | Qué hace |
|---|---|
| `.github/workflows/backend.yml` | Tests en cada push y PR; despliegue en la rama desplegada |
| `deploy/aws/ci/deploy-via-ssm.sh` | Corre en GitHub: envía el despliegue y espera el resultado |
| `deploy/aws/deploy-on-ec2.sh` | Corre en el EC2: `git` fast-forward, reconstruye la API, espera `/health`, migra |
| `deploy/aws/setup-cicd.sh` | Configuración única de AWS (este documento, paso 1) |

## Configuración (una sola vez)

### 1. AWS: permisos para Systems Manager y para GitHub

Desde la Mac, en la raíz del repo, con la sesión del AWS CLI activa
(`aws login --profile tania-semantic` si expiró). Usa SSH en el último paso, así que
un agente necesita permisos elevados:

```bash
bash deploy/aws/setup-cicd.sh
```

El script muestra qué va a crear y pide confirmación:

1. **Rol `semantic-ec2-ssm`** para el EC2, con la política administrada
   `AmazonSSMManagedInstanceCore`. Si el EC2 ya tiene un rol, le agrega esa política.
2. **Proveedor OIDC de GitHub** (`token.actions.githubusercontent.com`).
3. **Rol `github-deploy-semantic`**. Solo lo puede asumir GitHub Actions desde
   `tprieto23/semanticClassification` en el environment `production`, y solo puede
   ejecutar `AWS-RunShellScript` en este EC2 y leer el resultado.

Al final reinicia el agente de Systems Manager del EC2 (viene instalado en Ubuntu),
espera a que aparezca conectado e imprime los valores para GitHub.

### 2. GitHub: environment y variables

En el repo, **Settings**:

1. **Environments → New environment** → `production`. Opcional: en *Required
   reviewers* puedes exigir una aprobación antes de cada despliegue.
2. **Secrets and variables → Actions → Variables → New repository variable**, con los
   valores que imprimió el script:

| Variable | Ejemplo |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::<cuenta>:role/github-deploy-semantic` |
| `EC2_INSTANCE_ID` | `i-0abc…` |
| `GATEWAY_URL` | `https://3-13-151-74.sslip.io` |

No son secretos: no dan acceso por sí solos. El permiso real es la política de
confianza del rol, que solo acepta a este repo y a este environment.

Mientras `AWS_DEPLOY_ROLE_ARN` no exista, el workflow solo corre los tests.

### 3. Probar

**Actions → Backend · tests y despliegue → Run workflow** sobre
`feat/explorador-entidades`. El job *Desplegar en AWS* debe terminar con algo como:

```
DEPLOY_OK <commit>
Gateway OK: 115 documentos; períodos: 2000–2020 (33), 2021–2023 (31), 2024–2026 (51)
```

## Uso diario

- Hacer push a `feat/explorador-entidades` y esperar el ✅ en la pestaña *Actions*
  (de 3 a 15 minutos, según cuánto cambie la imagen).
- Si llegan varios pushes seguidos, se despliegan en orden, uno a la vez.
- Mientras se reconstruye, la API puede responder 502 durante unos segundos.

## Si algo falla

| Mensaje en el workflow | Qué hacer |
|---|---|
| `El EC2 está 'stopped'` | Encenderlo: `deploy/aws/bin/aws-project ec2 start-instances --instance-ids <id>` y volver a ejecutar el workflow |
| `El agente de Systems Manager del EC2 no está conectado` | Volver a correr `bash deploy/aws/setup-cicd.sh` (es idempotente) |
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | El environment no se llama `production` o el repo cambió de nombre: revisar el paso 2 o correr el script con `GITHUB_REPO=dueño/repo` |
| `La API no respondió en 150 s` | El log del job muestra los últimos logs de la API; corregir y hacer push |
| `fatal: Not possible to fast-forward` | Alguien cambió código directamente en el EC2: revisar `git status` ahí |

Si un despliegue deja la API rota, hacer push de un commit que lo revierta
(`git revert <commit>`) también lo despliega.

## Desactivar

Borrar la variable `AWS_DEPLOY_ROLE_ARN` en GitHub: los tests siguen corriendo, pero no
se despliega. Para quitar también los permisos en AWS, borrar el rol
`github-deploy-semantic` en IAM.
