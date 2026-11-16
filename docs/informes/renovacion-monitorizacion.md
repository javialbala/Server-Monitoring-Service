# Informe de cierre — Renovación: plataforma de monitorización de solo lectura

> Informe autocontenido para la memoria universitaria y la presentación.
> Proyecto: **MiniPaaS** (nombre histórico) — plataforma web ligera de monitorización y consulta.
> Asignatura: GSASD. Fecha: **2026-11-16**. Rama: `renovacion-monitorizacion` (creada desde `main`,
> es decir, desde la Fase 2).
> Estado: **terminada y verificada en local; pendiente de aprobación del equipo.** No se ha hecho
> *push* ni se ha probado en el servidor Ubuntu real.

Leyenda: **Implementado** (código escrito), **Verificado** (prueba ejecutada con resultado real),
**Pendiente** (no hecho o no comprobado).

---

## Resumen

El proyecto nació como una PaaS ligera para desplegar y gestionar aplicaciones en contenedores
(Fases 0 a 3). El 2026-11-16 el usuario aprobó **cambiar el objetivo**: ahora es una **plataforma web
ligera, solo de monitorización y consulta**, que muestra:

- las **métricas del servidor anfitrión**: CPU, RAM, disco y, además, sistema operativo, kernel,
  *hostname*, tiempo en marcha y temperaturas;
- los **contenedores Docker en ejecución**: nombre, imagen, estado, puertos, fecha de creación y
  proyecto/servicio de Compose, incluidos los **creados fuera de la plataforma**.

Está **prohibido** crear, iniciar, parar, borrar o modificar contenedores, imágenes o volúmenes. El
resultado es un sistema de dos procesos (panel y agente), sin base de datos y sin dependencias nuevas,
con **1 492 líneas de código fuente** (la Fase 2 tenía 2 967 y la Fase 3, 7 661), 48 tests, una prueba
extremo a extremo con Docker real (29 comprobaciones) y una prueba en navegador (11 comprobaciones),
todas superadas en la máquina local.

### Motivo del cambio de objetivo

El objetivo PaaS (catálogo, despliegues, revisiones, *rollback*, volúmenes, redes, límites) era
**demasiado amplio y complejo para un proyecto universitario que el equipo debe comprender,
explicar y demostrar**. La Fase 3 sola ya sumaba unas 7 700 líneas de código fuente y 4 500 de
pruebas, y quedaban diez fases. Se prioriza algo **funcional, sencillo y seguro**.

### Decisiones tomadas por el usuario (2026-11-16)

1. Nuevo objetivo: monitorización y consulta, solo lectura (ADR-036).
2. Rama nueva desde `main` (Fase 2, la última aprobada), no desde la Fase 3 (sin aprobar). La rama
   `fase-03-motor-despliegue` y su informe y ADR 025 a 035 se conservan intactos, pero no se
   aprobaron y no forman parte de esta rama.
3. Se mantiene la separación en dos procesos: panel sin socket Docker y agente con socket y solo
   lectura (ADR-037). Alternativa descartada: un solo proceso con el socket (equivaldría a dar root
   al proceso expuesto).
4. Se elimina SQLite: hash Argon2id en un archivo y sesiones en memoria (ADR-039).
5. Disco: montar el `/` del anfitrión en solo lectura y sin submontajes (ADR-038). Alternativa
   descartada: medir el disco que usa Docker, que podía no coincidir con el disco raíz.
6. Métricas con la biblioteca estándar, sin `psutil` (ADR-040).
7. Actualización por consulta HTTP cada 5 s, sin WebSockets (ADR-041).
8. Contraseña única de 4 a 128 caracteres (el mínimo de 4 se acordó expresamente).
9. Siguiente fase: mejora de la interfaz; después, despliegue en el servidor real con autorización.

---

## 1. Funcionalidades reutilizadas

Procedentes de la Fase 2 (y la Fase 1), adaptadas a la renovación:

