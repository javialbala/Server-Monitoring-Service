# Decisiones de la etapa PaaS (ADR sustituidas)

> **Documento histórico.** Estas ADR se tomaron entre las Fases 0 y 2 (2026-11-15), cuando el
> proyecto se llamaba MiniPaaS y era una PaaS para desplegar aplicaciones. Las sustituyó (del todo o
> en parte) el cambio de objetivo del 2026-11-16. Se conservan sin modificar el texto original (los
> nombres `minipaas`, `controlplane`, `MINIPAAS_*` son los de su época) porque explican por qué el
> proyecto es como es. Las decisiones vigentes están en [../10-decisiones.md](../10-decisiones.md).
> Las ADR 025 a 035 (motor de despliegue, Fase 3) solo existen en la rama `fase-03-motor-despliegue`.

| ADR | Tema | Sustituida por |
|---|---|---|
| 002 | Acceso a Docker mediante un agente propio que construye la configuración | En parte, ADR-037 (el agente ya no crea nada) |
| 005 | SQLite con el módulo estándar `sqlite3` | ADR-039 |
| 007 | Aplicaciones multi-servicio con red privada por aplicación | ADR-036 |
| 008 | Acceso a las aplicaciones: rango de puertos y proxy inverso opcional | ADR-036 |
| 009 | Fuentes de despliegue: imágenes y plantillas propias | ADR-036 |
| 010 | Autenticación con un único administrador y sesiones en servidor | En parte, ADR-039 |
| 011 | Despliegue *recreate* con restauración; *rollback* de aplicación, no de datos | ADR-036 |
| 012 | Ejecución en segundo plano con un *worker* `asyncio` interno | ADR-036 |
| 016 | Migraciones propias: archivos SQL numerados y tabla de versiones | ADR-039 |
| 017 | Conexiones SQLite por petición, transacciones explícitas y WAL | ADR-039 |
| 018 | Sesiones en servidor con el identificador guardado como hash | En parte, ADR-039 (se conserva el hash; sesiones en memoria) |
| 020 | Administrador inicial creado por CLI explícita e idempotente | ADR-039 (`set-password`) |
| 022 | Auditoría transaccional con metadatos filtrados | ADR-039 (registro en log) |
| 023 | Estado lógico en tabla de códigos; slug inmutable; borrado definitivo | ADR-036 |

### Historial de aprobaciones de la Fase 0

| Fecha | Revisión del equipo |
|---|---|
| 2026-11-15 | Aprobada la arquitectura general y las ADR 002, 007, 008, 009 y 010, con matices: (1) el agente construye internamente la configuración Docker y nunca acepta parámetros Docker arbitrarios (ADR-002); (2) el *rollback* recupera la versión de la aplicación, no sus datos persistentes (ADR-011); (3) el consumo < 250 MB es un objetivo de diseño hasta poder medirlo (RNF-07); (4) un único usuario administrador (ADR-010); (5) se mantiene el rango de puertos y el proxy inverso es opcional (ADR-008). |

---

## ADR-002 · Acceso a Docker mediante un agente propio que construye la configuración

> **Sustituida en parte por ADR-037 (2026-11-16).** Se mantiene la idea de separar el agente (único con el socket) del panel; deja de aplicar todo lo relativo a crear contenedores, la `ServiceRequest`, la lista blanca de escritura y la etiqueta `minipaas.managed`: el agente ya no crea ni modifica nada.

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

## ADR-005 · SQLite con el módulo estándar `sqlite3`

> **Sustituida por ADR-039 (2026-11-16).** La renovación elimina SQLite por completo.

**Alternativas.** SQLAlchemy/SQLModel (ORM), PostgreSQL.

**Decisión.** SQLite (modo WAL) con SQL explícito en un módulo de repositorios y migraciones
numeradas sencillas (tabla `schema_version`).

**Motivo.** Un único escritor y pocos datos: SQLite basta y no consume recursos. Sin ORM, cada
consulta se lee y se explica directamente; el esquema es pequeño. PostgreSQL sería otro servicio que
mantener sin beneficio a esta escala.

**Consecuencias.** Hay que escribir a mano el mapeo filas ↔ objetos (poco código). Si el esquema
creciera mucho, se podría reconsiderar un ORM.

## ADR-007 · Aplicaciones multi-servicio con red privada por aplicación

> **Sustituida por ADR-036 (2026-11-16).** Ya no hay aplicaciones ni redes por aplicación.

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

> **Sustituida por ADR-036 (2026-11-16).** Ya no se publican puertos de aplicaciones.

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

> **Sustituida por ADR-036 (2026-11-16).** Ya no se despliega nada desde imágenes ni plantillas.

**Alternativas.** Imágenes de registro; plantillas propias validadas; ficheros Compose subidos por el
usuario; construcción desde código/Git (*buildpacks* o Dockerfile).

**Estado:** Aceptada (2026-11-15).

**Decisión.** Imágenes + plantillas propias en un formato YAML sencillo que se traduce a la
misma configuración validada. Sin Compose arbitrario (saltaría la política de seguridad) y sin
construcción desde código (coste de CPU/disco y superficie de ataque), que queda como extensión
opcional.

## ADR-010 · Autenticación con un único administrador y sesiones en servidor

> **Sustituida en parte por ADR-039 (2026-11-16).** Se mantienen la sesión en servidor, la cookie `HttpOnly`/`SameSite=Strict`, el CSRF y la limitación de intentos; ahora hay una contraseña única (sin usuario), el hash va en un archivo y las sesiones viven en memoria.

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

> **Sustituida por ADR-036 (2026-11-16).** Ya no hay despliegues ni *rollback*.

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

> **Sustituida por ADR-036 (2026-11-16).** Sin despliegues no hay trabajos en segundo plano.

**Alternativas.** Celery + Redis; RQ; ejecución síncrona en la petición HTTP; *worker* interno.

**Decisión.** Una cola en memoria procesada por una tarea `asyncio` del control plane, con un candado
por aplicación. El estado de cada despliegue se persiste en SQLite, de modo que la cola en sí no
necesita sobrevivir a reinicios.

**Motivo.** Sin servicios adicionales; suficiente para un solo servidor; fácil de explicar.

## ADR-016 · Migraciones propias: archivos SQL numerados y tabla de versiones

> **Sustituida por ADR-039 (2026-11-16).** Sin base de datos no hay migraciones.

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

> **Sustituida por ADR-039 (2026-11-16).** Sin base de datos no hay conexiones ni transacciones.

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

> **Sustituida en parte por ADR-039 (2026-11-16).** Se conserva guardar solo el SHA-256 del identificador; las sesiones ya no están en SQLite sino en memoria.

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

## ADR-020 · Administrador inicial creado por CLI explícita e idempotente

> **Sustituida por ADR-039 (2026-11-16).** Ya no hay administrador con usuario: la orden es `manage set-password`.

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

## ADR-022 · Auditoría transaccional con metadatos filtrados

> **Sustituida por ADR-039 (2026-11-16).** No hay tabla de auditoría; los accesos se registran con `logging` (logger `minipaas.access`).

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

> **Sustituida por ADR-036 (2026-11-16).** Ya no existen aplicaciones, estados lógicos ni slugs.

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
