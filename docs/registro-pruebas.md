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
| 0.7 | Integridad de `formato_preguntas.md` al versionarlo | `sha256sum formato_preguntas.md`; `git show HEAD:formato_preguntas.md \| sha256sum`; `git diff --quiet HEAD -- formato_preguntas.md` | SHA-256 idéntico en disco y en Git (`af7d48262e8296a301435dc448af91f58bd84bbef21520ea3a6ef6b12d26f694`); sin diferencias. Commit `7275902`. |
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