| Funcionalidad | Cómo se reutiliza |
|---|---|
| Estructura de dos procesos (panel y agente) en un único paquete `minipaas` | Igual; el agente pasa de «ejecutar operaciones» a «solo consultar» |
| Token compartido como *secret* de archivo, una copia 600 por componente (ADR-014) | Igual; se mantiene `common/secrets.py` |
| Autenticación con Argon2id, cookie `HttpOnly`/`SameSite=Strict`, sesión con identificador guardado como SHA-256 y caducidad | Se simplifica: contraseña única, sesiones en memoria |
| CSRF (token por sesión + comprobación de `Origin`) | Igual; ahora solo afecta a logout y al login (`Origin`) |
| Límite de intentos de login (5 en 15 min) | Igual, solo por IP |
| Cabeceras de seguridad y CSP `default-src 'self'`; sin `/docs` | Igual |
| Cliente HTTP del agente (`agent_client.py`) | Reducido a dos consultas |
| `compose.dev.yaml` endurecido (red interna, `read_only`, `cap_drop: ALL`, `no-new-privileges`, no root, `group_add`) | Igual; se añade el montaje `/hostfs` |
| Dockerfiles con usuarios sin privilegios; `deploy/requirements` con hashes | Igual (el Dockerfile del panel solo cambia ligeramente) |
| Scripts `prepare_dev_env.sh`, `export_requirements.sh` y CI de GitHub Actions | Sin cambios |
| Panel web en HTML/CSS/JS sin framework (`dom.js`, `api.js`, `session.js`, `format.js`, `app.js`, login) | Adaptado; nueva vista `dashboard.js` |
| Documentación, ADR 001 a 024 e informes de las Fases 0 a 2 | Conservados; las ADR obsoletas se marcan como sustituidas |

## 2. Funcionalidades eliminadas o simplificadas

| Elemento | Qué pasó | Motivo |
|---|---|---|
| SQLite, migraciones, repositorios, conexiones y transacciones | **Eliminados** | Solo había que guardar una contraseña (ADR-039) |
| Aplicaciones (CRUD, slug, estado lógico), `services/`, `schemas.py`, `clock.py` | **Eliminados** | Ya no hay aplicaciones |
| Auditoría en base de datos | **Sustituida** por el log `minipaas.access` | Sin BD |
| Usuarios y `create-admin` | **Sustituidos** por una contraseña única y `set-password` | Sencillez |
| Sesiones en SQLite | **Simplificadas**: en memoria | Sin BD; se pierden al reiniciar |
| Límite de intentos por usuario | **Simplificado**: solo por IP | Sin usuario |
| Agente con `docker_runtime.py` (crear/borrar contenedores), `naming.py` | **Eliminados** | Solo lectura |
| Vistas del panel de aplicaciones (`apps`, `app-detail`, `app-form`, `status`, `ui.js`) | **Eliminadas** | Sustituidas por `dashboard.js` |
| Variable `MINIPAAS_DB_PATH` y `scripts/e2e_phase2.sh` | **Eliminadas** | Obsoletas |
| 214 tests de la Fase 2 | Sustituidos por 48 | Menos código que probar |
| Fase 3 (motor de despliegue) y Fases 4 a 13 planificadas | **No se incluyen / canceladas** | Fuera del nuevo objetivo |

## 3. Arquitectura final

```text
Navegador ──HTTP──▶ Panel (minipaas.controlplane) ──HTTP + token Bearer──▶ Agente (minipaas.agent)
 cookie de            sin socket Docker, no root,             red interna, sin puertos   │
 sesión               read_only, cap_drop ALL,                único con el socket        ├─▶ Docker: containers(status=running), version
                      volumen /data (password_hash)                                      ├─▶ /proc y /sys (valores del anfitrión)
                                                                                         └─▶ /hostfs (/ del anfitrión, solo lectura)
```

