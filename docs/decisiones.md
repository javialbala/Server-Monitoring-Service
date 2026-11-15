# Registro de decisiones técnicas (ADR)

Cada decisión sigue el formato *Architecture Decision Record*: contexto, alternativas, decisión y
consecuencias.

Estados posibles:

- **Propuesta**: requiere la aprobación del equipo.
- **Aceptada**: decisión menor dentro de los criterios acordados, o ya aprobada.
- **Sustituida**: reemplazada por otra ADR (se indica cuál).

| ADR | Tema | Estado |
|---|---|---|
| 001 | Runtime: Docker Engine en un solo nodo | Aceptada |
| 002 | Acceso a Docker mediante un agente propio que construye la configuración | **Aceptada con matices** (2026-11-15) |
| 003 | Integración con Docker mediante el SDK oficial de Python | Aceptada |
| 004 | Backend en Python con FastAPI | Aceptada |
| 005 | SQLite con el módulo estándar `sqlite3` | Aceptada |
| 006 | Panel en HTML/CSS/JS sin framework ni compilación | Aceptada |
| 007 | Aplicaciones multi-servicio con red privada por aplicación | **Aceptada** (2026-11-15) |
| 008 | Acceso a las aplicaciones: rango de puertos y proxy inverso opcional | **Aceptada** (2026-11-15) |
| 009 | Fuentes de despliegue: imágenes y plantillas propias | **Aceptada** (2026-11-15) |
| 010 | Autenticación con un único administrador y sesiones en servidor | **Aceptada con matices** (2026-11-15) |
| 011 | Despliegue *recreate* con restauración; *rollback* de aplicación, no de datos | Aceptada (matizada el 2026-11-15) |
| 012 | Ejecución en segundo plano con un *worker* `asyncio` interno | Aceptada |
| 013 | `uv` y `uv.lock` en desarrollo, CI e imágenes (exportado con hashes) | Aceptada (Fase 1, revisada) |
| 014 | Token compartido como *secret* de archivo: una copia 600 por componente | Aceptada (Fase 1, revisada) |
| 015 | Python 3.12 en imágenes y CI | Aceptada (Fase 1) |
| 016 | Migraciones propias: archivos SQL numerados y tabla de versiones | Aceptada (Fase 2) |
| 017 | Conexiones SQLite por petición, transacciones explícitas y WAL | Aceptada (Fase 2) |
| 018 | Sesiones en servidor con el identificador guardado como hash | Aceptada (Fase 2) |
| 019 | Argon2id (argon2-cffi) para las contraseñas | Aceptada (Fase 2) |
| 020 | Administrador inicial creado por CLI explícita e idempotente | Aceptada (Fase 2) |
| 021 | CSRF con token sincronizador por sesión + comprobación de `Origin` | Aceptada (Fase 2) |
| 022 | Auditoría transaccional con metadatos filtrados | Aceptada (Fase 2) |
| 023 | Estado lógico de la aplicación en tabla de códigos; slug inmutable; borrado definitivo | Aceptada (Fase 2) |
| 024 | Limitación de intentos de login en memoria | Aceptada (Fase 2) |

### Historial de aprobaciones

| Fecha | Revisión del equipo |
|---|---|
| 2026-11-15 | Aprobada la arquitectura general y las ADR 002, 007, 008, 009 y 010, con matices: (1) el agente construye internamente la configuración Docker y nunca acepta parámetros Docker arbitrarios (ADR-002); (2) el *rollback* recupera la versión de la aplicación, no sus datos persistentes (ADR-011); (3) el consumo < 250 MB es un objetivo de diseño hasta poder medirlo (RNF-07); (4) un único usuario administrador (ADR-010); (5) se mantiene el rango de puertos y el proxy inverso es opcional (ADR-008). |

---

## ADR-001 · Runtime: Docker Engine en un solo nodo

**Contexto.** El servidor doméstico ya usa Docker Engine y Compose y tiene recursos limitados.

**Alternativas.**

