# 10. Decisiones técnicas (ADR)

> Estado: **actualizado tras simplificar el despliegue (2026-11-16)**. Aquí están las
> decisiones **vigentes**, con su número original. Las que quedaron sustituidas están en
> [historico/decisiones-etapa-paas.md](historico/decisiones-etapa-paas.md).

Cada decisión sigue el formato *Architecture Decision Record*: contexto, alternativas, decisión y
consecuencias. Estados: **Aceptada** (vigente) y **Sustituida** (en el histórico). Los textos de las
ADR 001 a 024 se han actualizado para usar los nombres actuales; cuando una ADR cambió de alcance, se
indica con la etiqueta **Revisada**.

## Índice

| ADR | Tema | Estado | Dónde está |
|---|---|---|---|
| 001 | Runtime: Docker Engine en un solo nodo | Aceptada | Aquí |
| 002 | Agente propio con acceso a Docker | Sustituida en parte por ADR-037 | [Histórico](historico/decisiones-etapa-paas.md) |
| 003 | Integración con Docker mediante el SDK oficial de Python | Aceptada | Aquí |
| 004 | Backend en Python con FastAPI | Aceptada | Aquí |
| 005 | SQLite con el módulo estándar `sqlite3` | Sustituida por ADR-039 | Histórico |
| 006 | Panel en HTML/CSS/JS sin framework ni compilación | Aceptada (revisada) | Aquí |
| 007 a 009, 011, 012, 023 | Aplicaciones, redes, despliegues, *rollback*, *worker*, estado de aplicación | Sustituidas por ADR-036 | Histórico |
| 010 | Autenticación con un único administrador | Sustituida en parte por ADR-039 | Histórico |
| 013 | `uv` y `uv.lock` en desarrollo, CI e imágenes | Aceptada (revisada) | Aquí |
| 014 | Token compartido como *secret* de archivo, una copia 600 por componente | Sustituida por ADR-051 | [Histórico](historico/decisiones-etapa-paas.md) |
| 015 | Python 3.12 en imágenes y CI | Aceptada | Aquí |
| 016, 017, 020, 022 | Migraciones, conexiones SQLite, administrador inicial, auditoría en BD | Sustituidas por ADR-039 | Histórico |
| 018 | Sesiones con el identificador guardado como hash | Sustituida en parte por ADR-039 | Histórico |
| 019 | Argon2id para las contraseñas | Aceptada (revisada) | Aquí |
| 021 | CSRF con token sincronizador por sesión + comprobación de `Origin` | Aceptada (revisada) | Aquí |
| 024 | Limitación de intentos de login en memoria | Aceptada (revisada) | Aquí |
| 025 a 035 | Motor de despliegue (Fase 3) | No aprobadas; sustituidas por ADR-036 | Solo en la rama `fase-03-motor-despliegue` |
| 036 a 041 | Renovación: monitorización de solo lectura | Aceptadas | Aquí |
| 042 a 048 | Rediseño de interfaz y limpieza | Aceptadas (2026-11-16) | Aquí |
| 049 | Contraseña desde `APP_PASSWORD` con confirmación explícita de cambios | Sustituida por ADR-050 | [Histórico](historico/decisiones-etapa-paas.md) |
| 050 | Contraseña en `docker-compose.yml` con hash en memoria | Aceptada (2026-11-16) | Aquí |
| 051 | Sin token entre panel y agente: aislamiento por red interna | Aceptada (2026-11-16) | Aquí |
| 052 | Un único `docker-compose.yml` en la raíz para servidor y desarrollo | Aceptada (2026-11-16) | Aquí |

> **Dónde están las ADR que no están aquí.** Las sustituidas (002, 005, 007 a 012, 014, 016 a 018, 020,
> 022, 023, 049) están completas en el histórico. Las ADR 025 a 035 pertenecen a la Fase 3, que no se
> aprobó: su texto solo existe en la rama `fase-03-motor-despliegue`, y sus números no se reutilizan.

---

