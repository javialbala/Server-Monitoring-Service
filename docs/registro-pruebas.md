# Registro de pruebas

Registro cronológico de pruebas y validaciones **realmente ejecutadas**. Cada entrada indica la fase,
el comando o procedimiento, el resultado observado y las observaciones.

## Fase 0 — Análisis y arquitectura (2026-11-15)

En esta fase no hay código, por lo que no hay pruebas automáticas. Se han realizado las siguientes
validaciones:

| # | Validación | Comando / procedimiento | Resultado real |
|---|---|---|---|
| 0.1 | Estado inicial del repositorio | `git status`, `git log`, `git ls-remote origin` | Rama `main` sin commits; remoto `origin` (GitHub) sin referencias; un único archivo sin seguimiento: `formato_preguntas.md`. |
| 0.2 | Herramientas del entorno local | `python3 --version`, `docker --version`, `docker compose version` | Python 3.14.8, Docker 29.9.2, Docker Compose 5.6.1. |
| 0.3 | Acceso a Docker sin root en local | `docker info`, `id -nG` | El usuario pertenece al grupo `docker`; el demonio responde (perfil seccomp y cgroupns activos). Docker en modo *rootful*. |
| 0.4 | Enlaces internos de la documentación | Script Python (fuera del repositorio) que recorre `README.md`, `CHANGELOG.md` y `docs/**/*.md` y comprueba que cada enlace Markdown relativo apunta a un archivo o directorio existente | 1.ª ejecución: 2 enlaces rotos (el directorio `informes/` aún no existía y un ejemplo literal en este documento se detectaba como enlace). Corregidos. 2.ª ejecución: 0 enlaces rotos (ver informe de la Fase 0 para la salida exacta). |
| 0.5 | Ausencia de secretos en los archivos versionados | `grep -rniE` de patrones de credenciales (`password/token/secret/api_key = valor`, cabeceras de clave privada, tokens `ghp_`) sobre `README.md`, `CHANGELOG.md`, `.gitignore` y `docs/` | Sin coincidencias (código de salida 1 de `grep`). |
| 0.6 | Diagramas Mermaid | Revisión manual de la sintaxis de los 4 diagramas (`03-arquitectura.md` ×3, `06-roadmap.md` ×1) | Revisados manualmente. **Pendiente**: comprobar que GitHub los renderiza correctamente tras el *push*. |

### Revisión del equipo (2026-11-15)

| # | Validación | Comando / procedimiento | Resultado real |
|---|---|---|---|
| 0.7 | Integridad de `formato_preguntas.md` al versionarlo | `sha256sum formato_preguntas.md`; `git show HEAD:formato_preguntas.md \| sha256sum`; `git diff --quiet HEAD -- formato_preguntas.md` | SHA-256 idéntico en disco y en Git (`af7d48262e8296a301435dc448af91f58bd84bbef21520ea3a6ef6b12d26f694`); sin diferencias. Commit `8dc4833`. |
| 0.8 | *Push* a GitHub | `git push -u origin main`, `git push -u origin fase-00-analisis` (HTTPS) | **Fallido**: `fatal: could not read Username for 'https://github.com': terminal prompts disabled`. Sin credenciales HTTPS ni CLI `gh`. Una comprobación de autenticación SSH no se ejecutó (denegada por los permisos del entorno). |
| 0.9 | Coherencia de la documentación tras incorporar los matices | Script de enlaces relativos; `grep` de `RuntimeSpec`, de ADR en estado *Propuesta* y de patrones de secretos | 15 archivos, 17 enlaces relativos, 0 rotos. `RuntimeSpec` solo aparece como nombre antiguo. Ninguna ADR en estado *Propuesta*. Sin secretos. |

No se ha realizado ninguna conexión ni operación sobre el servidor real.

## Fase 1 — Estructura y entorno aislado (2026-11-15)

Entorno: Python 3.12.16 (`.venv` de uv), Docker 29.9.2, Compose 5.6.1. Todas las ejecuciones son
locales.