| Opción | Ventajas | Inconvenientes |
|---|---|---|
| **Docker Engine** | Ya instalado; ligero; API estable y documentada; conocido por el equipo | Un solo nodo; el socket da privilegios de root |
| Kubernetes (K3s, MicroK8s) | Estándar de la industria; reconciliación, despliegues, servicios | Consumo base de cientos de MB; mucha complejidad conceptual; la PaaS se limitaría a envolver Kubernetes |
| Docker Swarm | Servicios, réplicas y *rolling updates* integrados | Pensado para varios nodos; añade una capa que no aporta en un servidor |
| Podman | *Rootless* y sin demonio por defecto; API compatible con Docker | No es lo que usa el servidor; cambiaría su configuración |

**Decisión.** Docker Engine directamente. Construir nosotros la capa de aplicaciones y despliegues
sobre Docker es precisamente el valor académico del proyecto.

**Consecuencias.** No hay alta disponibilidad ni escalado multi-nodo (limitación documentada). Como
el agente habla la API de Docker, Podman podría usarse en el futuro con cambios mínimos.

## ADR-002 · Acceso a Docker mediante un agente propio que construye la configuración

**Estado:** Aceptada con matices (2026-11-15).

**Contexto.** Alguien tiene que hablar con Docker. Dar el socket al proceso expuesto a la red
equivale a dar root sobre el host a cualquiera que lo comprometa.

**Alternativas.**

| Opción | Ventajas | Inconvenientes |
|---|---|---|
| Socket montado en el backend | Lo más sencillo | Viola las reglas de seguridad del proyecto; un fallo en la API = control del host |
| *docker-socket-proxy* (proxy que filtra el socket) | Pieza existente; filtra por tipo de endpoint | Filtra rutas y métodos, **no el contenido**: si se permite crear contenedores, se permite crearlos privilegiados o montando `/` |
| **Agente propio con API de lista blanca** | La política se aplica sobre el contenido; solo existen las operaciones necesarias; protege recursos ajenos por etiqueta; muy explicable | Código adicional que mantener y probar |
| Agente propio como servicio *systemd* en el host | Igual que el anterior, sin contenedor | Instalación más intrusiva en el servidor; más difícil de reproducir en local |
| Docker *rootless* | Reduce el impacto de un compromiso | Complementario, no sustitutivo; cambia la configuración del servidor |

**Decisión.** Agente propio en un contenedor separado, sin puertos publicados, en una red Docker
`internal`, autenticado con token, con API mínima y política estricta que se aplica aunque la
petición venga del control plane. Docker *rootless* se evaluará en la Fase 11 como mejora.

**Matiz aprobado: el agente construye la configuración, no la recibe.** El agente **nunca acepta
parámetros de Docker** (ni un diccionario de opciones para `containers.create`, ni campos como
`privileged`, `cap_add`, `devices`, `network_mode`, `pid`, `ipc`, `binds`, `security_opt` o
`sysctls`). Lo que recibe es una descripción de alto nivel y cerrada de un servicio:

| Recibe (validado) | Ejemplo |
|---|---|
| Aplicación y servicio (nombres lógicos) | `blog`, `web` |
| Referencia de imagen | `nginx:1.27-alpine` |
| Variables de entorno | `{"TZ": "Europe/Madrid"}` |
| Puertos: puerto interno → puerto del host dentro del rango | `80 → 20001` |
| Volúmenes: nombre lógico → ruta absoluta dentro del contenedor | `datos → /var/lib/data` |
| Límites de memoria y CPU | `256 MB`, `0.5 CPU` |
| Health check (comando de la imagen o petición HTTP) y política de reinicio | — |

A partir de ella, el agente **construye él mismo** la llamada a Docker con valores fijos en el
código: nombre y etiquetas con prefijo, red de la aplicación, volúmenes con nombre propio
(`minipaas-<app>-<volumen>`, nunca rutas del host), puertos solo en el rango y la interfaz
configurados, `no-new-privileges`, sin capacidades añadidas y límites siempre presentes. Cualquier
campo desconocido provoca el rechazo de la petición. Así, la seguridad no depende de que el control
plane «se porte bien»: aunque se comprometa, solo puede pedir cosas que el agente sabe construir de
forma segura.