## Decisiones de la base del proyecto (vigentes)

### ADR-001 · Runtime: Docker Engine en un solo nodo

**Contexto.** El servidor doméstico ya usa Docker Engine y Compose y tiene recursos limitados.

| Opción | Ventajas | Inconvenientes |
|---|---|---|
| **Docker Engine** | Ya instalado; ligero; API estable y documentada; conocido por el equipo | Un solo nodo; el socket da privilegios de root |
| Kubernetes (K3s, MicroK8s) | Estándar de la industria | Consumo base de cientos de MB; mucha complejidad conceptual |
| Docker Swarm | Servicios y réplicas integrados | Pensado para varios nodos; no aporta en un servidor |
| Podman | *Rootless* y sin demonio | No es lo que usa el servidor |

**Decisión.** Docker Engine directamente.

**Consecuencias.** Sin alta disponibilidad ni multi-nodo (limitación documentada). Como el agente
habla la API de Docker, Podman podría usarse en el futuro con cambios mínimos.

### ADR-003 · Integración con Docker mediante el SDK oficial de Python

**Alternativas.** SDK `docker` (docker-py); invocar la CLI `docker` con `subprocess`.

**Decisión.** SDK oficial, usado solo en el agente. Respuestas estructuradas y errores tipados; no se
construyen comandos de shell (se elimina el riesgo de inyección); no hace falta la CLI en la imagen.

### ADR-004 · Backend en Python con FastAPI

**Alternativas.** Flask, Django, Node.js (Express), Go.

**Decisión.** FastAPI + Pydantic + Uvicorn. Validación declarativa (clave para la seguridad),
ligero, soporte `async` para el cliente HTTP del panel, y Python es el lenguaje que mejor conoce el
equipo. Django aporta mucho que no se necesita; Go sería más eficiente pero menos accesible. Las
páginas `/docs` y `/redoc` están desactivadas porque cargan recursos de un CDN (bloqueado por la CSP).

### ADR-006 · Panel en HTML/CSS/JS sin framework ni compilación (revisada)

**Alternativas.** React/Vue/Svelte (con paso de compilación), HTMX.

**Decisión.** HTML, CSS y JavaScript moderno (módulos ES) servidos como archivos estáticos por el
panel. Sin cadena de compilación ni `node_modules`; cualquier miembro del equipo puede leerlo. Un
módulo JS por vista y un cliente de API común.

**Revisión (2026-11-16).** El plan inicial incluía Chart.js para las gráficas; se sustituyó por SVG
propio (ADR-047), de modo que el panel no tiene ninguna librería de JavaScript.

**Consecuencias.** Hay que ser disciplinados con la estructura y con el escape de datos (XSS): todo
dato del servidor se inserta con `textContent`, nunca con `innerHTML`.

### ADR-013 · `uv` y `uv.lock` en desarrollo, CI e imágenes (revisada)

**Contexto.** Hace falta un entorno reproducible para el equipo y el CI.

**Alternativas.** `venv` + `pip` + `requirements.txt`; Poetry; **uv**.

**Decisión.** `uv` para crear el entorno, resolver y fijar las dependencias en `uv.lock`
(versionado). Las herramientas de desarrollo (`pytest`, `pytest-cov`, `ruff`) van en el grupo `dev`
de `[dependency-groups]`, que no se instala en las imágenes.

**Las imágenes también usan el bloqueo.** `scripts/export_requirements.sh` exporta `uv.lock` a
`deploy/requirements/panel.txt` y `agent.txt` con el hash SHA-256 de cada paquete; los Dockerfiles los
instalan con `pip install --require-hashes` y copian el código en `PYTHONPATH` sin instalarlo como
paquete. El CI regenera los archivos y falla si no coinciden con `uv.lock`. Alternativa descartada:
instalar `uv` en la imagen (una herramienta más sin necesidad).

