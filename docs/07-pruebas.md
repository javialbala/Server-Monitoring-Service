# 7. Pruebas

> Estado del documento: **actualizado en la fase de rediseño de interfaz y limpieza (2026-11-16)**.
> Contiene la estrategia de pruebas y el registro de las pruebas **realmente ejecutadas** de la
> etapa vigente. El registro de las Fases 0 a 2 está archivado en
> [historico/registro-pruebas-etapa-paas.md](historico/registro-pruebas-etapa-paas.md). Regla: no se
> registra como superada ninguna prueba que no se haya ejecutado, y todo lo no ejecutado figura como
> pendiente.

## 7.1 Niveles de prueba

| Nivel | Qué prueba | Herramienta | Necesita Docker | Cuándo |
|---|---|---|---|---|
| **Unitarias del agente** | Cálculo de métricas con directorios falsos (`/proc`, `/sys`, `hostfs`, `disks`, `net/dev`) y conversión de contenedores | `pytest` | No | Siempre (local y CI) |
| **API del agente** | Token, rutas solo `GET`, 503 sin detalles, `/metrics` con un anfitrión falso | `pytest` + `TestClient`, cliente Docker falso | No | Siempre |
| **API del panel** | Login, cookie, 429, CSRF, `Origin`, caducidad de sesión, 401, 502, cabeceras | `pytest` + `TestClient`, agente falso | No | Siempre |
| **Integración** | Agente contra Docker real: contenedor ajeno detectado, detenido incluido, métricas coherentes | `pytest -m integration` (3 tests) | Sí | Local (el CI las excluye) |
| **Extremo a extremo** | Sistema completo en un proyecto Compose aparte: contraseña, métricas frente al anfitrión, contenedores, solo lectura, sesión, bloqueo | `bash scripts/e2e_monitor.sh` (32 comprobaciones) | Sí | Local |
| **Navegador** | Recorrido del panel real con Chromium: indicadores frente a la API, gráficas, tooltip, pausa, responsive, logout, consola | `scripts/e2e_ui.py` con Playwright vía `uvx` (22 comprobaciones) | Sí | Local |
| **Estilo y sintaxis** | Formato, errores comunes y reglas de seguridad (`S`); sintaxis de los módulos JavaScript | `ruff check`, `ruff format --check`, `node --check` | No | Siempre |
| **Aislamiento del entorno** | Permisos, usuarios, secretos, ausencia del socket en el panel | `bash scripts/verify_dev_env.sh` (12 comprobaciones) | Sí | Local |

No hay pruebas automáticas del JavaScript aparte de `node --check` (sintaxis) y el recorrido en
navegador: la lógica de `history.js` y de `format.js` se ejercita solo a través de él.

## 7.2 Cómo se prueba cada parte

| Parte | Pruebas clave |
|---|---|
| Métricas | CPU con dos lecturas falsas (incluido sin cambios → 0 %), RAM, disco con `statvfs`, uptime, modelo ausente, `os-release` en `/etc` o `/usr/lib` |
| Discos | El raíz más los extra ordenados por nombre; omitido el que está en el mismo `st_dev`; sin directorio `/disks`, solo el raíz |
| Temperatura | `coretemp` usa «Package id 0» y no los núcleos; `k10temp` con «Tctl» y sin etiquetas; alternativa `x86_pkg_temp`; sin sensores → `null`; valores absurdos descartados |
| Red | Suma de interfaces reales, sin `lo`, `veth*`, `br-*`, `docker*`, `virbr*`; archivo ilegible → `null` |
| Contenedores | Conversión de puertos, nombre sin barra, ordenación (en ejecución primero, luego por nombre), detenidos incluidos, salud deducida del texto, etiquetas de Compose, una sola llamada de lectura |
| Solo lectura | Todas las rutas del agente son `GET`; sin `/docs`; el cliente falso solo admite lo previsto; en el E2E, `docker events` no registra eventos de modificación |
| Autenticación | Contraseña correcta/incorrecta, sin contraseña configurada (503), 5 fallos → 429 incluso con la contraseña correcta, cookie `HttpOnly`/`SameSite=Strict`, caducidad por inactividad y absoluta |
| CSRF | Logout sin token → 403, `Origin` ajeno → 403 |
| `APP_PASSWORD` | Primera instalación guarda un hash `$argon2id` (600, sin texto plano); coincide; no coincide sin reset → error y hash intacto; no coincide con reset → la nueva vale y la antigua no; reset con coincidencia; ausente, vacía, corta o larga → error; `RESET` distinto de `true` = no; ningún mensaje ni log (`caplog`) contiene la contraseña; `build_app_from_env` sale con `SystemExit(1)`; login 204 con la configurada y 401 con otra |
| Navegador | Número y arco de los indicadores = API, un indicador por disco, una temperatura, filas = contenedores, detenidos marcados, sin botones de modificación, ≥ 3 muestras en gráficas, tooltip, pausa, sin scroll horizontal, logout, sin errores de consola/CSP |