**Consecuencias.** El agente es el componente más crítico: debe ser pequeño, estar muy probado y no
ofrecer `exec`. Añadir una opción nueva de Docker exige modificar el agente de forma consciente
(es intencionado). El riesgo residual (compromiso del propio agente) se documenta.

## ADR-003 · Integración con Docker mediante el SDK oficial de Python

**Alternativas.** SDK `docker` (docker-py), invocar la CLI `docker` con `subprocess`, generar ficheros
Compose y ejecutar `docker compose`.

**Decisión.** SDK oficial de Python, usado solo en el agente.

**Motivo.** Respuestas estructuradas y errores tipados; no hay construcción de comandos de shell (se
elimina el riesgo de inyección); no requiere instalar la CLI en la imagen. Generar Compose sería
cómodo pero ocultaría precisamente lo que queremos explicar y obligaría a usar `subprocess`.

## ADR-004 · Backend en Python con FastAPI

**Alternativas.** Flask, Django, Node.js (Express), Go.

**Decisión.** FastAPI + Pydantic + Uvicorn.

**Motivo.** Validación declarativa con Pydantic (clave para la seguridad), documentación OpenAPI
automática (útil como documentación de la API), soporte `async` para el *worker* y las consultas a
Docker, ligero, y Python es el lenguaje que mejor conoce el equipo. Django aporta mucho que no
necesitamos; Go sería más eficiente pero menos accesible para el equipo.

## ADR-005 · SQLite con el módulo estándar `sqlite3`

**Alternativas.** SQLAlchemy/SQLModel (ORM), PostgreSQL.

**Decisión.** SQLite (modo WAL) con SQL explícito en un módulo de repositorios y migraciones
numeradas sencillas (tabla `schema_version`).

**Motivo.** Un único escritor y pocos datos: SQLite basta y no consume recursos. Sin ORM, cada
consulta se lee y se explica directamente; el esquema es pequeño. PostgreSQL sería otro servicio que
mantener sin beneficio a esta escala.

**Consecuencias.** Hay que escribir a mano el mapeo filas ↔ objetos (poco código). Si el esquema
creciera mucho, se podría reconsiderar un ORM.

## ADR-006 · Panel en HTML/CSS/JS sin framework ni compilación

**Alternativas.** React/Vue/Svelte (con paso de compilación), HTMX.

**Decisión.** HTML, CSS y JavaScript moderno (módulos ES) servidos como estáticos por FastAPI;
Chart.js incluido localmente solo para las gráficas.

**Motivo.** Sin cadena de compilación ni `node_modules`; cualquier miembro del equipo puede leerlo;
suficiente para un panel de pocas pantallas. Se mantendrá ordenado con un módulo JS por vista y un
cliente de API común.

**Consecuencias.** Hay que ser disciplinados con la estructura y con el escape de datos (XSS).

## ADR-007 · Aplicaciones multi-servicio con red privada por aplicación

**Contexto.** El título habla de *aplicaciones distribuidas*. Muchas aplicaciones reales necesitan
varios procesos (web + base de datos).

**Alternativas.** (a) Una aplicación = un contenedor; (b) **una aplicación = N servicios** en una red
privada propia; (c) todas las aplicaciones en una red compartida.

**Estado:** Aceptada (2026-11-15).

**Decisión.** (b). Las Fases 3–6 trabajan con un servicio; la Fase 7 habilita varios.
Cada aplicación tiene su red `bridge`, con DNS por nombre de servicio y aislamiento entre
aplicaciones.

**Consecuencias.** Modelo algo más complejo, pero refleja servicios distribuidos y aislamiento de
red, que son temas centrales de la asignatura.

## ADR-008 · Acceso a las aplicaciones: rango de puertos y proxy inverso opcional

**Alternativas.**

| Opción | Ventajas | Inconvenientes |
|---|---|---|
| **Publicar puertos del host dentro de un rango** (p. ej. 20000–20999) | Simple, transparente, sin componentes extra | URLs con puerto (`http://servidor:20001`) |
| Proxy inverso (Caddy o Traefik) con nombres (`app.casa.lan`) | URLs limpias; TLS posible | Componente extra; requiere DNS local o comodín; puede chocar con un proxy ya existente en el servidor (80/443) |