**Consecuencias.** Construcciones reproducibles y verificadas por hash. Coste: tras cambiar
dependencias hay que ejecutar `scripts/export_requirements.sh`. La imagen base `python:3.12-slim` se
referencia por etiqueta, no por *digest*: se fijará antes del despliegue final.

### ADR-015 · Python 3.12 en imágenes y CI

`python:3.12-slim` en las imágenes, Python 3.12 en el CI y en el `.venv` local (`requires-python >=
3.12`). Versión estable, con soporte de seguridad y *wheels* para todas las dependencias: lo que se
prueba es lo que se ejecuta.

### ADR-019 · Argon2id (argon2-cffi) para las contraseñas (revisada)

**Alternativas.** SHA-256 con sal (demasiado rápido); PBKDF2 (sin dureza de memoria); bcrypt
(límite de 72 bytes); **Argon2id**.

**Decisión.** Argon2id mediante `argon2-cffi` con sus parámetros por defecto (variante Argon2id, 3
iteraciones, 64 MiB de memoria, perfil de RFC 9106). Es el algoritmo recomendado por OWASP. No se
implementa criptografía propia y la biblioteca estándar no incluye Argon2.

**Revisión (2026-11-16).** Ya no hay usuarios ni base de datos: se usa un único hash (ADR-039, ADR-050: en memoria). Una verificación usa unos 64 MiB durante una fracción de segundo;
aceptable con un solo administrador y con el limitador de intentos (ADR-024).

### ADR-021 · CSRF con token sincronizador por sesión + comprobación de `Origin` (revisada)

**Problema.** Con autenticación por cookie, otra web podría hacer que el navegador del administrador
envíe peticiones que modifican datos.

**Alternativas.** Solo `SameSite` (no cubre todos los casos); *double-submit cookie* (cookie legible por
JS); **token sincronizador**.

**Decisión.** Cada sesión tiene un token CSRF aleatorio guardado en el servidor. El navegador lo
recibe en `GET /api/session`, lo guarda solo en memoria y lo envía en `X-CSRF-Token` en las peticiones
que modifican estado (hoy, solo `POST /api/logout`). Además, cualquier petición no segura (incluido el
login) con cabecera `Origin` ajena se rechaza con 403. Los `GET` nunca modifican nada.

### ADR-024 · Limitación de intentos de login en memoria (revisada)

**Decisión.** Ventana deslizante en memoria: tras 5 fallos en 15 minutos desde una IP se responde 429
con `Retry-After` (incluso si la contraseña es correcta) hasta que expire la ventana. Al no haber
nombre de usuario, el límite es solo por IP.

**Alternativas.** Tabla en base de datos (sobrevive a reinicios pero añade escrituras); herramientas
externas (fail2ban; fuera del alcance).

**Limitaciones aceptadas.** El contador se pierde al reiniciar el panel (un atacante no puede
provocarlo) y solo vale con un proceso de uvicorn. Detrás de un proxy inverso habrá que tomar la IP
real de una cabecera de confianza.

---

## Renovación a plataforma de monitorización (2026-11-16)

### ADR-036 · Cambio de objetivo: plataforma de monitorización de solo lectura

**Estado:** Aceptada (2026-11-16, decisión del usuario).

**Contexto.** El objetivo original era una PaaS: catálogo, despliegues, revisiones, *rollback*,
volúmenes, redes y límites. La Fase 3 ya sumaba unas 7 700 líneas de código fuente y 4 500 de
pruebas, y seguían faltando diez fases. Era demasiado amplio para un proyecto universitario que el
equipo debe comprender, explicar y demostrar.

**Alternativas.** (a) Seguir con la PaaS completa. (b) Recortarla a «solo desplegar una imagen». (c)
Cambiar a una plataforma que solo **consulta**.

**Decisión.** Opción (c): plataforma web ligera de **monitorización y consulta** del anfitrión y de
sus contenedores Docker. **Está prohibido** crear, iniciar, parar, borrar o modificar contenedores,
imágenes o volúmenes. Se parte de la Fase 2 (la última aprobada), no de la Fase 3.

