# Informe de cierre: Rediseño de interfaz y limpieza

> Informe autocontenido para la memoria universitaria y la presentación.
> Proyecto: **Server Monitoring Service** (antes MiniPaaS). Asignatura: GSASD. Fecha: **2026-11-16**.
> Rama: `rediseno-interfaz-limpieza`. No se ha hecho *commit* de esta fase ni *push*.
> Estado: **terminada y probada en local; pendiente de aprobación del usuario**. No se ha probado en el servidor Ubuntu real.

## Resumen

El proyecto era una plataforma de monitorización de solo lectura (la renovación del mismo día) con una
interfaz de tarjetas y un backend que devolvía datos mínimos. Esta fase hace cuatro cosas (y una quinta añadida al final, ver el punto 5):

1. **Renombra** todo a *Server Monitoring Service* (paquete `server_monitor`, componente `panel`,
   variables `SMS_*`).
2. **Amplía el backend del agente**: varios discos, una temperatura general, la red del anfitrión,
   todos los contenedores (también los detenidos) y marcas de tiempo con milisegundos.
3. **Rediseña la interfaz**: tema oscuro sobrio, indicadores circulares, gráficas de líneas en SVG propio
   con histórico de 10 minutos en el navegador, fuentes e iconos autoalojados.
4. **Limpia el código**: sin carpetas vacías, sin módulos muertos, sin cachés, sin dependencias nuevas.

5. **Cambia la configuración de la contraseña** (añadido al final de la fase, aprobado por el usuario):
   se define con la variable `APP_PASSWORD` y se elimina el comando `set-password` (ADR-049).

Además se **reorganiza toda la documentación** (apartado 5): la de la etapa PaaS se archiva en
`docs/historico/` y la vigente se numera de 01 a 11.

Cifras: `src/` tiene 2 518 líneas (sin contar fuentes, SVG ni licencias; la renovación tenía 1 492; el
aumento es el frontend: `charts.js` 216, `dashboard.js` 378, `styles.css` 457); los tests, 950 líneas y
68 casos tras el cambio de contraseña (antes, 823 líneas y 57 casos); `ruff` sin errores; extremo a extremo 46
comprobaciones (antes, 32); navegador 22 comprobaciones, todas superadas **en la máquina local** (CachyOS, Docker 29.9.2, Compose 5.6.1).

### Decisiones del usuario (todas aprobadas el 2026-11-16)

1. **Contenedores detenidos visibles**: se listan todos, con la misma llamada de lectura sin filtro
   (ADR-043).
2. **Discos declarados en Compose**: el raíz más los que el administrador monte en solo lectura en
   `/disks/<nombre>` (ADR-044).
3. **Renombrado** a Server Monitoring Service (ADR-042).
4. **Temperatura general = paquete del procesador** (ADR-045).

Otras decisiones técnicas de la fase, derivadas de las anteriores: la red del anfitrión vía
`/proc/1/net/dev` como único archivo de solo lectura (ADR-046); gráficas e indicadores en SVG propio con
histórico en el navegador (ADR-047); fuentes e iconos autoalojados por la CSP (ADR-048).

### Leyenda de estados

En todo el informe cada afirmación lleva uno de estos estados:

| Estado | Significado |
|---|---|
| **IMPLEMENTADO** | El código existe y se ha leído, pero no hay una prueba ejecutada que lo demuestre por sí sola |
| **PROBADO** | Hay una prueba ejecutada con resultado real (comando y salida en el apartado 9) |
| **PENDIENTE** | No hecho o no ejecutado todavía; hay que hacerlo |
| **NO VERIFICADO** | No se ha comprobado y no se sabe si funciona (o se ha elegido sin base) |

### Tabla de estado