**Estado:** Aceptada (2026-11-15).

**Decisión.** Publicación de puertos en el rango **20000–20999** (configurable) como mecanismo base
(Fases 5 y 7). El proxy inverso es una **funcionalidad opcional** (requisito RF-52, prioridad
«podría») que solo se abordará en la Fase 7 si hay tiempo y si el servidor lo permite; se necesita
saber si ya hay algo escuchando en 80/443.

## ADR-009 · Fuentes de despliegue: imágenes y plantillas propias

**Alternativas.** Imágenes de registro; plantillas propias validadas; ficheros Compose subidos por el
usuario; construcción desde código/Git (*buildpacks* o Dockerfile).

**Estado:** Aceptada (2026-11-15).

**Decisión.** Imágenes + plantillas propias en un formato YAML sencillo que se traduce a la
misma configuración validada. Sin Compose arbitrario (saltaría la política de seguridad) y sin
construcción desde código (coste de CPU/disco y superficie de ataque), que queda como extensión
opcional.

## ADR-010 · Autenticación con un único administrador y sesiones en servidor

**Estado:** Aceptada con matices (2026-11-15).

**Alternativas.** Sin autenticación (inaceptable); HTTP Basic; JWT; sesiones en servidor con cookie;
proveedor externo (OIDC).

**Decisión.** Un **único** usuario administrador creado en la instalación mediante un script,
contraseña con hash Argon2 (o bcrypt), sesiones guardadas en SQLite e identificadas por una cookie
aleatoria `HttpOnly`, `SameSite=Strict` (y `Secure` con HTTPS), token CSRF, caducidad por
inactividad y limitación de intentos fallidos.

**Motivo.** Las sesiones en servidor se pueden revocar (cerrar sesión de verdad) y son más simples
de explicar y asegurar que JWT en un panel web de un solo origen.

**Matiz aprobado.** Se empieza con un único administrador. Varios usuarios y roles (p. ej. solo
lectura) quedan fuera del alcance inicial. Aun así, la tabla de usuarios y el registro de auditoría
guardan el nombre de usuario, de modo que añadir más usuarios en el futuro no obligue a rediseñar.

## ADR-011 · Despliegue *recreate* con restauración; *rollback* de aplicación, no de datos

**Contexto.** Con puertos fijos del host, la versión nueva y la vieja no pueden escuchar a la vez.

**Decisión.** Parar la revisión anterior, arrancar la nueva, esperar a que esté sana (health check o
estado `running` estable) y, si falla, eliminar la nueva y volver a arrancar la anterior.

**Matiz aprobado (2026-11-15): qué recupera un *rollback* y qué no.**

| Concepto | ¿Se recupera? | Cómo |
|---|---|---|
| **Versión de la aplicación**: imagen, variables, puertos, límites, health check (la especificación de la revisión) | **Sí** | Se crea una revisión nueva copiando la especificación de la revisión elegida y se despliega con el flujo normal. |
| **Datos persistentes** (contenido de los volúmenes) | **No** | Los volúmenes se reutilizan tal como están. MiniPaaS no guarda instantáneas de los datos. |

Consecuencias que deben comunicarse al usuario (en la interfaz y en la documentación):

- Volver a una versión anterior **no deshace** los cambios que la versión nueva haya hecho en los
  datos (por ejemplo, una migración del esquema de una base de datos). La versión anterior podría no
  ser compatible con esos datos.
- La restauración automática tras un despliegue fallido tiene la misma limitación.
- El único mecanismo previsto relacionado con datos es la **exportación manual de un volumen**
  (RF-43, prioridad «podría»). Si llega a implementarse, se documentará como copia de seguridad
  manual, no como *rollback* de datos. No se promete recuperación de datos sin un mecanismo real.

**Consecuencias.** Breve corte de servicio en cada despliegue (aceptable en un entorno doméstico).
Con el proxy inverso de la ADR-008 se podría evolucionar a *blue-green*.