**Consecuencias.** Código mucho más pequeño y superficie de ataque menor; se pierde la gestión de
aplicaciones.

### ADR-037 · Agente separado y de solo lectura; el socket `:ro` no limita la API (revisada)

**Estado:** Aceptada (2026-11-16). Revisada el 2026-11-16 por ADR-043 (la consulta incluye los
contenedores detenidos) y por ADR-051 (el agente ya no exige token: lo aísla la red interna).

**Contexto.** Leer la lista de contenedores exige el socket de Docker, que equivale a root en el
anfitrión; el panel está expuesto al navegador.

**Alternativas.** (a) Un solo proceso con el socket: si se compromete el panel, el atacante tiene el
equivalente a root. (b) Dos procesos: panel sin socket y agente interno con socket y solo consultas.

**Decisión.** Opción (b). El **panel** (`server_monitor.panel`) no tiene el socket, no es root, con
`read_only`, `cap_drop: ALL` y `no-new-privileges`. El **agente** (`server_monitor.agent`) está en una
red interna sin puertos publicados, solo ofrece rutas `GET`
y solo hace dos consultas a Docker: `client.api.containers(all=True)` (lista) y `client.version()`
(comprobación de salud). No ejecuta comandos ni es privilegiado.

**Matiz importante.** Montar el socket con `:ro` **no** hace la API de solo lectura: `:ro` afecta al
archivo del socket, no a las peticiones HTTP que viajan por él (crear un contenedor privilegiado seguiría
funcionando). Por eso no se usa como protección: la garantía de solo lectura está **en el código del
agente**, y se comprueba con pruebas y con `docker events`.

**Consecuencias.** Un fallo en el código del agente seguiría dando acceso total a Docker. Mejora
posible, no adoptada (añadiría un componente): un *proxy* del socket que solo deje pasar lecturas.

### ADR-038 · Montaje del `/` del anfitrión en `/hostfs`, solo lectura y sin submontajes

**Estado:** Aceptada (2026-11-16).

**Contexto.** El agente corre en un contenedor: `statvfs("/")` mediría el sistema de archivos del
contenedor, no el disco del anfitrión, y necesita el nombre del SO y el *hostname* reales.

**Alternativas.** (a) Medir el disco que usa Docker (podía no ser el disco raíz). (b) Montar el `/`
del anfitrión en `/hostfs` en solo lectura, como hace `node_exporter`, pero sin submontajes.

**Decisión.** Opción (b): `type: bind`, `read_only: true` y `bind: recursive: disabled`. Sin
recursividad, `/hostfs` no incluye `/proc`, `/sys`, `/home` ni otros discos montados. Se usa para
`statvfs` (disco raíz), `/etc/os-release` y `/etc/hostname`. El agente no es root.

**Consecuencias.** El agente ve el árbol raíz del anfitrión en solo lectura (lo legible por todos los
usuarios). Se verifica en el E2E: no puede escribir y `/hostfs/proc` está vacío. La regla del proyecto
prohíbe montar `/` **con escritura**; este montaje no escribe y no es recursivo (excepción consciente).

### ADR-039 · Sin SQLite: hash de la contraseña en un archivo y sesiones en memoria

**Estado:** Aceptada (2026-11-16). Sustituye a ADR-005, 016, 017, 020 y 022, y en parte a ADR-010 y 018.
**Revisada por ADR-050:** la contraseña ya no se establece con `manage set-password` ni se guarda su
hash en un archivo: se escribe en `docker-compose.yml` (`APP_PASSWORD`) y el hash vive solo en memoria.
Las sesiones en memoria no cambian. El texto de abajo es el original de esta ADR.

**Alternativas.** (a) SQLite para una sola fila. (b) Hash Argon2id en un archivo. (c) Contraseña en una
variable de entorno (queda en `docker inspect`).