- **Panel** (`minipaas.controlplane`, puerto 8000, publicado solo en `127.0.0.1`): contraseña,
  sesiones, CSRF, límite de intentos, cabeceras de seguridad, archivos estáticos y reenvío de
  `/api/metrics` y `/api/containers`.
- **Agente** (`minipaas.agent`, puerto 8001, red interna): `GET /health`, `GET /metrics`,
  `GET /containers`, todas con token Bearer comparado con `hmac.compare_digest`.
- **Datos persistentes:** solo `/data/password_hash` en un volumen. Sin SQLite.
- Detalle en `docs/03-arquitectura.md`; API en `docs/api.md`.

## 4. Funcionamiento de la monitorización

1. El usuario inicia sesión con la contraseña. El panel crea una sesión en memoria y envía la cookie.
2. `dashboard.js` pide `GET /api/metrics` y `GET /api/containers` y pinta cuatro tarjetas (CPU, RAM,
   Disco, Sistema) y una tabla de contenedores, usando solo `textContent`.
3. La siguiente consulta se programa **5 s después de terminar la anterior** con `setTimeout`
   encadenado (nunca se solapan peticiones).
4. Con la pestaña oculta (`visibilitychange`) se pausa; al volver se reanuda y se actualiza al momento.
5. Al cerrar sesión o recibir un 401 se detiene y vuelve el formulario de acceso.
6. Si el agente o Docker fallan, se avisa «No se pudo actualizar; se muestran los últimos datos».

Alternativa descartada: WebSockets, por su mayor complejidad (ADR-041).

## 5. Obtención de métricas

Todo con la biblioteca estándar de Python, sin `psutil` (ADR-040). Dentro de un contenedor,
`/proc` y `/sys` muestran los valores del anfitrión, y `/hostfs` es el `/` del anfitrión.

| Métrica | Fuente y cálculo |
|---|---|
| CPU % | Dos lecturas de la línea `cpu` de `/proc/stat` separadas 0,5 s; `100 × (1 − Δidle/Δtotal)` con `idle = idle + iowait` |
| Núcleos y modelo | `os.cpu_count()` y `model name` de `/proc/cpuinfo` (`null` si no existe, p. ej. en ARM) |
| RAM | `/proc/meminfo`: `usada = MemTotal − MemAvailable`; porcentaje sobre el total |
| Disco | `os.statvfs("/hostfs")`; porcentaje calculado como lo hace `df` (`usado / (usado + libre)`) |
| SO | `PRETTY_NAME` de `/hostfs/etc/os-release` (o `usr/lib/os-release`) |
| *Hostname* | `/hostfs/etc/hostname` |
| Kernel y arquitectura | `os.uname()` (el kernel es compartido con el anfitrión) |
| Uptime | `/proc/uptime` |
| Temperaturas | `/sys/class/thermal/thermal_zone*/{type,temp}` (milésimas de grado → °C) |

Las funciones reciben las rutas como parámetro para probarlas con directorios falsos. El montaje
`/hostfs` usa `bind.recursive: disabled`, así que no incluye `/proc`, `/sys`, `/home` ni otros
discos (ADR-038). Cada llamada a `/metrics` tarda unos 0,5 s por la medición de CPU; el agente
ejecuta las rutas en hilos, así que no bloquea otras peticiones.

## 6. Detección de contenedores

- Una **única llamada de solo lectura**: `client.api.containers(filters={"status": "running"})`. Sin
  `inspect` por contenedor. Para `/health` se usa además `version`.
- Detecta **todos** los contenedores en ejecución, sean de la plataforma o no: no se filtra por
  etiquetas (en la etapa PaaS se usaba la etiqueta `minipaas.managed`).
- Se devuelve: identificador corto, nombre (sin la barra inicial), imagen, estado, texto de estado,
  fecha de creación (UTC), puertos (publicados o no) y las etiquetas `com.docker.compose.project` y
  `com.docker.compose.service`. Orden por nombre. Los contenedores parados no aparecen.