| # | Prueba | Comando | Resultado real |
|---|---|---|---|
| 1.1 | Estilo y análisis estático (incluye reglas de seguridad `S`) | `uv run ruff check .`; `uv run ruff format --check .` | `All checks passed!`; `35 files already formatted` |
| 1.2 | Tests unitarios y de API | `uv run pytest -m "not integration" --cov=minipaas` | **32 passed**, 1 deselected; cobertura total **96 %** (sin cubrir: la factoría `build_app_from_env` y la creación real del cliente Docker, cubiertas por 1.3 y 1.4). 1 aviso de deprecación de Starlette sobre `TestClient` (no es un fallo) |
| 1.3 | Integración con Docker real (solo lectura) | `uv run pytest -m integration` | **1 passed**: `DockerRuntime().ping()` alcanza Docker y obtiene versión |
| 1.4 | Entorno Compose y aislamiento | `bash scripts/verify_dev_env.sh` | **7/7 OK**: `/api/health` → `status ok`; el control plane no tiene el socket; el agente no publica puertos; el agente no es accesible desde el host (8001); ninguno de los dos procesos es root; el agente rechaza peticiones sin token (401) |
| 1.5 | Agente con token incorrecto | Petición desde el contenedor `controlplane` a `http://agent:8001/health` con `Bearer` de 48 caracteres incorrectos | `HTTP 401` |
| 1.6 | Agente sin salida a Internet | Desde el contenedor `agent`: `socket.create_connection(('1.1.1.1', 443))` | `OSError`: sin salida (red `internal: true`) |
| 1.7 | Cabeceras de seguridad del panel | `curl -sI http://127.0.0.1:8000/` | `200 OK` con `Content-Security-Policy: default-src 'self'` y `X-Frame-Options: DENY` (más `nosniff` y `no-referrer`, cubiertas por tests) |
| 1.8 | Estado degradado | `docker compose ... stop agent`; `curl /api/health` | `{"status":"degraded","agent":{"reachable":false},"docker":{"reachable":false}}` tras **3,0 s** (timeout); el control plane registra `El agente no está disponible: error de conexión (ConnectTimeout)` |
| 1.9 | Consumo orientativo en reposo | `docker stats --no-stream` | controlplane **38,4 MiB**, agent **44,4 MiB** (≈ 83 MiB en total); CPU ≈ 0,2 % cada uno. Medida puntual, **no** es la verificación de RNF-07 (Fase 12) |
| 1.10 | Limpieza | `docker compose ... down`; `docker ps -a --filter label=com.docker.compose.project=minipaas-dev`; `docker network ls --filter name=minipaas` | 0 contenedores y 0 redes residuales. No se tocó ningún contenedor ajeno |
| 1.11 | Ausencia de secretos en lo versionado | `git grep --untracked -F "<token>"` excluyendo `deploy/secrets/` | El token no aparece; `deploy/secrets/` y `deploy/.env` están ignorados (`git check-ignore`) |
| 1.12 | Integridad de `formato_preguntas.md` | `sha256sum` | Sin cambios (`af7d4826…f694`) |

Errores encontrados y corregidos durante la revisión:

1. `DockerRuntime.ping()` solo capturaba `DockerException`; si Docker deja de responder después de
   crear el cliente, el SDK lanza `requests.exceptions.RequestException`, lo que habría producido un
   500 en el agente y un diagnóstico erróneo («agente no disponible» en vez de «Docker no
   disponible»). Corregido y cubierto por `tests/unit/test_docker_runtime_errors.py`.
2. El cliente HTTP del agente no se cerraba al apagar el control plane. Añadido `lifespan` y test.
3. Parámetro `settings` sin uso en `create_app` del control plane. Eliminado.
4. Colisión de nombres de módulos de test (`test_docker_runtime.py` en dos carpetas). Renombrado.

Pendiente: ejecución del CI en GitHub (requiere *push*); revisión visual del panel por el equipo.

### Revisión de la Fase 1 (2026-11-15, tras los cambios de permisos y reproducibilidad)