**Decisión.** Opción (b). El hash está en `/data/password_hash` (volumen `sms-data`, permisos 600) y se
crea el propio panel al arrancar (originalmente con `manage set-password`, **sustituido por ADR-050**, que elimina también el archivo). Contraseña
única de 4 a 128 caracteres, sin usuario. Las sesiones viven en la memoria del proceso: se pierden
al reiniciar el panel. Los accesos se registran con `logging` (`server_monitor.access`) sin
contraseñas. Del diseño anterior se conserva guardar solo el SHA-256 del identificador de sesión.

**Consecuencias.** Sin migraciones, repositorios ni transacciones. Limitaciones aceptadas: sesiones y
limitador solo valen para un proceso; la longitud mínima de 4 caracteres es decisión del equipo.

### ADR-040 · Métricas con la biblioteca estándar, sin `psutil` (revisada)

**Estado:** Aceptada (2026-11-16).

**Decisión.** Leer `/proc` y `/sys` con Python estándar en vez de `psutil` (una dependencia más, con
parte compilada, para leer unos pocos archivos). CPU por diferencia de dos lecturas de `/proc/stat`
separadas 0,5 s; RAM `MemTotal − MemAvailable`; disco con `os.statvfs` calculado como `df`. Las
funciones reciben las rutas como parámetro para probarlas con directorios falsos.

**Revisión (2026-11-16).** Se añaden los discos extra (ADR-044), la temperatura del paquete del
procesador (ADR-045) y la red (ADR-046), también con la biblioteca estándar. Detalle de cada fórmula en
[04-backend.md](04-backend.md).

**Consecuencias.** Sin dependencias nuevas; cada cálculo se explica fórmula a fórmula. Cada consulta
de `/metrics` tarda unos 0,5 s por la medición de CPU.

### ADR-041 · Consulta HTTP periódica con pausa en pestaña oculta, sin WebSockets

**Estado:** Aceptada (2026-11-16).

**Alternativas.** (a) WebSockets o *Server-Sent Events*: más complejos de probar y de proteger. (b)
Consultar cada 5 s con HTTP normal.

**Decisión.** Opción (b), con `setTimeout` encadenado (la siguiente consulta se programa al terminar
la anterior, así nunca se acumulan). Se pausa con la pestaña oculta (`visibilitychange`), se
reanuda al volver y se detiene al cerrar sesión o al recibir 401.

**Consecuencias.** Los datos tienen hasta 5 s de retraso. La autenticación y el CSRF son los mismos
que en el resto de la API.

---

## Rediseño de interfaz y limpieza (2026-11-16)

Las siete decisiones siguientes se tomaron con la aprobación del usuario el 2026-11-16.

### ADR-042 · Renombrado a Server Monitoring Service

**Estado:** Aceptada.

**Contexto.** El nombre «MiniPaaS» describía el objetivo anterior (una PaaS), que ya no existe.
`controlplane` («plano de control») era también un término de la etapa PaaS.

**Alternativas.** (a) Mantener los nombres por historia. (b) Renombrar todo de una vez.

**Decisión.** Opción (b). Nombre del proyecto **Server Monitoring Service** (abreviatura `SMS`);
paquete `minipaas` → `server_monitor`; `controlplane` → `panel`; variables `MINIPAAS_*` → `SMS_*`;
Dockerfile y requisitos `controlplane` → `panel`; extra de `pyproject.toml` `controlplane` → `panel`;
servicio Compose `panel`; proyecto Compose `sms-dev` (luego `server-monitoring`, ADR-052), redes
`sms-internal` y `sms-public` (luego `internal` y `public`); cookie `sms_session`; logger
`server_monitor.access`; usuarios de las imágenes `sms-panel` (UID 10001) y `sms-agent` (UID 10002).

**Consecuencias.** Todo el código y la documentación vigente usan los nombres nuevos. Los documentos históricos conservan los nombres de su época. Si existía el entorno antiguo
(`minipaas-dev`), hay que bajarlo (`docker compose -p minipaas-dev down`) para liberar el puerto 8000.

### ADR-043 · Contenedores detenidos visibles con la misma llamada de lectura