| Elemento | Estado | Evidencia o matiz |
|---|---|---|
| Renombrado (paquete, variables, Compose, usuarios, cookie...) | **IMPLEMENTADO y PROBADO** | tests, E2E y navegador con los nombres nuevos |
| Contraseña desde `APP_PASSWORD`: primera instalación, coincide, no coincide, no coincide + reset, falta | **IMPLEMENTADO y PROBADO** | 15 casos de test y 14 comprobaciones nuevas del E2E con Docker real (apartado 9) |
| La contraseña no aparece en logs, mensajes de error ni en el archivo de hash | **PROBADO** | `caplog` en tests; `docker compose logs panel` y el archivo de hash en el E2E |
| Contraseña visible con `docker inspect` (variable de entorno) | Riesgo residual **aceptado** | Solo la ve quien ya tiene acceso a Docker; por eso en disco solo hay el hash |
| `verify_dev_env.sh` con el entorno renombrado | **PROBADO** (antes del cambio de contraseña) | 12/12 OK. **NO VERIFICADO** tras el cambio: no se ejecutó para no tocar el proyecto `sms-dev` |
| Construcción desde un entorno limpio siguiendo la guía | **PROBADO** | pasos 1–5 de la guía, correcta |
| Contenedores detenidos visibles y ordenados (en ejecución primero) | **IMPLEMENTADO y PROBADO** | E2E y navegador |
| Salud deducida del texto de estado | **IMPLEMENTADO y PROBADO** | tests de la conversión |
| Presentación de «Con fallos» y «Arrancando» en el navegador | **NO VERIFICADO** | el recorrido no incluyó contenedores con *healthcheck* en esos estados |
| Disco raíz y un indicador por disco | **IMPLEMENTADO y PROBADO** | E2E contra `df`; navegador contra la API |
| Discos extra en `/disks/<nombre>` | **IMPLEMENTADO**; **NO VERIFICADO** con un disco real | solo directorios falsos en los tests |
| Temperatura con `coretemp` (Intel) | **IMPLEMENTADO y PROBADO** | E2E (±5 °C) y comparación con `/sys/class/hwmon` |
| Temperatura con `k10temp` (AMD) y `x86_pkg_temp` | **IMPLEMENTADO**; **NO VERIFICADO** en hardware real | solo directorios falsos |
| Red: contadores del anfitrión | **IMPLEMENTADO y PROBADO** | interfaces reales leídas en un contenedor sin red ni privilegios; E2E |
| Red: valor numérico de la velocidad | **IMPLEMENTADO**; **NO VERIFICADO** numéricamente | la gráfica se dibuja con muestras reales; no se contrastó con otra herramienta |
| Indicadores circulares (número y arco = API) | **IMPLEMENTADO y PROBADO** | navegador |
| Gráficas: líneas, ≥ 3 muestras reales, tooltip con ratón | **IMPLEMENTADO y PROBADO** | navegador |
| Gráficas: ventana de 10 min llena (desplazamiento) | **IMPLEMENTADO**; **PENDIENTE** de probar | requiere 10 min reales |
| Tooltip en pantalla táctil | **IMPLEMENTADO**; **NO VERIFICADO** | |
| Tooltip con teclado | **PENDIENTE** (no implementado) | los valores actuales están en la leyenda |
| Tema claro | **PENDIENTE** (no implementado) | solo oscuro |
| Pausa con pestaña oculta y reanudación | **IMPLEMENTADO y PROBADO** | simulando `visibilitychange` |
| Sin scroll horizontal a 1024 y 390 px | **PROBADO** | otros anchos: **NO VERIFICADO** |
| Sin errores de consola ni de CSP (fuentes e iconos propios) | **PROBADO** | navegador |
| Sin controles de modificación de contenedores | **IMPLEMENTADO y PROBADO** | tests del agente, `docker events` y navegador |
| Umbrales de color (CPU 75/90, RAM 80/90, disco 80/90, temperatura 75/90) | **IMPLEMENTADO**; **NO VERIFICADO** como requisito | valores elegidos sin requisito |
| Paleta: contraste AA y daltonismo | Validada al diseñar; **NO VERIFICADO** automáticamente | |
| Limpieza de código (vacíos, muertos, cachés) | **IMPLEMENTADO y PROBADO** | `vulture`, `ruff`, `pytest` |
| CI en GitHub | **NO VERIFICADO** | sin *push*; además excluye integración |
| Servidor Ubuntu real | **NO VERIFICADO** | solo CachyOS |
| Consumo de memoria y CPU | **NO VERIFICADO** | |

---

## 1. Cambios visuales realizados

Detalle y valores en [../09-interfaz.md](../09-interfaz.md).

| Cambio | Antes (renovación) | Ahora | Estado |
|---|---|---|---|
| Identidad | MiniPaaS | **Server Monitoring Service**, con marca propia (arco de 270° y punto central, también favicon) | **IMPLEMENTADO** |
| Tema | Interfaz sencilla de tarjetas y tabla (141 líneas de CSS) | Tema **oscuro sobrio** de panel de operaciones: fondo `#0e1115`, superficie `#151920`, elevada `#1b2028`, líneas `#252b34`/`#343c48`, texto `#e6e9ee`/`#b0b8c4`/`#8c95a2`, acento `#7aaef7` | **IMPLEMENTADO** |
| Estados | — | Normal `#3fb97a`, aviso `#e2a93b`, crítico `#f0645f`, detenido `#6b7480`; siempre con texto además del color | **IMPLEMENTADO** |
| Series | — | CPU `#3b8beb`, RAM `#d6578a`, bajada `#1fa2ae`, subida `#9085e9`, discos `#a3afbf` | **IMPLEMENTADO** |
| Tipografía | — | **IBM Plex Sans** (400/500/600) e **IBM Plex Mono** (400/500), autoalojadas | **IMPLEMENTADO y PROBADO** (sin errores de CSP) |
| Iconos | — | 18 iconos **Lucide** en un *sprite* y la marca propia | **IMPLEMENTADO y PROBADO** |
| Indicadores | Tarjetas de métricas | **Indicador circular de 270°** por CPU, RAM y cada disco; «Alto» y «Crítico» también en texto | **IMPLEMENTADO y PROBADO** |
| Evolución | No había | Dos gráficas de líneas: CPU y RAM, y red (bajada y subida); eje de 1 a 10 min; tooltip; cortes por huecos | **IMPLEMENTADO y PROBADO** (ventana llena: **PENDIENTE**) |
| Cabecera | — | Marca, *hostname*, estado de conexión (Conectado / Agente sin respuesta / Sin conexión con el panel / Error al actualizar), hora de la última actualización | **IMPLEMENTADO y PROBADO** |
| Sistema | Lista de sensores de temperatura | Una **temperatura general** o «No disponible» | **IMPLEMENTADO y PROBADO** |
| Contenedores | Solo en ejecución | Todos; detenidos, «Con fallos» y «Arrancando» diferenciados; puertos IPv4 e IPv6 agrupados; resumen; sin botones de modificación | **IMPLEMENTADO**; detenidos y ausencia de botones **PROBADOS**; «Con fallos» y «Arrancando» **NO VERIFICADOS** en navegador |
| Responsive | — | Rejilla con cortes a 420, 700, 760, 1100 y 1200 px; tabla que pasa a fichas en móvil | **PROBADO** a 1024 y 390 px |
| Accesibilidad | — | Foco visible, `role` en avisos, `aria-label` en gráficas, `prefers-reduced-motion` | **IMPLEMENTADO** (sin auditoría automática) |