## 7.3 Reglas de las pruebas con Docker

- Solo contra el **Docker local**, nunca contra el servidor real.
- Los proyectos Compose de prueba (`sms-e2e`, `sms-ui`) son distintos del de desarrollo (`sms-dev`) y se
  eliminan al terminar.
- Los contenedores de prueba son pequeños y llevan una etiqueta propia; se eliminan al terminar.

## 7.4 Pruebas implementadas

| Ubicación | Qué cubre |
|---|---|
| `tests/agent/test_host_metrics.py` | Funciones de lectura de `/proc`, `/sys`, `hostfs`, discos, temperatura y red |
| `tests/agent/test_containers.py` | Conversión de los datos de Docker, orden, salud |
| `tests/agent/test_agent_api.py` | Token, rutas, métricas con anfitrión falso, 503 |
| `tests/agent/test_agent_docker_integration.py` | 3 tests con Docker real (marcador `integration`) |
| `tests/panel/test_auth.py` | Login, 429, CSRF, `Origin`, sesiones, limitador |
| `tests/panel/test_password_config.py` | Configuración de `APP_PASSWORD` y `APP_PASSWORD_RESET` (11 funciones, 15 casos con los parametrizados) |
| `tests/panel/test_api.py` | Rutas protegidas, reenvío al agente, 502, estáticos con CSP |
| `tests/test_secrets.py` | Lectura y validación del token |
| `scripts/e2e_monitor.sh` | 46 comprobaciones de extremo a extremo (incluye las de `APP_PASSWORD`) |
| `scripts/e2e_ui.py` | 22 comprobaciones en navegador |
| `scripts/verify_dev_env.sh` | 12 comprobaciones de aislamiento del entorno |

## 7.5 Integración continua

El *workflow* de GitHub Actions ejecuta la sincronización de `deploy/requirements` con `uv.lock`,
`ruff check`, `ruff format --check` y `pytest -m "not integration" --cov=server_monitor`; **excluye** las
pruebas de integración y no ejecuta el E2E ni la prueba de navegador. **No se ha ejecutado el CI en
GitHub** para esta rama (no se ha hecho *push*).

## 7.6 Registro de la fase de rediseño de interfaz y limpieza (2026-11-16)

Entorno: máquina local CachyOS (kernel 7.3.0-4-cachyos), Docker 29.9.2, Compose 5.6.1, rama
`rediseno-interfaz-limpieza`. **No se usó el servidor Ubuntu real.**

| # | Prueba | Comando | Resultado real |
|---|---|---|---|
| D.1 | Estilo | `uv run ruff check .`; `uv run ruff format --check .` | `All checks passed!`; `51 files already formatted` |
| D.2 | Sintaxis de JavaScript | `node --check` en los 9 módulos de `web/js` | OK |
| D.3 | Suite completa | `uv run pytest -q` | **57 passed**, 1 aviso (deprecación de httpx en el `TestClient` de Starlette; no es un fallo) |
| D.4 | Suite sin integración (la del CI) | `uv run pytest -q -m "not integration"` | **54 passed**, 3 deselected |
| D.5 | Extremo a extremo con Docker real | `bash scripts/e2e_monitor.sh` | **32 OK**, «E2E correcto.» (proyecto `sms-e2e`, puerto 8010) |
| D.6 | Recorrido en navegador | `SMS_URL=http://127.0.0.1:8011 SMS_PASSWORD=... SMS_SCREENSHOTS=... uvx --with playwright python scripts/e2e_ui.py`, en un proyecto Compose aislado `sms-ui` | **22 OK**, «UI correcta.» |
| D.7 | Agente aislado | Contenedor efímero sin red, no root y sin capabilities, con `/proc/1/net/dev` montado | Se leen las interfaces reales del anfitrión (`enp0s31f6`, `wlan0`, `tailscale0`); la temperatura detectada (`coretemp: Package id 0`, 46 °C) coincide con `/sys/class/hwmon` |
| D.8 | Código muerto | `vulture --min-confidence 80` | Sin resultados. Las clases CSS «sin uso» que detectó eran generadas dinámicamente |