- Si Docker falla: 503 «Docker no está disponible» sin detalles internos.

## 7. Seguridad implementada

| Medida | Estado |
|---|---|
| Panel sin socket de Docker; solo el agente lo monta | Verificado (E2E) |
| Agente en red interna, sin puertos, token Bearer en todas las rutas, solo `GET`, sin `/docs`, no ejecuta comandos | Verificado (tests y E2E) |
| Solo lectura: solo se llama a `containers` y `version`; las consultas no generan eventos de modificación en `docker events` | Verificado (tests con cliente falso que falla ante cualquier otra operación; E2E) |
| `/hostfs` solo lectura y sin submontajes; el agente no puede escribir | Verificado (E2E) |
| Ningún contenedor privilegiado, root, con capabilities o sistema de archivos escribible (salvo `/data` y `tmpfs`) | Configuración revisada; `verify_dev_env.sh` pendiente de reejecutar |
| Contraseña única de 4 a 128 caracteres con Argon2id; el hash en `/data/password_hash` (600) | Verificado (tests) |
| 5 fallos en 15 min por IP → 429 + `Retry-After`, incluso con la contraseña correcta | Verificado (tests y E2E) |
| Cookie `HttpOnly`, `SameSite=Strict`, `Secure` configurable (`MINIPAAS_COOKIE_SECURE`); token de 256 bits guardado como SHA-256 | Verificado (tests) |
| Caducidad de sesión: 30 min de inactividad y 8 h absolutas | Verificado (tests con reloj simulado) |
| CSRF por sesión (`X-CSRF-Token`) en logout y rechazo de `Origin` ajeno | Verificado (tests y E2E) |
| CSP `default-src 'self'`, sin `innerHTML` con datos del servidor, `nosniff`, `X-Frame-Options: DENY` | Verificado (test de cabeceras; revisión del JS) |
| Registro de accesos con `logging` (`minipaas.access`), sin contraseñas | Implementado; sin prueba automática del contenido del log |

Limitación importante (ADR-037): montar el socket con `:ro` **no** limita la API de Docker; la
solo-lectura la garantiza el código del agente, no Docker.

## 8. Pruebas realizadas y resultados

Entorno: máquina local CachyOS (kernel 7.3.0-4-cachyos), Docker 29.9.2, Compose 5.6.1, Python 3.12.
**No se usó el servidor Ubuntu real.** Fecha: 2026-11-16.

| Comando | Resultado real |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | Sin cambios pendientes |
| `uv run pytest -q` | **48 passed**, 1 aviso (deprecación de httpx en el `TestClient` de Starlette) |
| `uv run pytest -q -m "not integration"` | **45 passed**, 3 deselected |
| `bash scripts/e2e_monitor.sh` | **29 OK**, «E2E correcto.» |
| `MINIPAAS_URL=http://127.0.0.1:8011 MINIPAAS_PASSWORD=... uvx --with playwright python scripts/e2e_ui.py` (proyecto Compose aislado `minipaas-ui`, puerto 8011) | **11 OK**, «UI correcta.» |

**Qué comprueba `e2e_monitor.sh` (29):** levantar el proyecto `minipaas-e2e`; `set-password` rechaza
3 caracteres y acepta la de prueba; 401 sin sesión en `/api/metrics` y `/api/containers`; login
incorrecto 401 y correcto 204 con cookie; CPU entre 0 y 100 y núcleos > 0; RAM total igual a
`MemTotal`; usada + disponible = total; disco igual al de `/` según `df` y porcentaje entre 0 y 100;
*hostname* y SO del anfitrión; uptime cercano (±60 s); una segunda consulta devuelve una medición
nueva; el contenedor creado fuera de la plataforma se detecta con imagen, estado, puerto y proyecto
Compose correctos; el mismo número de contenedores que `docker ps`; solo en ejecución; un contenedor
parado deja de aparecer; las consultas no generan eventos de modificación en Docker; el panel no
tiene el socket; el agente no puede escribir en `/hostfs`; `/hostfs/proc` vacío; logout sin CSRF 403 y
con CSRF 204; la cookie antigua da 401; tras 5 fallos queda bloqueada la IP (429) incluso con la
contraseña correcta.