## 2. Componentes nuevos y modificaciones del frontend

Todo en `src/server_monitor/panel/web/`. Sin librerías de JavaScript (ADR-047).

| Archivo | Cambio | Estado |
|---|---|---|
| `js/charts.js` (216 líneas) | **Nuevo.** `createGauge` (indicador circular con `stroke-dasharray`) y `createLineChart` (gráfica SVG con ejes, rejilla, tooltip, cortes por huecos > 15 s, eje que crece de 1 a 10 min y luego se desplaza, `prefers-reduced-motion`) | **IMPLEMENTADO y PROBADO**; desplazamiento **PENDIENTE** |
| `js/history.js` (44) | **Nuevo.** 120 muestras en memoria del navegador (10 min); velocidad de red `Δbytes/Δcollected_at`; hueco si un contador baja | **IMPLEMENTADO**; probado indirectamente en navegador (**NO VERIFICADO** el valor numérico) |
| `js/views/dashboard.js` (378) | **Reescrito.** Indicadores, gráficas, panel Sistema, contenedores; umbrales en `THRESHOLDS`; sondeo cada 5 s con `setTimeout` encadenado y pausa con pestaña oculta | **PROBADO** |
| `js/format.js` (85) | **Reescrito.** Bytes, velocidad, porcentaje, uptime, fechas, marcas del eje y agrupación de puertos | **IMPLEMENTADO** (sin prueba automática propia) |
| `js/dom.js` (38) | **Ampliado.** `svg()` y `icon()` además de `el()`; todo texto por `textContent` | **IMPLEMENTADO y PROBADO** |
| `js/app.js` (51) | Adaptado a la cabecera, que se muestra solo en el panel | **PROBADO** |
| `js/views/login.js` (64) | Pantalla de login con marca e icono; lógica del formulario igual | **PROBADO** (error de contraseña incorrecta) |
| `js/api.js` (75), `js/session.js` (37) | Sin cambios de lógica (solo un texto en `api.js`) | **PROBADO** |
| `index.html` | Cabecera y precarga de fuentes; sin scripts ni estilos en línea | **PROBADO** (CSP) |
| `css/styles.css` (457) | **Reescrito**: tokens de color, tipografía, rejilla y puntos de corte | **PROBADO** (scroll horizontal) |
| `icons.svg`, `icons-LICENSE.txt` | **Nuevos.** Sprite de 18 iconos Lucide y la marca; licencia ISC | **IMPLEMENTADO y PROBADO** |
| `fonts/` (5 `woff2` + `OFL.txt`) | **Nuevos.** IBM Plex Sans 400/500/600 e IBM Plex Mono 400/500, SIL OFL 1.1 | **IMPLEMENTADO y PROBADO** |
| `favicon.svg` | **Nuevo diseño** (la marca) | **IMPLEMENTADO** |

## 3. Cambios realizados en el backend

Detalle en [../04-backend.md](../04-backend.md) y [../05-api.md](../05-api.md).

| Cambio | Dónde | Estado |
|---|---|---|
| Renombrado `minipaas` → `server_monitor`, `controlplane` → `panel`, `MINIPAAS_*` → `SMS_*`, cookie `sms_session`, logger `server_monitor.access`, secrets `panel_token` y `agent_token` | `src/`, `deploy/`, `scripts/`, `tests/`, `pyproject.toml` | **IMPLEMENTADO y PROBADO** |
| `/metrics`: `disks` (raíz «Sistema» + `/disks/<nombre>`, se omiten los del mismo `st_dev`) | `agent/host_metrics.py` | **IMPLEMENTADO y PROBADO** (extra: **NO VERIFICADO** con disco real) |
| `/metrics`: `temperature` única (`coretemp` «Package id 0», `k10temp` «Tctl» o `x86_pkg_temp`; `null` si no hay; 0 < t ≤ 150) | `agent/host_metrics.py` | **IMPLEMENTADO y PROBADO** (Intel) |
| `/metrics`: `network` (contadores acumulados de `/host/net/dev`; se excluyen `lo`, `veth*`, `br-*`, `docker*`, `virbr*`); la velocidad la calcula el navegador | `agent/host_metrics.py` | **IMPLEMENTADO y PROBADO** |
| `/metrics`: `collected_at` con milisegundos; **se eliminan** `disk` y `temperatures` | `agent/host_metrics.py` | **IMPLEMENTADO y PROBADO** |
| `/containers`: **todos** los contenedores con `client.api.containers(all=True)`, primero los `running`, `health` deducido del estado | `agent/containers.py` | **IMPLEMENTADO y PROBADO** |
| Variables nuevas `SMS_DISKS_DIR` (`/disks`) y `SMS_NET_DEV` (`/proc/net/dev`; `/host/net/dev` en Compose) | `agent/config.py`, `compose.dev.yaml` | **IMPLEMENTADO y PROBADO** |
| Montajes del agente: `/proc/1/net/dev:/host/net/dev:ro` y discos extra opcionales en `/disks/*:ro` | `deploy/compose.dev.yaml` | **PROBADO** `/host/net/dev`; `/disks/*` **NO VERIFICADO** con disco real |
| Proyecto Compose `sms-dev`, redes `sms-internal`/`sms-public`, volumen `sms-data`, usuarios `sms-panel` (10001) y `sms-agent` (10002) | `deploy/` | **IMPLEMENTADO y PROBADO** (E2E con `sms-e2e`) |
| El panel (Python) **no cambia de comportamiento** al reenviar el JSON del agente; el login y las sesiones tampoco cambian | `panel/` | **PROBADO** (tests) |
| Contraseña desde `APP_PASSWORD` / `APP_PASSWORD_RESET` (`configure_password`, `write_hash_file` movida a `security/passwords.py`; `build_app_from_env` la llama y sale con `SystemExit(1)` si falla) | `panel/security/passwords.py`, `panel/main.py` | **IMPLEMENTADO y PROBADO** (tests y E2E) |
| `compose.dev.yaml` exige `APP_PASSWORD` y pasa `APP_PASSWORD_RESET`; `deploy/.env.example` las documenta | `deploy/` | **IMPLEMENTADO y PROBADO** (E2E: `docker compose config` sin la variable falla) |
| `prepare_dev_env.sh` conserva `deploy/.env` (solo actualiza `DOCKER_GID`, permisos 600, avisa si falta `APP_PASSWORD`) | `scripts/` | **IMPLEMENTADO**; probado sobre una copia temporal, **NO** sobre el `deploy/.env` real |

