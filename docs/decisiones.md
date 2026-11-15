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