**Estado:** Aceptada. Revisa ADR-037.

**Contexto.** Hasta ahora solo se listaban los contenedores en ejecución. Un contenedor que se cae
dejaba de aparecer, justo cuando más interesa verlo.

**Alternativas.** (a) Seguir con solo los en ejecución. (b) Una segunda llamada solo para los
detenidos. (c) Quitar el filtro de la llamada existente.

**Decisión.** Opción (c): `client.api.containers(all=True)`, **una sola llamada de lectura**. El estado
se conserva en `state`; los que están en ejecución se ordenan primero y `health` se deduce del texto
de `status` («(healthy)», «(unhealthy)», «(health: starting)»). La interfaz muestra los detenidos con
otro aspecto y el resumen indica cuántos hay de cada tipo.

**Consecuencias.** La superficie del agente no crece (sigue habiendo dos consultas de Docker en total:
lista y versión). El texto de estado de Docker está en inglés (limitación conocida).

### ADR-044 · Discos extra declarados por el administrador en `/disks`

**Estado:** Aceptada.

**Contexto.** El disco raíz no es el único que interesa (p. ej. un disco de datos). Pero el agente
no debe ver todos los discos del anfitrión: ampliaría lo que puede leer.

**Alternativas.** (a) Descubrir los discos automáticamente leyendo los montajes del anfitrión. (b) Que
el administrador declare en Compose qué discos se ven.

**Decisión.** Opción (b). Cada disco extra se monta **en solo lectura** en `/disks/<nombre>`
(p. ej. `- /mnt/datos:/disks/datos:ro` en `docker-compose.yml`). El agente mide el raíz (nombre
«Sistema») y cada subdirectorio de `SMS_DISKS_DIR`, ordenado por nombre; omite los que están en el
mismo sistema de archivos que el raíz (mismo `st_dev`), para no repetir el mismo disco.

**Consecuencias.** Sin montajes extra, solo se ve el raíz. El administrador decide exactamente qué
ve el agente. Añadir un disco exige editar Compose y recrear el contenedor del agente.

### ADR-045 · Temperatura general = paquete del procesador

**Estado:** Aceptada.

**Contexto.** La versión anterior mostraba todos los sensores de `thermal_zone*` (en el equipo de
prueba, 15), muchos sin significado para el usuario y con valores dispares.

**Alternativas.** (a) Mostrar todos. (b) Promediar los sensores (sin sentido físico). (c) Una sola
temperatura: la del paquete del procesador.

**Decisión.** Opción (c). Se busca en `/sys/class/hwmon/hwmon*`: si el controlador es `coretemp`
(Intel), el `temp*_input` cuya etiqueta es `Package id 0`; si es `k10temp` (AMD), el de etiqueta
`Tctl` (o `temp1_input` si no hay etiquetas). Si no hay hwmon válido, la `thermal_zone` de tipo
`x86_pkg_temp`. Se descartan valores ≤ 0 o > 150 °C. Si no hay ninguno, `null` y la interfaz muestra
«No disponible». Nunca se inventa ni promedia.

**Consecuencias.** Una cifra clara y comparable. No cubre procesadores sin esos controladores (p. ej.
muchos ARM): allí se muestra «No disponible».

### ADR-046 · Red del anfitrión vía `/proc/1/net/dev` como único archivo de solo lectura

**Estado:** Aceptada. Sustituye la decisión de no mostrar la red.

**Contexto.** `/proc/net/dev` dentro del agente muestra las interfaces **del contenedor**, no las del
anfitrión. La alternativa habitual, `network_mode: host`, daría al agente la red del anfitrión (y
quitaría el aislamiento de la red interna), lo que la regla del proyecto prohíbe.

**Alternativas.** (a) `network_mode: host` (rechazada). (b) No mostrar la red. (c) Montar un único
archivo: `/proc/1/net/dev` del anfitrión.