Como el volumen cambia de nombre, el primer arranque guarda de nuevo el hash de `APP_PASSWORD`, y hay
que bajar el entorno antiguo con `docker compose -p minipaas-dev down` (ver la guía).

### Configuración de la contraseña con `APP_PASSWORD`

El panel lee `APP_PASSWORD` al arrancar, **antes** de crear la aplicación, y guarda solo el hash
Argon2id en `/data/password_hash` (permisos 600, escritura atómica). No hay contraseña por defecto, y la
contraseña nunca se guarda ni se registra. Si no se puede continuar, se registra el motivo y el proceso
termina con `SystemExit(1)` (el contenedor sale con código 1; `uvicorn --factory` no muestra traceback).
Solo el texto `true` (sin distinguir mayúsculas) activa `APP_PASSWORD_RESET`.

| Situación | Resultado | Log |
|---|---|---|
| Primera instalación (sin hash) | Se guarda el hash | INFO «Contraseña inicial configurada a partir de APP_PASSWORD» |
| Hay hash y coincide | Arranque normal | INFO breve (WARNING si `RESET=true`: puede quitarse) |
| Hay hash y **no** coincide, sin reset | **No arranca** (código 1) | ERROR: no coincide; añade `APP_PASSWORD_RESET=true` en `deploy/.env`, reinicia y quítala, o restaura el valor anterior |
| Hay hash, no coincide y `APP_PASSWORD_RESET=true` | Se sustituye el hash | WARNING «Contraseña cambiada por APP_PASSWORD_RESET=true; quita APP_PASSWORD_RESET de deploy/.env» |
| `APP_PASSWORD` falta, vacía o fuera de 4 a 128 | No arranca | ERROR «Falta APP_PASSWORD: define la contraseña del panel en deploy/.env (ver deploy/.env.example)» o «APP_PASSWORD no es válida…» |

Las sesiones están en memoria: cualquier reinicio, y por tanto cualquier cambio de contraseña, las cierra
(comprobado en el E2E). El login conserva el 503 si no hay hash (caso defensivo). Riesgo residual: la
variable es visible con `docker inspect` para quien ya tiene acceso a Docker. Detalle en
[../04-backend.md](../04-backend.md), [../06-seguridad.md](../06-seguridad.md) y ADR-049 en
[../10-decisiones.md](../10-decisiones.md).

## 4. Archivos y módulos eliminados, con sus motivos

| Elemento eliminado | Motivo |
|---|---|
| Carpetas vacías `tests/fakes/`, `tests/integration/` y `tests/unit/` | No contenían pruebas. `tests/unit/test_secrets.py` se movió a `tests/test_secrets.py` (la única prueba que quedaba) |
| Cachés locales (`__pycache__`, `.pytest_cache`, `.ruff_cache`) | Archivos generados e ignorados por Git; no son parte del proyecto |
| Campo `disk` y lista `temperatures` de `/metrics` | Sustituidos por `disks` (varios discos) y `temperature` (una sola); mantenerlos duplicaría datos |
| Antiguo código de lectura de todas las `thermal_zone*` | Sustituido por la lectura del paquete del procesador (ADR-045) |
| Antiguas tarjetas y CSS de la interfaz | Sustituidos por el rediseño |
| `panel/manage.py` y el comando `set-password` (con sus 3 tests y las referencias en scripts y documentación vigente) | Sustituidos por `APP_PASSWORD` (ADR-049): una sola forma de configurar la contraseña. `write_hash_file` se conserva, movida a `security/passwords.py`. Un `grep` no encuentra ya `set-password` fuera de `docs/historico/`, las entradas antiguas del `CHANGELOG`, ADR-039 (donde figura como sustituido) y este informe |
| Nombres `minipaas`, `controlplane`, `MINIPAAS_*`, `Dockerfile.controlplane`, `requirements/controlplane.txt`, extra `controlplane` | Renombrados (ADR-042); no quedan en el código vigente |
| **Ningún módulo Python muerto** | `vulture --min-confidence 80` sin resultados. Las clases CSS «sin uso» que señaló eran generadas dinámicamente: **no** se eliminaron |