**Cambio posterior: configuración de la contraseña con `APP_PASSWORD` (2026-11-16, ADR-049).** Se
repitieron las pruebas con el código nuevo. Los resultados de D.1 a D.6 de arriba son los **anteriores**
a este cambio; los vigentes son estos:

| # | Prueba | Comando | Resultado real |
|---|---|---|---|
| P.1 | Estilo | `uv run ruff check .`; `uv run ruff format --check .` | `All checks passed!`; `58 files already formatted` |
| P.2 | Suite completa | `uv run pytest -q` | **68 passed**, 1 aviso (el mismo de httpx) |
| P.3 | Suite sin integración | `uv run pytest -q -m "not integration"` | **65 passed**, 3 deselected |
| P.4 | Extremo a extremo | `bash scripts/e2e_monitor.sh` | **46 OK**, «E2E correcto.» (proyecto `sms-e2e`, puerto 8010) |
| P.5 | Navegador | `SMS_URL=http://127.0.0.1:8011 APP_PASSWORD=... uvx --with playwright python scripts/e2e_ui.py`, proyecto `sms-ui` | **22 OK**, «UI correcta.» (el proyecto se borró al terminar) |
| P.6 | Sintaxis de los scripts | `bash -n scripts/*.sh`; `python3 -m py_compile scripts/e2e_ui.py`; `node --check` en `web/js` | OK |
| P.7 | `prepare_dev_env.sh` conserva `deploy/.env` | Fragmento que escribe `DOCKER_GID`, sobre una copia temporal con `APP_PASSWORD`, `DOCKER_GID` antiguo y otra línea | Se actualiza solo `DOCKER_GID`, el resto se conserva y los permisos quedan en 600; con el archivo vacío añade `DOCKER_GID` y avisa de que falta `APP_PASSWORD` (el script entero **no** se ejecutó sobre el `deploy/.env` real) |
| P.8 | `$` en `.env` | `docker compose config` con `APP_PASSWORD=a$b` y con `a$$b c` | `a$b` se interpreta como la variable `b` (queda `a`); `$$` es un `$` literal |

**Comprobaciones nuevas del E2E (`APP_PASSWORD`):** (a) `docker compose config` sin `APP_PASSWORD` falla y
pide definirla; (b) la imagen del panel ejecutada directamente sin `APP_PASSWORD` sale con código distinto
de 0 y dice «Falta APP_PASSWORD»; (c) login correcto 204 y 401 con otra contraseña; (d) el archivo de hash
empieza por `$argon2id` y no contiene la contraseña, con permisos 600; (e) `docker compose logs panel` no
contiene la contraseña; (f) reiniciar con otra `APP_PASSWORD` sin reset deja el panel parado (`exited`,
código 1) y el log explica que no coincide; (g) con `APP_PASSWORD_RESET=true` arranca con el aviso, la
nueva da 204 y la antigua 401; reiniciar cierra la sesión anterior (401); se restaura la contraseña
original y un reinicio sin `RESET` arranca con normalidad; los logs finales no contienen ninguna de las
dos contraseñas.

`verify_dev_env.sh` **no se volvió a ejecutar** con este cambio (levanta el proyecto `sms-dev`, que está
en uso); ahora necesita `APP_PASSWORD` en `deploy/.env`: **NO VERIFICADO** tras el cambio.

**Comprobaciones del E2E (D.5):** despliegue y `set-password` (rechaza 3 caracteres y acepta la de
prueba); 401 sin sesión en `/api/metrics` y `/api/containers`; login incorrecto 401 y correcto 204 con
cookie; CPU entre 0 y 100; RAM igual a `MemTotal` y coherente; disco raíz igual al de `/` (`df`);
porcentajes de los discos entre 0 y 100; temperatura igual a la del paquete del procesador (±5 °C); red
con las interfaces del anfitrión y sin `lo`/`veth`/`docker`, y total igual a la suma; *hostname* y SO del
anfitrión; uptime ±60 s; segunda consulta con medición nueva; contenedor ajeno detectado con imagen,
estado, puerto y proyecto Compose; mismo número que `docker ps -a`; los en ejecución primero; un contenedor
detenido sigue apareciendo con estado `exited`; las consultas no generan eventos de modificación en
`docker events`; el panel no tiene el socket; el agente no puede escribir en `/hostfs`; `/hostfs/proc`
vacío; logout sin CSRF 403 y con CSRF 204; la cookie antigua da 401; tras 5 fallos la IP queda bloqueada
(429) incluso con la contraseña correcta.