**Decisión.** Opción (c): `/proc/1/net/dev:/host/net/dev:ro` y `SMS_NET_DEV=/host/net/dev`. El
archivo es el contador de red del proceso 1 del anfitrión, es decir, de su espacio de nombres de red.
El agente suma `rx_bytes` y `tx_bytes` de las interfaces, excluyendo `lo`, `veth*`, `br-*`, `docker*`
y `virbr*`. Los contadores son acumulados; la **velocidad la calcula el navegador** con dos muestras
seguidas (ADR-047). Comprobado en un contenedor efímero sin red, no root y sin capabilities: se
leen las interfaces reales del anfitrión.

**Consecuencias.** Sin `network_mode: host` ni más privilegios. El total incluye interfaces como
`tailscale0` (VPN) si existen: el total mezcla tráfico físico y de VPN. Si el archivo no existe, la
red es `null` y la interfaz oculta la gráfica de red.

### ADR-047 · Gráficas e indicadores en SVG propio, sin librerías, con histórico en el navegador

**Estado:** Aceptada. Revisa ADR-006.

**Contexto.** El panel necesita indicadores circulares y gráficas de evolución. Y no puede cargar
nada de un CDN (CSP `default-src 'self'`).

**Alternativas.** (a) Chart.js u otra librería (una dependencia más que mantener y que adaptar a la paleta y a
la CSP). (b) SVG dibujado a mano con JavaScript. Histórico: (c) en una base
de datos del servidor; (d) solo en memoria del navegador.

**Decisión.** (b) y (d). `js/charts.js` dibuja el indicador (círculo con `stroke-dasharray`) y la
gráfica de líneas (ejes, rejilla, tooltip, cortes por huecos); `js/history.js` guarda hasta 120
muestras (10 min a una cada 5 s) en la memoria de la pestaña. Al recargar, el histórico empieza de
cero. El servidor no almacena métricas (coherente con ADR-039).

**Consecuencias.** Cero dependencias nuevas y control total del aspecto. A cambio, hay que mantener el
código de las gráficas (216 líneas) y el histórico no sobrevive a recargar ni se comparte entre
pestañas. Limitación: el tooltip no es accesible por teclado (los valores actuales están en la
leyenda).

### ADR-048 · Fuentes e iconos autoalojados por la CSP

**Estado:** Aceptada.

**Contexto.** La CSP `default-src 'self'` impide cargar fuentes o iconos de Google Fonts, de un CDN o
de cualquier otro origen. Además, un panel de monitorización no debería depender de servicios
externos para mostrarse.

**Alternativas.** (a) Relajar la CSP añadiendo orígenes externos. (b) Fuentes del sistema y emojis.
(c) Incluir los archivos en el propio panel.

**Decisión.** Opción (c). Tipografía **IBM Plex Sans** (400/500/600) e **IBM Plex Mono** (400/500)
en `woff2` latino, de los paquetes `@fontsource/ibm-plex-sans@5.2.8` y
`@fontsource/ibm-plex-mono@5.2.7` (licencia SIL OFL 1.1, © IBM Corp.; texto en `web/fonts/OFL.txt`).
18 iconos de **Lucide** (`lucide-static@1.68.0`, licencia ISC; texto en `web/icons-LICENSE.txt`)
reunidos en un *sprite* `web/icons.svg`, junto con la marca propia (arco de 270°, también el favicon).
Son recursos estáticos, **no** dependencias del proyecto: se copian al repositorio y no hay
instalación ni paso de compilación.

**Consecuencias.** La CSP no cambia. Las licencias se citan en [bibliografia.md](bibliografia.md).
Actualizar una fuente o un icono es una operación manual.

---

## Despliegue simplificado (2026-11-16)

### ADR-050 · Contraseña en `docker-compose.yml` con hash en memoria

**Estado:** Aceptada (2026-11-16, decisión del usuario). **Sustituye** a ADR-049 y a lo que aplicaba
de ADR-039 (hash en archivo y volumen `/data`).

**Contexto.** ADR-049 exigía `deploy/.env`, un archivo de hash, un volumen y una variable de
confirmación para cambiar la contraseña: demasiadas piezas para algo que debe entenderse de un vistazo.