## ADR-012 · Ejecución en segundo plano con un *worker* `asyncio` interno

**Alternativas.** Celery + Redis; RQ; ejecución síncrona en la petición HTTP; *worker* interno.

**Decisión.** Una cola en memoria procesada por una tarea `asyncio` del control plane, con un candado
por aplicación. El estado de cada despliegue se persiste en SQLite, de modo que la cola en sí no
necesita sobrevivir a reinicios.

**Motivo.** Sin servicios adicionales; suficiente para un solo servidor; fácil de explicar.

## ADR-013 · `uv` y `uv.lock` en desarrollo, CI e imágenes

**Contexto.** El sistema no tiene `pip` global y hace falta un entorno reproducible para el equipo y
el CI.

**Alternativas.** `venv` + `pip` + `requirements.txt`; Poetry; **uv**.

**Decisión.** `uv` para crear el entorno virtual, resolver dependencias y fijarlas en `uv.lock`
(versionado). Las herramientas de desarrollo (`pytest`, `pytest-cov`, `ruff`) van en un grupo `dev`
de `[dependency-groups]`, que no se instala en las imágenes.

**Revisión (2026-11-15): las imágenes también usan el bloqueo.** En la primera versión, las imágenes
hacían `pip install .`, de modo que pip resolvía las versiones en el momento de construir (y además
descargaba la herramienta de build `hatchling` sin versión fija). Alternativas valoradas:

| Opción | Valoración |
|---|---|
| Instalar `uv` en la imagen y usar `uv sync --frozen` | Añade una herramienta más a la imagen o una etapa extra; innecesario |
| **Exportar `uv.lock` a `requirements` con hashes** (`uv export`) e instalar con `pip --require-hashes` | Sin herramientas nuevas en la imagen; mismo tamaño; además verifica la integridad (SHA-256) de cada paquete |

Se elige la exportación. `scripts/export_requirements.sh` genera `deploy/requirements/controlplane.txt`
y `deploy/requirements/agent.txt` (versionados); los Dockerfiles los instalan con
`pip install --require-hashes` y copian el código en `PYTHONPATH` sin instalarlo como paquete. El CI
regenera los archivos y falla si no coinciden con `uv.lock`.

**Consecuencias.** Construcciones reproducibles y verificadas por hash; tamaño de imagen igual
(203/208 MB frente a 204/209 MB). Coste: tras cambiar dependencias hay que ejecutar
`scripts/export_requirements.sh` (el CI lo recuerda). La imagen base `python:3.12-slim` sigue
referenciada por etiqueta, no por *digest*: se fijará antes del despliegue final (Fase 11/13).

## ADR-014 · Token compartido como *secret* de archivo: una copia 600 por componente

**Contexto.** Control plane y agente comparten un token. Debe llegar a ambos procesos sin quedar
expuesto.

**Alternativas.** Variable de entorno; *secret* de Docker Compose (archivo montado en
`/run/secrets/`).

**Decisión.** *Secret* de Compose. Las variables de entorno son visibles con `docker inspect` y se
heredan por los procesos hijos; un archivo montado no. Los procesos leen la ruta de
`MINIPAAS_AGENT_TOKEN_FILE`, exigen un mínimo de 32 caracteres y **no arrancan** si falta. La
comparación usa `hmac.compare_digest` (tiempo constante) y responde igual si el token falta o es
incorrecto.

**Permisos (revisión del 2026-11-15).** Sin Swarm, Compose monta cada *secret* como un *bind mount*
del archivo del host, con su propietario y sus permisos, e **ignora** `uid`, `gid` y `mode`
(verificado con Compose 5.6.1: «not supported outside Swarm mode»). Por eso, con un único archivo
`600` de tu usuario, los UID 10001 y 10002 recibían `Permission denied`, y la primera versión usó
`644`. Alternativas valoradas:

| Opción | Valoración |
|---|---|
| `644` dentro de un directorio `700` (primera versión) | Funciona, pero el archivo es legible por «otros»; rechazada en la revisión |
| `640` con un grupo compartido | Sigue sin ser `600` y añade un grupo en el host |
| Mismo UID para ambos contenedores o el UID del desarrollador | Pierde la separación de identidades entre componentes |
| Contenedor de arranque como root que copie el token | Un proceso root más en cada arranque |
| **Una copia del mismo token por componente, `600`, con propietario el UID de su contenedor**, directorio `700` | Mínimo privilegio: cada archivo solo lo lee el proceso que lo necesita (ni siquiera el usuario del host) |

Se elige la última. `scripts/prepare_dev_env.sh` crea `controlplane_token` (UID 10001) y
`agent_token` (UID 10002). Asignar un archivo a otro UID requiere root en el host: en lugar de pedir
`sudo`, el script usa un contenedor efímero sin red que solo escribe esos dos archivos. No concede
privilegios nuevos, porque quien usa Docker ya tiene un acceso equivalente a root (ADR-002).
`scripts/verify_dev_env.sh` comprueba los permisos en el host y que cada contenedor lee su archivo con
su propio UID. Para producción (Fase 13) se aplicará el mismo esquema.

## ADR-015 · Python 3.12 en imágenes y CI

**Contexto.** El equipo de desarrollo tiene Python 3.14; el servidor ejecutará las imágenes.

**Decisión.** `python:3.12-slim` en las imágenes, Python 3.12 en el CI y en el `.venv` local
(`requires-python >= 3.12`). Es una versión estable, con soporte de seguridad y con *wheels* para
todas las dependencias. Lo que se prueba es lo que se ejecuta.

## ADR-016 · Migraciones propias: archivos SQL numerados y tabla de versiones

**Problema.** El esquema de SQLite debe crearse de forma reproducible, evolucionar entre fases y
permitir saber qué versión está instalada.

**Alternativas.**

| Opción | Ventajas | Inconvenientes |
|---|---|---|
| Alembic | Estándar, autogeneración | Pensado para SQLAlchemy (que no usamos, ADR-005); dependencia y conceptos extra |
| `CREATE TABLE IF NOT EXISTS` al arrancar | Mínimo | No permite cambiar tablas existentes ni saber la versión |
| **Archivos `NNNN_nombre.sql` + tabla `schema_migrations`** | Cada cambio es SQL legible; versión consultable; ~100 líneas de Python | Hay que escribir a mano las migraciones (incluidas las que reconstruyen tablas) |

**Decisión.** Mecanismo propio. Cada migración se aplica en su propia transacción
`BEGIN IMMEDIATE`, releyendo la versión dentro de la transacción (dos procesos a la vez no la
aplican dos veces). No se usa `executescript`, porque hace un `COMMIT` implícito y rompería la
atomicidad: el SQL se divide en sentencias con `sqlite3.complete_statement`. Si la base de datos tiene
una versión mayor que la que conoce el código, el control plane no arranca (protección ante una
vuelta atrás del código). Las migraciones se aplican al arrancar el control plane y también con
`manage migrate`.

## ADR-017 · Conexiones SQLite por petición, transacciones explícitas y WAL

**Problema.** Varias peticiones simultáneas (y la CLI) usan el mismo archivo sin corromperlo ni
bloquearse indefinidamente.

**Decisión.**

- Una conexión por petición (dependencia de FastAPI que la abre y siempre la cierra).
- `isolation_level=None`: el módulo `sqlite3` no abre transacciones implícitas; cada escritura va en
  una transacción explícita `BEGIN IMMEDIATE … COMMIT/ROLLBACK`. `IMMEDIATE` toma el bloqueo de
  escritura al empezar, lo que evita errores al «promocionar» una lectura a escritura.
- `PRAGMA foreign_keys=ON` en cada conexión (no es persistente en SQLite) y `busy_timeout` de 5 s.
- `journal_mode=WAL`: los lectores no bloquean al escritor; adecuado para un panel con pocas escrituras.
- La base de datos vive en un **volumen con nombre** (`minipaas-data`, montado en `/data`): sobrevive a
  `restart`, `down` y reconstrucciones de imagen; solo `down -v` la borra.