**Comprobaciones del navegador (D.6):** error con contraseña incorrecta; número y arco de CPU y RAM
iguales a los de la API; un indicador por disco y arco igual al de la API; una sola temperatura general;
7 filas de contenedores, como la API; los 2 detenidos marcados; sin botones para iniciar, parar o
borrar; la hora de actualización cambia sola; 3 muestras reales en las gráficas; líneas dibujadas;
tooltip al pasar el cursor; sin consultas con la pestaña oculta y reanudación al volver (la pestaña
oculta se **simula** con `visibilitychange`, porque Chromium sin interfaz no la oculta; la versión anterior
del script no era fiable en ese punto y se corrigió); sin scroll horizontal a 1024 y 390 px; logout y
sesión no reconocida por el servidor después; sin errores de JavaScript ni de CSP en la consola.

### Fallos encontrados y corregidos durante la fase

La versión anterior de `e2e_ui.py` no comprobaba de forma fiable la pausa con la pestaña oculta (se
corrigió para simular el evento `visibilitychange`).

### Comprobaciones finales del entorno

| Comprobación | Resultado |
|---|---|
| `bash scripts/verify_dev_env.sh` con el entorno renombrado | **12/12 OK** (panel sin socket Docker; agente sin puertos publicados y no accesible desde el anfitrión; ningún contenedor como root; el agente rechaza peticiones sin token; secrets 600/700 con su UID; `/data` volumen escribible por el UID 10001; raíz del panel en solo lectura) |
| Construcción desde un entorno limpio siguiendo [08-guia-desarrollo.md](08-guia-desarrollo.md) | **Correcta**: copia limpia de los archivos versionados (sin `.venv`, secretos ni cachés) en un directorio temporal, con `COMPOSE_PROJECT_NAME=sms-clean` y `SMS_PORT=8020` para no chocar con el entorno de desarrollo; pasos 1–5 de la guía sin cambios: `uv sync --all-extras`; ruff OK; 54 tests OK; `prepare_dev_env.sh` creó secretos y `.env`; `compose up --build --wait` con ambos contenedores *healthy*; `set-password --stdin` guardó el hash; login 204; `/api/metrics` con datos reales (CPU, RAM, disco Sistema, temperatura coretemp 43 °C, 3 interfaces de red); `/api/containers` con 7 contenedores; `/` 200. Después se borró todo (proyecto, imágenes, volumen y copia) |

### Pendiente de ejecutar o de comprobar

| Pendiente | Motivo |
|---|---|
| Desplazamiento de la gráfica con la ventana de 10 min llena | Requiere 10 min reales en el navegador |
| Tooltip en pantalla táctil | No probado |
| CI en GitHub | Sin *push* |
| Servidor Ubuntu real | Sin autorización; solo se probó en CachyOS |
| Consumo de memoria y CPU; contraste y daltonismo automatizados | No medidos |

## 7.7 Registro de la renovación (2026-11-16, etapa anterior)

Se conserva como evidencia. Usaba los nombres de su época (`minipaas`, `controlplane`, proyectos
`minipaas-e2e` y `minipaas-ui`); las cifras corresponden a aquella versión del código y no son las
actuales (48 tests, E2E de 29 y navegador de 11 comprobaciones).

| # | Prueba | Resultado real |
|---|---|---|
| R.1 | `ruff check` y `ruff format --check` | Sin errores |
| R.2 | `pytest -q` | 48 passed, 1 aviso (deprecación de httpx) |
| R.3 | `pytest -q -m "not integration"` | 45 passed, 3 deselected |
| R.4 | `scripts/e2e_monitor.sh` | 29 OK, «E2E correcto.» |
| R.5 | `scripts/e2e_ui.py` en un proyecto aislado | 11 OK, «UI correcta.» |
| R.6 | `scripts/verify_dev_env.sh` (entorno reconstruido, 2026-11-16) | 12/12 OK: health, panel sin socket, agente sin puertos y no accesible desde el host, ningún contenedor como root, agente rechaza sin token (401), secrets 600/700 con su UID, `/data` escribible por el UID 10001 y raíz del panel en solo lectura |

Fallos de entonces, corregidos: la comprobación de `docker events` falló por los *healthchecks* que
Docker ejecuta por su cuenta y por una parada hecha en el mismo segundo (el script se ajustó); la prueba
de navegador necesitó ajustes de selectores y de esperas.

## 7.8 No probado

- El servidor Ubuntu real (la autorización no se ha pedido ni dado).
- Consumo de memoria y CPU de los contenedores; carga con muchos contenedores.
- Discos extra reales montados en `/disks/*` y sensores `k10temp` (AMD) o `x86_pkg_temp`: solo con
  directorios falsos.
- La presentación en navegador de los estados «Con fallos» y «Arrancando» y del aviso de fallo del agente.