No se añadió ni eliminó ninguna dependencia (apartado 8).

## 5. Documentación actualizada, archivada y eliminada

Criterio: lo que **describe el sistema actual** va en `docs/`; lo que **justifica decisiones, explica la
evolución o demuestra trabajo realizado** se archiva en `docs/historico/`; solo se elimina lo duplicado.
Los movimientos se hicieron con `git mv` (se conserva el historial).

### Actualizados o creados (documentación vigente)

| Documento | Cambio |
|---|---|
| `README.md` (raíz) | Reescrito para el proyecto actual; arranque rápido con `APP_PASSWORD` |
| `CHANGELOG.md` | Entrada nueva; las anteriores se conservan con los nombres de su época |
| `docs/README.md` | Índice nuevo y aviso sobre `historico/` |
| `docs/01-vision-y-alcance.md` | Objetivo y alcance actuales; evolución en un apartado; **absorbe el roadmap** (siguientes pasos) |
| `docs/02-requisitos.md` | Solo requisitos vigentes, con estado de verificación actualizado (RF-M16, M24, M25, M33 y RNF-M15 nuevos) |
| `docs/03-arquitectura.md` | Actualizado; **absorbe la estructura del proyecto** |
| `docs/04-backend.md` | **Nuevo.** Módulos, origen de cada métrica, contenedores, secuencias, autenticación, permisos y variables |
| `docs/05-api.md` | Antes `api.md`; contrato v2 con ejemplos JSON y códigos de error |
| `docs/06-seguridad.md` | Antes `04-seguridad.md`; amenazas y medidas actuales (T9, T9b y T9c sobre la contraseña) |
| `docs/07-pruebas.md` | Fusiona la estrategia (antes `05-estrategia-pruebas.md`) y el registro vigente |
| `docs/08-guia-desarrollo.md` | Antes `guia-desarrollo.md`; instalación desde cero, disco extra, migración desde `minipaas-dev` |
| `docs/09-interfaz.md` | **Nuevo.** Decisiones de diseño y componentes JavaScript |
| `docs/10-decisiones.md` | Antes `decisiones.md`; solo ADR vigentes, más **ADR-042 a 049** (ADR-049: contraseña desde `APP_PASSWORD`; ADR-039 marcada como revisada) |
| `docs/11-estado-del-arte.md` | Solo herramientas de monitorización comparables |
| `docs/bibliografia.md` | Ampliada: IBM Plex, Lucide, `@fontsource`, `proc(5)`, hwmon, thermal, API de Docker, `statvfs`, MDN y WCAG; etapa PaaS en sección propia. La sección «Uso de herramientas de IA» **no se ha tocado** |
| `docs/informes/renovacion-monitorizacion.md` | Se conserva; se añade al principio una nota sobre el renombrado |
| `docs/informes/rediseno-interfaz-limpieza.md` | Este informe |

### Archivados en `docs/historico/`

| Archivo | Origen |
|---|---|
| `historico/README.md` | Nuevo: qué contiene, por qué se conserva y cómo se relaciona con el proyecto actual |
| `historico/informes/fase-00.md`, `fase-01.md`, `fase-02.md` | `git mv` desde `docs/informes/` (con un aviso al principio) |
| `historico/decisiones-etapa-paas.md` | ADR sustituidas (002, 005, 007 a 012, 016 a 018, 020, 022, 023) con su texto original, extraídas de `decisiones.md` |
| `historico/arquitectura-etapa-paas.md` | Resumen de la arquitectura PaaS (antes, apartado 3.8 de la arquitectura) |
| `historico/requisitos-etapa-paas.md` | Requisitos RF-01 a RF-73 y su correspondencia (antes, apartados 2.3 y 2.4) |
| `historico/roadmap-etapa-paas.md` | `git mv` de `06-roadmap.md` con el roadmap PaaS (la situación y fases siguientes vigentes pasan a `01-vision-y-alcance.md`) |
| `historico/estado-del-arte-etapa-paas.md` | `git mv` de `07-estado-del-arte.md`, sin el apartado de monitorización |
| `historico/registro-pruebas-etapa-paas.md` | `git mv` de `registro-pruebas.md`, solo las Fases 0 a 2 |

### Eliminados

| Archivo | Motivo |
|---|---|
| `docs/08-estructura-proyecto.md` (`git rm`) | Duplicado: su contenido (el árbol de carpetas) está en `03-arquitectura.md`, apartado 3.7, actualizado |

Los apartados con la renovación del registro de pruebas pasaron a `07-pruebas.md` (apartado 7.7). Las
ADR 025 a 035 (Fase 3) solo existen en la rama `fase-03-motor-despliegue`; la nota correspondiente está en
`10-decisiones.md`.

## 6. Nueva estructura de carpetas

Árbol real al cerrar la fase (sin `.git`, `.venv`, cachés ni `deploy/secrets/`):