| # | Prueba | Comando / procedimiento | Resultado real |
|---|---|---|---|
| 1.13 | ¿Respeta Compose `uid`/`gid`/`mode` en *secrets* de archivo? | Proyecto Compose desechable (`minipaas-secret-test`, en el directorio temporal de la sesión): archivo `600` de UID 1000, contenedor con `user: 10002` y sintaxis larga con `uid/gid/mode` | **No**: Compose 5.6.1 avisa `uid/gid/mode is not supported outside Swarm mode and will be ignored`; el archivo aparece como `600 1000` y `wc` da `Permission denied`. Proyecto eliminado |
| 1.14 | Preparación de los tokens | `bash scripts/prepare_dev_env.sh` (dos veces) | 1.ª: regenera (el archivo antiguo `644` no era válido): `drwx------ 1000 deploy/secrets`, `-rw------- 10002 agent_token`, `-rw------- 10001 controlplane_token`. 2.ª: «ya existen… no se regeneran» (idempotente). `cat deploy/secrets/agent_token` desde el host: «Permiso denegado» |
| 1.15 | Exportación del bloqueo | `bash scripts/export_requirements.sh` (dos veces) y `cmp` | Genera `controlplane.txt` (17 paquetes) y `agent.txt` (22 entradas, una de ellas `pywin32` solo para Windows); segunda ejecución idéntica byte a byte |
| 1.16 | Estilo | `uv run ruff check .`; `uv run ruff format --check .` | `All checks passed!`; `37 files already formatted` |
| 1.17 | Tests unitarios y de API | `uv run pytest -m "not integration" --cov=minipaas` | **32 passed**, 1 deselected; cobertura **96 %** |
| 1.18 | Integración con Docker | `uv run pytest -m integration` | **1 passed** |
| 1.19 | Construcción de imágenes desde el bloqueo | `docker compose ... build --no-cache` y `up --build` | `pip install --no-cache-dir --require-hashes -r requirements.txt` instala exactamente las versiones exportadas (p. ej. `fastapi-0.163.1`, `docker-7.2.0`, `uvicorn-0.54.0`); `pywin32` ignorado por marcador de plataforma |
| 1.20 | Aislamiento (7 comprobaciones originales + 3 nuevas) | `bash scripts/verify_dev_env.sh` | **10/10 OK**, código de salida 0. Nuevas: secret `600` y directorio `700` en el host; el control plane lee su secret (`600`, propietario su UID 10001); el agente lee su secret (`600`, propietario su UID 10002) |
| 1.21 | Contenido de las imágenes | `importlib.metadata` dentro de cada contenedor | agent: fastapi 0.163.1, docker 7.2.0, uvicorn 0.54.0. controlplane: fastapi 0.163.1, **sin** SDK de Docker, **sin** `hatchling` |
| 1.22 | Tamaño de las imágenes | `docker image ls` | agent **208 MB** (antes 209), controlplane **203 MB** (antes 204) |
| 1.23 | Consumo orientativo | `docker stats --no-stream` | agent 42,9 MiB, controlplane 38,7 MiB (no verifica RNF-07) |
| 1.24 | Limpieza | `docker compose ... down`; borrado por ID de 5 imágenes huérfanas propias (CMD `minipaas.*`) | 0 contenedores residuales; imágenes ajenas intactas (`n8n`, `postgres`, etc.) |
| 1.25 | Credenciales para *push* (sin intentarlo) | `git config credential.helper`, `command -v gh`, variables `GH_TOKEN`/`GITHUB_TOKEN`, `~/.git-credentials` | Ninguna disponible. No se intentó el *push* |

No ejecutado: CI en GitHub (requiere *push*); revisión visual del panel.

## Fase 2 — Persistencia, aplicaciones, autenticación y auditoría (2026-11-15)

Entorno: Python 3.12 (`.venv`, `uv sync --all-extras`), Docker 29.9.2, Compose 5.6.1. Todas las
pruebas que usan base de datos emplean archivos temporales o proyectos Compose separados
(`minipaas-e2e`, `minipaas-ui`); la base de datos de desarrollo no se ha usado para pruebas.