**Alternativas descartadas.** Conexión global compartida (requiere serializar el acceso a mano); pool
de conexiones (innecesario a esta escala); `executescript`/transacciones implícitas (comportamiento
menos evidente).

## ADR-018 · Sesiones en servidor con el identificador guardado como hash

**Problema.** Mantener la sesión del administrador de forma revocable y sin que una copia de la base
de datos permita suplantarlo.

**Alternativas.** Cookie firmada sin estado (no se puede revocar de verdad); JWT (mismo problema y más
complejidad); **sesión en SQLite**.

**Decisión.** Identificador de 256 bits (`secrets.token_urlsafe(32)`) enviado solo en la cookie
`minipaas_session` (`HttpOnly`, `SameSite=Strict`, `Path=/`, `Secure` configurable para HTTPS,
`Max-Age` igual a la duración absoluta). En SQLite se guarda **solo su SHA-256**: quien lea la base de
datos no obtiene cookies válidas. Basta un hash rápido (no Argon2) porque el identificador es aleatorio
y largo, no adivinable como una contraseña. Caducidad absoluta de 8 h y por inactividad de 30 min;
revocación al cerrar sesión; el login siempre crea un identificador nuevo y revoca el anterior del
navegador (evita la fijación de sesión).

## ADR-019 · Argon2id (argon2-cffi) para las contraseñas

**Problema.** Guardar la contraseña del administrador de forma que una filtración de la base de datos
no permita recuperarla.

**Alternativas.** SHA-256 con sal (demasiado rápido: vulnerable a fuerza bruta); PBKDF2 (biblioteca
estándar, pero sin dureza de memoria); bcrypt (bueno, pero limita a 72 bytes); **Argon2id**.

**Decisión.** Argon2id mediante `argon2-cffi`, con sus parámetros por defecto (perfil de RFC 9106:
64 MiB, 3 iteraciones, 4 hilos). Es el algoritmo recomendado por OWASP y ganó la *Password Hashing
Competition*. Es la única dependencia nueva de la fase: no implementamos criptografía propia y la
biblioteca estándar no incluye Argon2. Al iniciar sesión se recalcula el hash si los parámetros han
cambiado. Si el usuario no existe se verifica igualmente contra un hash ficticio para no revelar su
existencia por el tiempo de respuesta.

**Coste.** Cada verificación usa unos 64 MiB de memoria durante una fracción de segundo; aceptable con
un único administrador y con el limitador de intentos (ADR-024).

## ADR-020 · Administrador inicial creado por CLI explícita e idempotente

**Problema.** Crear el primer administrador sin contraseñas por defecto, sin credenciales en el código
y sin exponer la contraseña.

**Alternativas.**

| Opción | Problema |
|---|---|
| Usuario/contraseña por defecto | Prohibido; el típico fallo de seguridad |
| Variable de entorno con la contraseña | Visible con `docker inspect` (mismo motivo que ADR-014) |
| Asistente web «primer arranque» | Quien llegue primero al panel se queda con él |
| *Secret* de archivo generado | El token de la Fase 1 no es legible por el usuario del host (ADR-014); habría que mostrarle la contraseña de algún modo |
| **CLI dentro del contenedor (`manage create-admin`)** | Requiere acceso a la terminal del servidor, que es justo quien debe poder crearlo |

**Decisión.** `python -m minipaas.controlplane.manage create-admin --username <u>` ejecutado con
`docker compose exec`. La contraseña se pide con `getpass` (dos veces) o se lee de la entrada estándar
con `--password-stdin` (para scripts); **nunca** como argumento, porque quedaría en el historial y en
la lista de procesos. Si ya existe un administrador, termina con código 1 y no modifica nada. Se
registra el evento `admin.create`. El panel muestra el comando cuando aún no hay administrador
(`setup_required`), sin revelar nada más.

## ADR-021 · CSRF con token sincronizador por sesión + comprobación de `Origin`

**Problema.** Con autenticación por cookie, otra web podría hacer que el navegador del administrador
envíe peticiones que modifican datos.

**Alternativas.** Solo `SameSite` (no protege frente a subdominios del mismo sitio ni en todos los
navegadores); *double-submit cookie* (requiere una cookie legible por JS); **token sincronizador**.