```text
server-monitoring-service/
├── README.md
├── CHANGELOG.md
├── formato_preguntas.md                  (sin modificar)
├── pyproject.toml, uv.lock
├── .github/workflows/ci.yml
├── .dockerignore, .gitignore
├── deploy/
│   ├── Dockerfile.agent
│   ├── Dockerfile.panel
│   ├── compose.dev.yaml
│   ├── .env.example
│   └── requirements/{agent.txt, panel.txt}
├── scripts/
│   ├── prepare_dev_env.sh, verify_dev_env.sh, export_requirements.sh
│   └── e2e_monitor.sh, e2e_ui.py
├── src/server_monitor/
│   ├── common/secrets.py
│   ├── agent/{main.py, host_metrics.py, containers.py, config.py}
│   └── panel/
│       ├── {main.py, routes.py, config.py, agent_client.py}
│       ├── security/{passwords.py, sessions.py, rate_limit.py, csrf.py}
│       └── web/
│           ├── index.html, favicon.svg, icons.svg, icons-LICENSE.txt
│           ├── css/styles.css
│           ├── fonts/{ibm-plex-sans-latin-{400,500,600}-normal.woff2,
│           │          ibm-plex-mono-latin-{400,500}-normal.woff2, OFL.txt}
│           └── js/{api,app,charts,dom,format,history,session}.js
│               └── views/{login,dashboard}.js
├── tests/
│   ├── test_secrets.py
│   ├── agent/{conftest, fakes, test_agent_api, test_containers, test_host_metrics,
│   │          test_agent_docker_integration}.py
│   └── panel/{conftest, test_api, test_auth, test_password_config}.py
└── docs/
    ├── README.md
    ├── 01-vision-y-alcance.md   02-requisitos.md      03-arquitectura.md
    ├── 04-backend.md            05-api.md             06-seguridad.md
    ├── 07-pruebas.md            08-guia-desarrollo.md 09-interfaz.md
    ├── 10-decisiones.md         11-estado-del-arte.md bibliografia.md
    ├── informes/
    │   ├── renovacion-monitorizacion.md
    │   └── rediseno-interfaz-limpieza.md
    └── historico/
        ├── README.md
        ├── informes/{fase-00.md, fase-01.md, fase-02.md}
        └── {decisiones, arquitectura, requisitos, roadmap, estado-del-arte, registro-pruebas}-etapa-paas.md
```

## 7. Explicación de la arquitectura final del backend

Detalle completo en [../04-backend.md](../04-backend.md). En resumen:

```text
Navegador ──HTTP + cookie──▶ PANEL (UID 10001, sin socket)
                               │  FastAPI: /api/*, estáticos, sesiones en memoria,
                               │  hash Argon2id en /data/password_hash
                               └──HTTP interno + Bearer──▶ AGENTE (UID 10002, red interna)
                                    FastAPI: /health, /metrics, /containers (solo GET)
                                    ├─ Docker (socket): containers(all=True), version
                                    ├─ /proc, /sys (del anfitrión)
                                    ├─ /hostfs (:ro, no recursivo): statvfs, os-release, hostname
                                    ├─ /disks/<nombre> (:ro): discos extra declarados
                                    └─ /host/net/dev (:ro) = /proc/1/net/dev del anfitrión
```

- **Panel:** autentica (contraseña única, Argon2id, límite de 5 fallos en 15 min por IP, sesiones de 30
  min de inactividad y 8 h, cookie `sms_session`, CSRF, comprobación de `Origin`), añade las cabeceras
  de seguridad y la CSP, sirve la interfaz y **reenvía sin transformar** `/api/metrics` y
  `/api/containers`.
- **Agente:** único con el socket de Docker. Solo rutas `GET`, token Bearer en todas, sin documentación
  OpenAPI. Lee del anfitrión con la biblioteca estándar (sin `psutil`): CPU de dos lecturas de
  `/proc/stat` separadas 0,5 s; RAM `MemTotal − MemAvailable`; discos con `statvfs` como `df`;
  temperatura del paquete del procesador; contadores de red acumulados. A Docker solo le hace dos
  consultas: la lista de contenedores y la versión.
- **Cálculo repartido:** el servidor entrega contadores y estado; el navegador calcula la velocidad de
  red y guarda el histórico. El servidor no almacena métricas.
- **Garantía de solo lectura:** está en el código del agente (el socket sin `:ro` no limita la API), en
  los tests y en la comprobación de `docker events` del E2E: **PROBADO**.
- **Permisos:** ambos contenedores sin root, con `read_only`, `cap_drop: ALL` y `no-new-privileges`; el
  panel sin socket; el agente en una red `internal` sin puertos. Comprobado con `verify_dev_env.sh` con los
  nombres nuevos: 12/12 OK (**PROBADO**).

## 8. Dependencias añadidas y eliminadas

| Tipo | Añadidas | Eliminadas |
|---|---|---|
| Dependencias de Python (`pyproject.toml`) | **Ninguna** | **Ninguna** |
| Librerías de JavaScript | **Ninguna** | **Ninguna** |
| Cambio de contraseña con `APP_PASSWORD` | **Ninguna** (usa `os`, `logging` y el `argon2-cffi` que ya había) | **Ninguna** |

Dependencias vigentes sin cambios: `fastapi`, `uvicorn` (comunes), `httpx` y `argon2-cffi` (extra
`panel`), `docker` (extra `agent`) y, solo para desarrollo, `pytest`, `pytest-cov` y `ruff`. `uv.lock`
se regeneró **solo** por el cambio de nombre del proyecto (`server-monitoring-service`) y del extra
(`controlplane` → `panel`); `deploy/requirements/` se reexportó.

**Recursos estáticos nuevos (no son dependencias):** se copian al repositorio y se sirven desde el panel.