**Qué comprueba `e2e_ui.py` (11):** error con contraseña incorrecta («Contraseña incorrecta»); se ven
las tarjetas CPU, Memoria RAM, Disco y Sistema; la tabla de contenedores tiene filas; la hora de
actualización cambia sola («Última actualización: 16:15:09» → «16:15:15»); con la pestaña oculta no se
hacen consultas; al volver se reanuda; al cerrar sesión vuelve el login; el servidor ya no reconoce la
sesión.

**Datos que mostró el panel en la máquina local:** CPU Intel i7-8550U de 8 núcleos, RAM 15,5 GiB,
disco 238 GiB, CachyOS, 15 sensores de temperatura y los contenedores en ejecución, incluidos
contenedores ajenos (p. ej. `calendar_paas_db` con `postgres:16-alpine`).

**Fallos encontrados y corregidos durante el desarrollo** (del script de prueba, no de la plataforma):

1. La comprobación de `docker events` falló la primera vez por dos motivos ajenos a la plataforma:
   (a) los *healthchecks* que Docker ejecuta por su cuenta generan eventos (`exec_create`,
   `exec_start`, `die`) y (b) el propio script paraba el contenedor de prueba en el mismo segundo y
   `docker events --since` tiene resolución de segundos. Se corrigió el script.
2. La prueba de navegador necesitó ajustes: selectores, usar `browser.new_context()` y `wait_for`
   (porque `is_visible` no espera).

**No ejecutado:** `scripts/verify_dev_env.sh` (reconstruir el entorno `minipaas-dev` quedó bloqueado por
los permisos del modo automático; sus comprobaciones de seguridad están cubiertas solo en parte por
`e2e_monitor.sh`); CI en GitHub; servidor Ubuntu real; medición de consumo de memoria y CPU.

**Tamaño del código (líneas, sin contar el favicon):**

| Versión | Código fuente | Archivos | Pruebas |
|---|---|---|---|
| Fase 2 (`a1d62f4`) | 2 967 | 52 | 1 651 |
| Fase 3 (`f96a6a3`, rama no aprobada) | 7 661 | 75 | 4 458 |
| **Renovación (HEAD)** | **1 492** | **29** | **655** |

Diferencia respecto a la Fase 2: 82 archivos, +1 663 / −3 966 líneas.

## 9. Archivos modificados

Obtenidos con `git diff --name-status a1d62f4 HEAD` (código, pruebas, scripts y despliegue) más los
de documentación de esta etapa. Total del diff de código respecto a la Fase 2: 82 archivos, +1 663 /
−3 966 líneas.

### Creados (código, pruebas y scripts)

- `scripts/e2e_monitor.sh`
- `scripts/e2e_ui.py`
- `src/minipaas/agent/containers.py`
- `src/minipaas/agent/host_metrics.py`
- `src/minipaas/controlplane/routes.py`
- `src/minipaas/controlplane/web/js/views/dashboard.js`
- `tests/agent/conftest.py`
- `tests/agent/fakes.py`
- `tests/agent/test_agent_api.py`
- `tests/agent/test_agent_docker_integration.py`
- `tests/agent/test_containers.py`
- `tests/agent/test_host_metrics.py`
- `tests/panel/conftest.py`
- `tests/panel/test_api.py`
- `tests/panel/test_auth.py`

Documentación creada: `docs/informes/renovacion-monitorizacion.md` (este informe).

### Modificados (código, pruebas, scripts y despliegue)