| # | Prueba | Comando / procedimiento | Resultado real |
|---|---|---|---|
| 2.1 | Estilo y análisis estático | `uv run ruff check .`; `uv run ruff format --check .` | `All checks passed!`; 77 archivos formateados |
| 2.2 | Suite completa (unitarias, API e integración) | `uv run pytest` | **214 passed** (213 + 1 de integración), ~16–21 s (Argon2 real). 1 aviso de deprecación de Starlette (no es un fallo) |
| 2.3 | Unitarias y API con cobertura | `uv run pytest -m "not integration" --cov=minipaas` | 212 passed antes del último cambio (cobertura total **98 %**, 964 sentencias, 15 sin cubrir); tras desactivar `/docs` y `/redoc`, 213 passed |
| 2.4 | Integración con Docker | `uv run pytest -m integration` | 1 passed |
| 2.5 | Dependencias por componente | `uv lock`; `bash scripts/export_requirements.sh`; inspección de `deploy/requirements/*.txt` y de las imágenes con `importlib.util.find_spec` | El agente **no** contiene `argon2` ni `httpx` (sí `docker`); el control plane contiene `argon2` y **no** `docker`. Imagen del agente 206 MB (211 MB antes de separar extras) |
| 2.6 | Aislamiento del entorno | `bash scripts/verify_dev_env.sh` | **12/12 OK**: las 10 anteriores + `/data` es un volumen escribible por el UID 10001 + la raíz sigue en solo lectura |
| 2.7 | Extremo a extremo con contenedores reales | `bash scripts/e2e_phase2.sh` | **12/12 OK** («E2E correcto.»): crear administrador; segundo `create-admin` falla; login; 401 sin cookie; 403 sin CSRF; 201 con CSRF; `down` + `up`; la aplicación persiste; la sesión persiste; logout 204; la cookie antigua da 401. Después: 0 contenedores, 0 volúmenes y 0 imágenes `minipaas-e2e` |
| 2.8 | Recorrido del panel en navegador | Chromium *headless* + Playwright (herramienta temporal ejecutada con `uvx`, fuera del proyecto) contra un proyecto Compose separado `minipaas-ui` (puerto 8020) con un administrador de contraseña aleatoria | Ruta privada sin sesión → login; contraseña incorrecta → «Usuario o contraseña incorrectos»; login → lista; alta de dos aplicaciones; nombre repetido → «Ya existe una aplicación con ese identificador» en el campo; detalle; diálogo de borrado → borrada y vuelta a la lista; estado del sistema; móvil 390 px en modo oscuro sin desbordamiento horizontal; logout; sesión revocada desde otra pestaña → login con «Tu sesión ha caducado». Sin errores de JavaScript. Proyecto eliminado después (`down -v --rmi local`) |
| 2.9 | CSP efectiva | Mismo recorrido | La CSP `default-src 'self'` bloqueó el `eval` interno de la herramienta (`wait_for_function`): «violates the following Content Security Policy directive… 'unsafe-eval'». Confirma que la política está activa |
| 2.10 | Páginas de documentación de FastAPI | `TestClient` sobre `/docs`, `/redoc`, `/openapi.json` | Antes: `/docs` y `/redoc` 200 y cargaban `cdn.jsdelivr`. Desactivadas: 404; `/openapi.json` 200. Test `test_no_cdn_documentation_pages` |
| 2.11 | Consumo del control plane (medido durante la implementación) | `docker stats --no-stream` en reposo y con 6 logins simultáneos | Reposo 40,6 MiB; pico 48,7 MiB (el semáforo limita a 2 hashes Argon2 simultáneos); cada login 0,16–0,44 s. Medida orientativa, no verifica RNF-07 |
| 2.12 | Secretos en lo versionado | `grep` de claves privadas, tokens `ghp_` y hashes Argon2 completos en los archivos nuevos y modificados | Sin coincidencias. Ninguna base de datos (`*.sqlite3`, `*.db`) en el árbol |
| 2.13 | Integridad de `formato_preguntas.md` | `sha256sum` | Sin cambios (`af7d4826…f694`) |

Errores encontrados y corregidos durante la revisión:

1. La imagen del agente incluía `argon2-cffi` y `httpx` porque eran dependencias base. Se separaron en
   extras por componente (commit `679529d`).
2. `/docs` y `/redoc` dependían de un CDN y quedaban rotas por la CSP. Desactivadas (commit `6297e77`).
3. El navegador pedía `/favicon.ico` (404 en consola). Añadido `favicon.svg` local.
4. El script E2E dejaba sus imágenes `minipaas-e2e-*`. Ahora usa `down -v --rmi local`.
5. Durante el recorrido del panel, dos fallos eran de la propia herramienta de prueba (un selector que
   coincidía con el título del diálogo y una navegación a la misma URL sin recarga); no eran fallos
   del panel. Se comprobó en los logs del servidor (no llegó ninguna petición `DELETE`) antes de
   descartarlo.