| Recurso | Versión y origen | Licencia |
|---|---|---|
| IBM Plex Sans (400, 500, 600) | `@fontsource/ibm-plex-sans@5.2.8`, descargado de cdn.jsdelivr.net | SIL OFL 1.1, © IBM Corp. (`web/fonts/OFL.txt`) |
| IBM Plex Mono (400, 500) | `@fontsource/ibm-plex-mono@5.2.7`, descargado de cdn.jsdelivr.net | SIL OFL 1.1, © IBM Corp. (`web/fonts/OFL.txt`) |
| 18 iconos Lucide (sprite `icons.svg`) | `lucide-static@1.68.0`, descargados de unpkg.com | ISC (`web/icons-LICENSE.txt`) |

## 9. Pruebas ejecutadas y resultados reales

Entorno: equipo local CachyOS, Docker 29.9.2, Compose 5.6.1, 2026-11-16. **No es el servidor Ubuntu
real.** Detalle en [../07-pruebas.md](../07-pruebas.md), apartado 7.6.

| # | Comando | Resultado real | Estado |
|---|---|---|---|
| 1 | `uv run ruff check .` | All checks passed | **PROBADO** |
| 2 | `uv run ruff format --check .` | 51 files already formatted | **PROBADO** |
| 3 | `node --check` en los 9 módulos de `web/js` | OK | **PROBADO** |
| 4 | `uv run pytest -q` | 57 passed, 1 aviso (deprecación de httpx en el `TestClient` de Starlette) | **PROBADO** |
| 5 | `uv run pytest -q -m "not integration"` | 54 passed, 3 deselected | **PROBADO** |
| 6 | `bash scripts/e2e_monitor.sh` | 32 OK, «E2E correcto.» | **PROBADO** |
| 7 | `SMS_URL=... SMS_PASSWORD=... SMS_SCREENSHOTS=... uvx --with playwright python scripts/e2e_ui.py` (proyecto Compose aislado `sms-ui`, puerto 8011) | 22 OK, «UI correcta.» | **PROBADO** |
| 8 | Agente en un contenedor efímero sin red, no root y sin capabilities, con `/proc/1/net/dev` montado | Se leen las interfaces reales del anfitrión (`enp0s31f6`, `wlan0`, `tailscale0`); la temperatura detectada (`coretemp: Package id 0`, 46 °C) coincide con `/sys/class/hwmon` | **PROBADO** |
| 9 | `vulture --min-confidence 80` | Sin resultados | **PROBADO** |
| 10 | `bash scripts/verify_dev_env.sh` con el entorno renombrado | **12/12 OK** (panel sin socket Docker; agente sin puertos publicados y no accesible desde el anfitrión; ningún contenedor como root; el agente rechaza peticiones sin token; secrets 600/700 con su UID; `/data` volumen escribible por el UID 10001; raíz del panel en solo lectura) | **PROBADO** |
| 11 | Construcción desde un entorno limpio siguiendo [la guía](../08-guia-desarrollo.md) | **Correcta**: copia limpia de los archivos versionados (sin `.venv`, secretos ni cachés) en un directorio temporal, con `COMPOSE_PROJECT_NAME=sms-clean` y `SMS_PORT=8020` para no chocar con el entorno de desarrollo; pasos 1–5 de la guía sin cambios: `uv sync --all-extras`; ruff OK; 54 tests OK; `prepare_dev_env.sh` creó secretos y `.env`; `compose up --build --wait` con ambos contenedores *healthy*; `set-password --stdin` guardó el hash; login 204; `/api/metrics` con datos reales (CPU, RAM, disco Sistema, temperatura coretemp 43 °C, 3 interfaces de red); `/api/containers` con 7 contenedores; `/` 200. Después se borró todo (proyecto, imágenes, volumen y copia) | **PROBADO** |
| 12 | `uv run ruff check .`; `uv run ruff format --check .` (tras el cambio de contraseña) | All checks passed; 58 files already formatted | **PROBADO** |
| 13 | `uv run pytest -q`; `uv run pytest -q -m "not integration"` (tras el cambio) | **68 passed**, 1 aviso; **65 passed**, 3 deselected | **PROBADO** |
| 14 | `bash scripts/e2e_monitor.sh` (tras el cambio) | **46 OK**, «E2E correcto.» | **PROBADO** |
| 15 | `SMS_URL=http://127.0.0.1:8011 APP_PASSWORD=... uvx --with playwright python scripts/e2e_ui.py` (proyecto `sms-ui`, borrado al terminar) | **22 OK**, «UI correcta.» | **PROBADO** |
| 16 | `bash -n scripts/*.sh`; `py_compile` de `e2e_ui.py`; `node --check` | OK | **PROBADO** |

**Nota.** Las filas 4 a 7 son los resultados **anteriores** al cambio de contraseña (57 tests, 32
comprobaciones E2E); los vigentes son los de las filas 12 a 16. La fila 11 y la 10 se ejecutaron antes de
ese cambio.