- `deploy/Dockerfile.controlplane`
- `deploy/compose.dev.yaml`
- `src/minipaas/agent/config.py`
- `src/minipaas/agent/main.py`
- `src/minipaas/controlplane/agent_client.py`
- `src/minipaas/controlplane/config.py`
- `src/minipaas/controlplane/main.py`
- `src/minipaas/controlplane/manage.py`
- `src/minipaas/controlplane/security/passwords.py`
- `src/minipaas/controlplane/security/rate_limit.py`
- `src/minipaas/controlplane/security/sessions.py`
- `src/minipaas/controlplane/web/css/styles.css`
- `src/minipaas/controlplane/web/index.html`
- `src/minipaas/controlplane/web/js/api.js`
- `src/minipaas/controlplane/web/js/app.js`
- `src/minipaas/controlplane/web/js/format.js`
- `src/minipaas/controlplane/web/js/session.js`
- `src/minipaas/controlplane/web/js/views/login.js`

Documentación modificada en esta etapa (sin commit todavía):

- `README.md`
- `CHANGELOG.md`
- `docs/README.md`
- `docs/01-vision-y-alcance.md`
- `docs/02-requisitos.md`
- `docs/03-arquitectura.md`
- `docs/04-seguridad.md`
- `docs/05-estrategia-pruebas.md`
- `docs/06-roadmap.md`
- `docs/07-estado-del-arte.md`
- `docs/08-estructura-proyecto.md`
- `docs/api.md`
- `docs/decisiones.md`
- `docs/guia-desarrollo.md`
- `docs/registro-pruebas.md`

### Eliminados

- `scripts/e2e_phase2.sh`
- `src/minipaas/agent/docker_runtime.py`
- `src/minipaas/common/naming.py`
- `src/minipaas/controlplane/api/__init__.py`
- `src/minipaas/controlplane/api/applications.py`
- `src/minipaas/controlplane/api/auth.py`
- `src/minipaas/controlplane/api/deps.py`
- `src/minipaas/controlplane/api/health.py`
- `src/minipaas/controlplane/clock.py`
- `src/minipaas/controlplane/db/__init__.py`
- `src/minipaas/controlplane/db/connection.py`
- `src/minipaas/controlplane/db/migrations.py`
- `src/minipaas/controlplane/db/migrations/0001_initial.sql`
- `src/minipaas/controlplane/repositories/__init__.py`
- `src/minipaas/controlplane/repositories/applications.py`
- `src/minipaas/controlplane/repositories/audit.py`
- `src/minipaas/controlplane/repositories/sessions.py`
- `src/minipaas/controlplane/repositories/users.py`
- `src/minipaas/controlplane/schemas.py`
- `src/minipaas/controlplane/services/__init__.py`
- `src/minipaas/controlplane/services/applications.py`
- `src/minipaas/controlplane/services/audit.py`
- `src/minipaas/controlplane/services/auth.py`
- `src/minipaas/controlplane/web/js/ui.js`
- `src/minipaas/controlplane/web/js/views/app-detail.js`
- `src/minipaas/controlplane/web/js/views/app-form.js`
- `src/minipaas/controlplane/web/js/views/apps.js`
- `src/minipaas/controlplane/web/js/views/status.js`
- `tests/api/test_agent_api.py`
- `tests/api/test_applications_api.py`
- `tests/api/test_audit_api.py`
- `tests/api/test_auth_api.py`
- `tests/api/test_controlplane_api.py`
- `tests/api/test_csrf_api.py`
- `tests/api/test_persistence_api.py`
- `tests/conftest.py`
- `tests/integration/test_docker_runtime.py`
- `tests/unit/test_audit.py`
- `tests/unit/test_database.py`
- `tests/unit/test_docker_runtime_errors.py`
- `tests/unit/test_manage.py`
- `tests/unit/test_migrations.py`
- `tests/unit/test_naming.py`
- `tests/unit/test_passwords.py`
- `tests/unit/test_rate_limit.py`
- `tests/unit/test_repositories.py`
- `tests/unit/test_session_service.py`
- `tests/unit/test_settings.py`
- `tests/unit/test_slug.py`