**Alternativas.** (a) Mantener ADR-049. (b) Contraseña en un archivo `.env` aparte. (c) Contraseña
visible y editable en el propio `docker-compose.yml`, con el hash calculado solo en memoria.

**Decisión.** Opción (c). El servicio `panel` lleva `APP_PASSWORD: ""` en `docker-compose.yml`. Al
arrancar, `build_app_from_env` la valida (4 a 128 caracteres) y calcula su hash Argon2id **en
memoria**. Si falta, está vacía o no es válida, registra un error claro (sin el valor) y sale con
código 1; con `restart: unless-stopped` Docker reintenta y repite el error. Cambiarla es editar el
archivo y ejecutar `docker compose up -d`, que recrea el panel y cierra las sesiones. Se eliminan el
archivo de hash, el volumen `/data`, `APP_PASSWORD_RESET` y el comando `set-password`.

**Consecuencias.** Un solo lugar de configuración y nada en disco. Riesgo aceptado: la contraseña está
en claro en el `docker-compose.yml` del servidor y se ve con `docker inspect` (quien lo ve ya tiene
acceso a Docker); no hay que subir ese archivo con la contraseña a un repositorio público.

### ADR-051 · Sin token entre panel y agente: aislamiento por red interna

**Estado:** Aceptada (2026-11-16, decisión del usuario). **Sustituye** a ADR-014 (token compartido).

**Contexto.** El token obligaba a secretos de archivo con una copia por componente y propietarios
distintos, y a un script de preparación del entorno con un contenedor efímero. Era mucha maquinaria
para proteger un servicio que ya no es alcanzable desde fuera.

**Alternativas.** (a) Mantener el token. (b) Confiar en el aislamiento de red.

**Decisión.** Opción (b). El agente no publica puertos, la red `internal` tiene `internal: true` (sin
salida a Internet) y solo el panel está en ella. Solo se exponen rutas `GET` de lectura. Se eliminan el
token, `SMS_AGENT_TOKEN_FILE`, `deploy/secrets/` y `common/secrets.py`.

**Consecuencias.** Menos código y ningún secreto que preparar. El E2E comprueba que el agente solo
responde desde la red interna, que no es accesible desde el anfitrión y que no tiene salida a Internet.
Riesgo residual: cualquier contenedor que se conectara a la red `internal` podría consultar al agente
(solo lectura); por eso solo debe usarla el panel.

### ADR-052 · Un único `docker-compose.yml` en la raíz para servidor y desarrollo

**Estado:** Aceptada (2026-11-16, decisión del usuario).

**Contexto.** Había un Compose de desarrollo (`deploy/compose.dev.yaml`), un `.env` generado por
scripts y otro script de verificación: el servidor real y el desarrollo se instalaban de forma distinta.

**Decisión.** Un único `docker-compose.yml` en la raíz (`name: server-monitoring`, servicios `panel` y
`agent`, redes `internal` y `public`, `restart: unless-stopped`) sirve para instalar en un servidor y
para desarrollar. El agente corre sin root (UID 10002) y accede al socket con `group_add: ["999"]`, donde
`999` se cambia por el GID real del servidor (`stat -c %g /var/run/docker.sock`), visible en el propio
archivo. Se eliminan `deploy/compose.dev.yaml`, `deploy/.env*`, `deploy/secrets/`,
`scripts/prepare_dev_env.sh` y `scripts/verify_dev_env.sh` (sus comprobaciones se fusionaron en
`scripts/e2e_monitor.sh`). La instalación es: clonar, editar dos valores y `docker compose up -d --build`.

**Consecuencias.** Menos archivos y un solo camino. Las pruebas E2E usan un *override* temporal (con
`!override`, Compose 2.24 o superior) en lugar de modificar el archivo. Quien edita `APP_PASSWORD` y el
GID modifica un archivo versionado: no debe confirmar esos cambios con la contraseña real.