**Decisión.** Cada sesión tiene un token CSRF aleatorio guardado en servidor. El frontend lo recibe en
el JSON de `login` y de `GET /api/auth/session`, lo guarda solo en memoria y lo envía en la cabecera
`X-CSRF-Token` en `POST`/`PATCH`/`DELETE`; el servidor lo compara en tiempo constante (403 si falta o
no coincide). Como defensa adicional, cualquier petición no segura (incluido el login, que aún no tiene
sesión) con cabecera `Origin` ajena se rechaza. Las peticiones `GET` nunca modifican datos de negocio.
Una web ajena no puede leer el token porque no hay cabeceras CORS que lo permitan.

## ADR-022 · Auditoría transaccional con metadatos filtrados

**Problema.** Registrar las operaciones relevantes sin almacenar secretos y sin que una operación
fallida deje un registro de éxito.

**Decisión.**

- Tabla `audit_events` (tipo, fecha UTC, resultado `success`/`failure`, usuario, recurso, IP,
  metadatos JSON).
- Los eventos de **éxito** se escriben **en la misma transacción** que la operación: si la operación
  falla, el `ROLLBACK` elimina también el evento. Los de **fallo** se escriben después, en una
  transacción aparte.
- El recurso se guarda como texto (`resource_type`, `resource_id`) sin clave foránea, para que el
  evento sobreviva al borrado del recurso; el usuario es clave foránea con `ON DELETE SET NULL`.
- Los metadatos solo admiten valores simples y rechazan claves que contengan `password`, `token`,
  `csrf`, `cookie`, `secret`, `authorization` o `session` (error de programación detectado en tests).
- Los intentos de login fallidos no guardan el usuario escrito (podría ser una contraseña tecleada en
  el campo equivocado); las modificaciones guardan los nombres de los campos cambiados, no sus valores.

## ADR-023 · Estado lógico en tabla de códigos; slug inmutable; borrado definitivo

**Estado lógico.** En esta fase una aplicación solo puede estar **registrada sin desplegar**
(`draft`). No se inventan estados de ejecución: los estados del ciclo de vida se añadirán cuando
existan los despliegues (Fase 3–4). Se guarda como clave foránea a `application_statuses` en lugar de
un `CHECK`, porque en SQLite cambiar un `CHECK` exige reconstruir la tabla y añadir un código es un
simple `INSERT` en una migración. El estado lógico (qué quiere el usuario) se mantendrá separado del
estado real de los contenedores, que se consultará a Docker.

**Slug.** Identificador legible (`^[a-z][a-z0-9-]{1,38}[a-z0-9]$`, sin `--`), derivado del nombre si
no se indica. Es **inmutable** porque en la Fase 3 formará parte de los nombres de redes, volúmenes y
contenedores (`minipaas-<slug>-…`): cambiarlo obligaría a renombrar recursos Docker.

**Borrado.** Definitivo (no lógico): en esta fase una aplicación no tiene recursos asociados que
limpiar, y el evento de auditoría conserva el rastro. La Fase 3 revisará el borrado cuando haya
contenedores y volúmenes (relacionado con RF-19).

## ADR-024 · Limitación de intentos de login en memoria

**Problema.** Impedir la fuerza bruta contra el formulario de acceso.

**Decisión.** Ventana deslizante en memoria: tras 5 fallos en 15 minutos, por IP **o** por nombre de
usuario, se responde 429 con `Retry-After` (incluso si la contraseña es correcta) hasta que expire la
ventana. Un acceso correcto reinicia el contador del usuario.

**Alternativas.** Tabla en SQLite (sobrevive a reinicios, pero añade escrituras y limpieza); proxy
externo (fail2ban, etc.; fuera del alcance).

**Limitaciones aceptadas.** El contador se pierde al reiniciar el control plane (el atacante no puede
provocar ese reinicio) y solo es válido con un único proceso de uvicorn, que es la configuración del
proyecto. Detrás de un proxy inverso habrá que tomar la IP real de una cabecera de confianza.