**Lo que comprueba el E2E (46; las 32 anteriores más las de `APP_PASSWORD`):** despliegue con `APP_PASSWORD`; 401 sin sesión; login; CPU, RAM, disco,
discos, temperatura, red, *hostname*, SO y uptime frente al anfitrión; medición nueva en cada consulta;
contenedor ajeno detectado (imagen, estado, puerto y proyecto Compose); mismo número que `docker ps -a`;
en ejecución primero; un contenedor detenido sigue apareciendo; sin eventos de modificación en
`docker events`; el panel sin socket; el agente sin escritura en `/hostfs` y sin submontajes; logout con
CSRF; sesión antigua rechazada; bloqueo tras 5 fallos. **Nuevas de `APP_PASSWORD`:** `docker compose
config` sin la variable falla con el mensaje; la imagen del panel sin `APP_PASSWORD` sale con código ≠ 0 y
explica el motivo; el hash empieza por `$argon2id`, no contiene la contraseña y tiene permisos 600; los
logs no contienen la contraseña; otra contraseña sin reset deja el panel parado (código 1) con el motivo
en el log; con `APP_PASSWORD_RESET=true` arranca, la nueva vale (204), la antigua da 401 y reiniciar
cierra la sesión anterior; se restaura la original y un reinicio sin `RESET` arranca con normalidad.

**Lo que comprueba el navegador (22):** error con contraseña incorrecta; número y arco de CPU, RAM y
cada disco iguales a la API; un indicador por disco; una sola temperatura; filas de la tabla igual que
contenedores de la API; detenidos marcados; sin botones de modificación; la hora cambia sola; ≥ 3
muestras reales y líneas en las gráficas; tooltip; pausa con la pestaña oculta y reanudación (simulada
con `visibilitychange`, porque Chromium sin interfaz no oculta pestañas; la versión anterior del script
no era fiable en ese punto y se corrigió); sin scroll horizontal a 1024 y 390 px; logout y sesión
rechazada; sin errores de consola ni de CSP.

## 10. Problemas detectados y aspectos pendientes

| # | Aspecto | Estado | Detalle y consecuencia |
|---|---|---|---|
| 1 | `verify_dev_env.sh` con el entorno renombrado | Resuelto | 12/12 OK (apartado 9) |
| 2 | Construcción desde un entorno limpio siguiendo la guía | Resuelto | Correcta (apartado 9) |
| 3 | No probado en el servidor Ubuntu real | **NO VERIFICADO** | Solo CachyOS; requiere autorización expresa |
| 4 | Sin tema claro | **PENDIENTE** | Solo oscuro; no era un requisito |
| 5 | Tooltip no accesible por teclado; no probado en táctil | **PENDIENTE** / **NO VERIFICADO** | Los valores actuales están en la leyenda, que sí es texto |
| 6 | Deslizamiento con la ventana de 10 min llena | **PENDIENTE** | Requiere 10 min reales en el navegador |
| 7 | Umbrales elegidos sin requisito | **NO VERIFICADO** | CPU 75/90, RAM 80/90, disco 80/90, temperatura 75/90; fáciles de cambiar en `dashboard.js` |
| 8 | Texto de `status` de Docker en inglés | Limitación conocida | Se muestra tal cual («Up 3 hours») |
| 9 | La red incluye interfaces como `tailscale0` (VPN) en el total | Limitación conocida | Se mezcla tráfico físico y de VPN |
| 10 | Sesiones y limitador en memoria | Limitación conocida | Se pierden al reiniciar el panel y solo valen con un proceso |
| 11 | El socket de Docker da acceso equivalente a root al agente | Riesgo reconocido | La solo-lectura la garantiza el código (ADR-037); mejora posible: proxy del socket |
| 12 | Aviso de deprecación de httpx en el `TestClient` de Starlette | Aviso | No es un fallo; dependencia indirecta |
| 13 | El CI excluye las pruebas de integración y no se ha ejecutado en GitHub | **NO VERIFICADO** | Sin *push*; el CI tampoco ejecuta E2E ni navegador |
| 14 | Discos extra reales, `k10temp` y `x86_pkg_temp` | **NO VERIFICADO** | Solo con directorios falsos |
| 15 | Valor numérico de la velocidad de red | **NO VERIFICADO** | No contrastado con otra herramienta |
| 16 | «Con fallos» y «Arrancando» en el navegador | **NO VERIFICADO** | Probada la conversión, no la presentación |
| 17 | Consumo de memoria y CPU | **NO VERIFICADO** | Objetivo de diseño sin medir |
| 18 | Hay que bajar el entorno `minipaas-dev`; el primer arranque guarda de nuevo el hash de `APP_PASSWORD` | Aviso de migración | El volumen cambia de nombre; ver la guía |
| 19 | `verify_dev_env.sh` tras el cambio de contraseña | **NO VERIFICADO** | Necesita `APP_PASSWORD` en `deploy/.env` y levanta `sms-dev` (en uso); no se ejecutó |
| 20 | El entorno `sms-dev` en marcha necesita `APP_PASSWORD` en `deploy/.env` antes de recrearlo | Aviso de migración | Si se pone igual que la contraseña actual no cambia nada; si es distinta, hace falta `APP_PASSWORD_RESET=true` |
| 21 | `APP_PASSWORD` visible con `docker inspect`; `$` y comillas en `.env` | Riesgo reconocido / limitación | Documentado en la guía y en seguridad; los `$` deben duplicarse (`$$`) |
| 22 | `prepare_dev_env.sh` completo no se ejecutó sobre el `deploy/.env` real | **NO VERIFICADO** | Solo se probó el fragmento que escribe `DOCKER_GID`, sobre una copia temporal |

**Siguiente paso recomendado:** aprobar la fase y, solo con autorización,
probar en Ubuntu (ver [01-vision-y-alcance.md](../01-vision-y-alcance.md), apartado 1.7).