No se han tocado `docs/informes/fase-00.md` a `fase-02.md`, `docs/bibliografia.md` ni
`formato_preguntas.md`.

## 10. Dependencias añadidas o eliminadas

**Ninguna.** `pyproject.toml`, `uv.lock` y `deploy/requirements/*.txt` no cambian. Las dependencias
siguen siendo: `fastapi`, `uvicorn`, `httpx`, `argon2-cffi` y `docker`. Deja de usarse el módulo
estándar `sqlite3`. Playwright se usa solo para la prueba de
navegador mediante `uvx --with playwright` y **no** es dependencia del proyecto.

Variables de entorno: panel `MINIPAAS_AGENT_TOKEN_FILE`, `MINIPAAS_AGENT_URL`
(`http://agent:8001`), `MINIPAAS_PASSWORD_HASH_FILE` (`/data/password_hash`),
`MINIPAAS_COOKIE_SECURE` (`false`); agente `MINIPAAS_AGENT_TOKEN_FILE` y `MINIPAAS_HOSTFS` (`/` por
defecto, `/hostfs` en Compose). Se elimina `MINIPAAS_DB_PATH`.

## 11. Problemas pendientes

| Problema | Detalle |
|---|---|
| Red del anfitrión no implementada | Requeriría `network_mode: host` para el agente, que se evita por seguridad; solo se mostraría la red del contenedor |
| El socket de Docker da acceso equivalente a root al agente | La solo-lectura la garantiza el código, no Docker. Mejora posible: un proxy del socket (nueva dependencia o componente; decisión futura) |
| Temperaturas | Se listan todas las `thermal_zone`, con nombres repetidos (p. ej. `acpitz`) y algunas a 0 °C; habría que filtrarlas o agruparlas |
| Sesiones y limitador en memoria | Válidos para un solo proceso; se pierden al reiniciar |
| IP del cliente detrás de un proxy inverso | El límite usa la IP de la conexión; habría que tomar la de una cabecera de confianza |
| Nombre del proyecto y paquete | Siguen siendo MiniPaaS / `minipaas` / `controlplane`; renombrarlos es decisión del equipo |
| Latencia de `/metrics` | Cada llamada tarda unos 0,5 s por la medición de CPU |
| No probado en el servidor Ubuntu real | Solo CachyOS con Docker 29.9.2 |
| `verify_dev_env.sh` sin reejecutar | Pendiente de reconstruir `minipaas-dev` y comprobar |
| Aviso de deprecación de httpx | En el `TestClient` de Starlette; no es un fallo |
| El CI excluye las pruebas de integración | Y no ejecuta el E2E ni la prueba de navegador; el CI no se ha ejecutado en GitHub (sin *push*) |
| Contraseña mínima de 4 caracteres | Decisión del equipo; débil si el panel se expone a Internet |
| Consumo de recursos no medido | RNF-M11 sigue siendo un objetivo de diseño |

## 12. Siguiente fase recomendada

1. **Mejora de la interfaz** (la pide el usuario): revisión visual y de usabilidad del panel (diseño,
   barras de uso, colores de estado, adaptación a móvil, textos, accesibilidad básica), sin cambiar la
   API ni el modelo de seguridad, y actualizando `e2e_ui.py`.
2. Después, **despliegue en el servidor Ubuntu real**, solo con autorización expresa del usuario:
   probar antes en Ubuntu o en una VM, reejecutar `verify_dev_env.sh`, decidir HTTPS y
   `MINIPAAS_COOKIE_SECURE=true`, medir el consumo y escribir la guía de instalación.
3. Cierre académico: memoria y presentación.

Pendiente de aprobación del equipo antes de fusionar la rama `renovacion-monitorizacion`.