No ejecutado: CI en GitHub (sin *push* en esta fase, por indicación del usuario).

## Renovación — Plataforma de monitorización de solo lectura (2026-11-16)

Entorno: máquina local CachyOS (kernel 7.3.0-4-cachyos), Python 3.12 (`uv sync --all-extras`),
Docker 29.9.2, Compose 5.6.1, rama `renovacion-monitorizacion`. **No se usó el servidor Ubuntu real.**
Las pruebas con Docker usaron proyectos Compose separados (`minipaas-e2e`, `minipaas-ui`).

| # | Prueba | Comando / procedimiento | Resultado real |
|---|---|---|---|
| R.1 | Estilo y análisis estático | `uv run ruff check .`; `uv run ruff format --check .` | `All checks passed!`; formato sin cambios |
| R.2 | Suite completa | `uv run pytest -q` | **48 passed**, 1 aviso (deprecación de httpx en el `TestClient` de Starlette; no es un fallo) |
| R.3 | Suite sin integración (la del CI) | `uv run pytest -q -m "not integration"` | **45 passed**, 3 deselected |
| R.4 | Extremo a extremo con Docker real | `bash scripts/e2e_monitor.sh` | **29 OK**, «E2E correcto.» Comprobaciones: despliegue y `set-password` (rechaza 3 caracteres, acepta la de prueba); 401 sin sesión en `/api/metrics` y `/api/containers`; login incorrecto 401 y correcto 204 con cookie; CPU entre 0 y 100; RAM igual a `MemTotal` del anfitrión y coherente; disco igual al de `/` (`df`); *hostname* y SO del anfitrión; uptime ±60 s; segunda consulta con medición nueva; contenedor ajeno detectado con imagen, estado, puerto y proyecto Compose; mismo número de contenedores que `docker ps`; un contenedor parado deja de aparecer; las consultas no generan eventos de modificación en `docker events`; el panel no tiene el socket; el agente no puede escribir en `/hostfs`; `/hostfs/proc` vacío; logout sin CSRF 403 y con CSRF 204; la cookie antigua da 401; tras 5 fallos la IP queda bloqueada (429) incluso con la contraseña correcta |
| R.5 | Recorrido en navegador | Proyecto Compose aislado `minipaas-ui` en el puerto 8011; `MINIPAAS_URL=http://127.0.0.1:8011 MINIPAAS_PASSWORD=... uvx --with playwright python scripts/e2e_ui.py` | **11 OK**, «UI correcta.»: error con contraseña incorrecta («Contraseña incorrecta»); tarjetas CPU, Memoria RAM, Disco y Sistema; la tabla de contenedores tiene filas; la hora de actualización cambia sola (16:15:09 → 16:15:15); sin consultas con la pestaña oculta; reanudación al volver; logout vuelve al login; el servidor ya no reconoce la sesión |
| R.6 | Datos mostrados por el panel en la máquina local | Mismo recorrido | CPU Intel i7-8550U de 8 núcleos, RAM 15,5 GiB, disco 238 GiB, CachyOS, 15 sensores de temperatura y los contenedores en ejecución, incluidos los ajenos a la plataforma (p. ej. `calendar_paas_db` con `postgres:16-alpine`) |

Fallos encontrados y corregidos durante el desarrollo (eran del script de prueba, no de la plataforma):

1. La comprobación de `docker events` falló por (a) los *healthchecks* que Docker ejecuta por su
   cuenta (eventos `exec_create`, `exec_start`, `die`) y (b) la parada del contenedor de prueba hecha
   por el propio script en el mismo segundo (`docker events --since` tiene resolución de segundos).
   Se corrigió el script.
2. La prueba de navegador necesitó ajustes: selectores, usar `browser.new_context()` y usar
   `wait_for` (`is_visible` no espera).

No ejecutado: `scripts/verify_dev_env.sh` (reconstruir el entorno `minipaas-dev` quedó bloqueado por
los permisos del modo automático); CI en GitHub (sin *push*); servidor Ubuntu real; medición de
consumo de memoria y CPU.
