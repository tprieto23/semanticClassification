# Despliegue automático de la API

Cada push a `feat/explorador-entidades` corre los tests del backend en GitHub Actions.
El EC2 revisa GitHub cada 5 minutos: si la rama tiene un commit nuevo **y su job
«Tests» terminó bien**, actualiza el código y reconstruye la API. No hace falta entrar
por SSH ni correr nada a mano.

```
push a feat/explorador-entidades
  → GitHub Actions: job «Tests» (pytest)
  → el EC2, cada 5 minutos: ¿commit nuevo con «Tests» en verde?
  → sí: deploy/aws/deploy-on-ec2.sh <commit> (fast-forward, reconstruye la API,
         espera /health, aplica migraciones)
```

- **No despliega código con tests rotos**, ni commits cuyos tests siguen corriendo.
- **No toca la base de datos.** Los datos se siguen actualizando desde la Mac con
  `resync-from-mac.sh`, porque la base principal está ahí (opción A).
- **No hay credenciales.** El repo es público: el EC2 solo lee la API de GitHub. No se
  guardan llaves de AWS en GitHub ni se abren puertos.
- **Costo: ninguno.** GitHub Actions es gratis en repos públicos y el sondeo corre en el
  EC2 que ya existe.

### Por qué así y no desde GitHub

La forma habitual es que GitHub Actions entre a AWS con credenciales temporales (OIDC).
En la nueva experiencia de AWS no es posible: la política administrada del project
prohíbe `iam:*Provider*`, tanto en el plan Free como en el pago, así que no se puede
registrar a GitHub como proveedor de identidad. La alternativa, una llave de AWS fija
guardada en GitHub, es menos segura. Por eso el servidor consulta a GitHub.

Archivos:

| Archivo | Qué hace |
|---|---|
| `.github/workflows/backend.yml` | Job «Tests» en cada push a la rama y en cada pull request |
| `deploy/aws/autodeploy/autodeploy.sh` | Corre en el EC2 cada 5 minutos y decide si desplegar |
| `deploy/aws/deploy-on-ec2.sh` | Despliega un commit: fast-forward, reconstruye la API, espera `/health`, migra |
| `deploy/aws/autodeploy/install.sh` | Crea el servicio y el temporizador de systemd en el EC2 |
| `deploy/aws/install-autodeploy.sh` | Lo instala desde la Mac (una sola vez) |
| `deploy/aws/bin/autodeploy-status` | Muestra el estado desde la Mac |

## Instalación (una sola vez)

Desde la Mac, en la raíz del repo, en la Terminal (usa SSH; un agente necesita permisos
elevados):

```bash
git checkout feat/explorador-entidades && git pull
bash deploy/aws/install-autodeploy.sh
```

El script pide confirmación, actualiza el repo del EC2, instala el temporizador
`semantic-autodeploy.timer` y hace una primera revisión. Si el servidor ya está al día,
esa revisión no hace nada.

## Uso diario

- Hacer push a `feat/explorador-entidades`.
- Ver el job «Tests» en la pestaña *Actions* de GitHub (menos de un minuto).
- Dentro de los 5 minutos siguientes, el EC2 despliega. La reconstrucción tarda de 3 a
  15 minutos, según cuánto cambie la imagen; mientras tanto la API puede responder 502
  durante unos segundos.

Para ver qué pasó:

```bash
deploy/aws/bin/autodeploy-status
```

Muestra la próxima revisión, el commit del código, el último commit desplegado por el
temporizador, cuándo se construyó la imagen de la API, el historial y los últimos
mensajes. El temporizador compara GitHub con lo que **él mismo desplegó** (no con la
carpeta del repo), así que un `git pull` a mano en el servidor no lo confunde: en el
siguiente ciclo reconstruye la API. Ejemplo de mensajes:

```
Commit 3a1b2c4: tests aún no terminan (in_progress); se reintenta en el próximo ciclo.
Desplegando 3a1b2c4 (antes 415fa73)
DEPLOY_OK 3a1b2c4…
Despliegue de 3a1b2c4 terminado.
```

## Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `los tests no pasaron (failure); no se despliega` | Corregir y hacer push; el servidor sigue con la versión anterior |
| `tests aún no terminan (none)` durante mucho tiempo | El commit no tiene job «Tests» (por ejemplo, se canceló el workflow). Volver a ejecutarlo en *Actions* |
| `El despliegue de … falló; se reintentará` | Ver el detalle con `autodeploy-status`. Si la API no arranca, el log muestra sus últimas líneas |
| `falló 3 veces; se espera un commit nuevo` | Tras 3 intentos fallidos con el mismo commit deja de reconstruir. Corregir y hacer push; para reintentar el mismo commit, borrar `~/.semantic-autodeploy/history` en el EC2 |
| `fatal: Not possible to fast-forward` | Alguien cambió código directamente en el EC2: revisar `git status` ahí |

Si un despliegue deja la API rota, hacer push de un commit que lo revierta
(`git revert <commit>`) también lo despliega.

El sondeo hace unas 24 consultas por hora a la API pública de GitHub, que permite 60
sin token.

## Pausar o desinstalar

```bash
deploy/aws/bin/ec2-ssh 'sudo systemctl disable --now semantic-autodeploy.timer'   # pausar
deploy/aws/bin/ec2-ssh 'sudo systemctl enable --now semantic-autodeploy.timer'    # reanudar
```

Para desinstalarlo, además de pausar, borrar
`/etc/systemd/system/semantic-autodeploy.{service,timer}` en el EC2.

## Recurso que quedó de la primera versión

Durante la primera configuración se creó el rol de IAM `semantic-ec2-ssm`, asociado al
EC2 con la política `AmazonSSMManagedInstanceCore`. No tiene costo y permite usar
*Systems Manager → Session Manager* para abrir una terminal en el servidor desde la
consola, sin SSH. Si no se quiere, se puede desasociar en *EC2 → Actions → Security →
Modify IAM role* y borrar en IAM.
