# 3. Arquitectura

> Estado del documento: **arquitectura aprobada por el equipo (2026-11-15)**, con los matices
> recogidos en `decisiones.md`. Nada de lo descrito está implementado todavía.

## 3.1 Visión general

MiniPaaS se divide en **dos procesos** con niveles de privilegio distintos, más el runtime Docker:

```mermaid
flowchart LR
    U[Navegador<br/>administrador] -- HTTPS/HTTP + cookie de sesión --> CP

    subgraph MiniPaaS
        CP["<b>Control plane</b> (FastAPI)<br/>API REST + panel web<br/>lógica de aplicaciones y despliegues<br/>monitorización · auditoría"]
        DB[(SQLite<br/>metadatos)]
        AG["<b>Agente runtime</b><br/>API mínima con lista blanca<br/>única pieza con acceso a Docker"]
        CP --- DB
        CP -- "HTTP interno + token<br/>(red Docker interna, sin puertos publicados)" --> AG
    end

    AG -- "/var/run/docker.sock" --> D[Docker Engine]
    D --> A1[App 1<br/>red privada app-1]
    D --> A2[App 2<br/>red privada app-2]
    V[Visitantes] -- puertos publicados<br/>o proxy inverso --> A1
```

| Pieza | Responsabilidad | Privilegios |
|---|---|---|
| **Panel web** | Interfaz HTML/CSS/JS servida por el control plane. Solo habla con la API REST. | Ninguno |
| **Control plane** | Autenticación, validación, modelo de aplicaciones, orquestación de despliegues, monitorización, auditoría, persistencia. | Sin acceso a Docker. Usuario no root. |
| **Agente runtime** | Traduce operaciones permitidas a llamadas de Docker. Vuelve a validar todo con una política de seguridad estricta. | Acceso al socket de Docker. Sin puertos expuestos al exterior. |
| **SQLite** | Configuración deseada, historial de despliegues, usuarios, auditoría, muestras de métricas. | Fichero en un volumen del control plane. |
| **Docker Engine** | Ejecuta los contenedores, redes y volúmenes de las aplicaciones. | — |

### ¿Por qué esta separación?

Quien controla el socket de Docker controla, en la práctica, el host como root (puede crear un
contenedor privilegiado que monte `/`). Por eso el componente expuesto a la red (control plane) **no**
tiene ese acceso. Si un atacante compromete el control plane, solo puede pedir al agente las
operaciones de su lista blanca, y el agente rechaza cualquier especificación peligrosa aunque le
llegue «desde dentro». Es el principio de **mínimo privilegio** y de **defensa en profundidad**.
Las alternativas consideradas están en `decisiones.md` (ADR-002).

## 3.2 Revisión de la arquitectura de partida

El enunciado proponía diez componentes. Se mantienen todas sus responsabilidades, pero no todas
merecen ser un componente independiente: separar en exceso crearía capas que solo se pasan datos
entre sí. Correspondencia:

| Componente propuesto | Dónde queda | Justificación |
|---|---|---|
| Frontend | Panel web (estático, servido por el control plane) | Igual. |
| API / Control Plane | Control plane: capa `api/` | Igual. |
| Application Manager | Control plane: `services/applications.py` | Igual. |
| Deployment Engine | Control plane: `services/deployments.py` | Igual; coordina el despliegue paso a paso. |
| Runtime Adapter | Se divide en **cliente del agente** (control plane) + **agente runtime** (proceso separado) | Es la frontera de privilegios: aquí sí aporta valor separar. |
| Storage Manager | Módulo `spec/storage.py` (validación y nombres de volúmenes) + operaciones de volumen del agente | No tiene estado propio; es política + traducción. |
| Network Manager | Módulo `spec/networking.py` (puertos, rango, conflictos) + operaciones de red del agente | Ídem. |
| Resource Manager | Módulo `spec/resources.py` (límites, cuotas) | Ídem. |
| Monitoring | Control plane: `services/monitoring.py` + lecturas del agente | Igual. |
| Database | SQLite + `db/` (repositorios con SQL explícito) | Igual. |

Los módulos `spec/*` tienen una única tarea: convertir la **configuración de alto nivel** que maneja
el usuario («quiero 512 MB y el puerto 8080») en una **especificación de runtime** validada que el
agente entiende. Así, almacenamiento, red y recursos quedan como piezas pequeñas, testeables y sin
capas artificiales.

## 3.3 Modelo de dominio

> Este es el **modelo objetivo** de todo el proyecto. Lo que existe realmente en la base de datos
> tras la Fase 2 está en el apartado 3.10: las tablas de despliegues, servicios y volúmenes se
> crearán cuando se implemente su funcionalidad.

```mermaid
erDiagram
    APPLICATION ||--o{ DEPLOYMENT : "tiene historial de"
    APPLICATION ||--o{ VOLUME : "posee"
    APPLICATION ||--o| DEPLOYMENT : "despliegue actual"
    DEPLOYMENT ||--|{ SERVICE_SPEC : "contiene (JSON)"
    USER ||--o{ AUDIT_EVENT : "realiza"

    APPLICATION {
        int id
        string name "slug DNS: a-z, 0-9, guiones"
        string description
        string desired_state "running | stopped"
        int current_deployment_id
        datetime created_at
    }
    DEPLOYMENT {
        int id
        int application_id
        int revision "1, 2, 3..."
        json spec "configuración completa congelada"
        string status "pending | deploying | active | failed | superseded"
        string message
        datetime created_at
        datetime finished_at
    }
    SERVICE_SPEC {
        string name
        string image "con etiqueta o digest"
        map env
        list ports
        list volumes
        object resources
        object healthcheck
        string restart_policy
    }
    VOLUME {
        int id
        int application_id
        string name
        datetime created_at
    }
    USER {
        int id
        string username
        string password_hash
    }
    AUDIT_EVENT {
        int id
        datetime at
        string username
        string action
        string target
        string result
    }
```

Decisiones de modelado:

- **La especificación de un despliegue es inmutable.** Cambiar la configuración crea una revisión
  nueva. Esto da historial y *rollback* **de la versión de la aplicación** con poco código, y es la
  misma idea que usan Cloud Foundry (*droplets/releases*) y OpenShift/Kubernetes
  (*ReplicaSets/rollouts*). Los **datos de los volúmenes no forman parte de la revisión** y no se
  revierten (ver 3.5 y ADR-011).
- **Los secretos** se guardan en la especificación, pero la API nunca los devuelve en claro (se
  muestran como `••••`). El cifrado en reposo con una clave de la plataforma se evaluará en la Fase 5.
- **Estado deseado frente a estado real.** La base de datos guarda lo que *debería* estar ocurriendo
  (`desired_state`, despliegue actual). El estado real se consulta a Docker. Un sincronizador
  periódico detecta diferencias (p. ej. un contenedor caído) y las muestra; es una versión sencilla
  del *bucle de reconciliación* de Kubernetes.

## 3.4 Convenciones en Docker

Todo recurso creado por MiniPaaS sigue estas reglas, que son la base de la seguridad frente a los
servicios existentes del servidor:

| Recurso | Nombre | Etiquetas obligatorias |
|---|---|---|
| Contenedor | `minipaas-<app>-<servicio>-r<revisión>` | `minipaas.managed=true`, `minipaas.app`, `minipaas.service`, `minipaas.revision` |
| Red | `minipaas-app-<app>` | `minipaas.managed=true`, `minipaas.app` |
| Volumen | `minipaas-<app>-<volumen>` | `minipaas.managed=true`, `minipaas.app` |

El agente **rechaza** cualquier operación sobre un recurso que no tenga `minipaas.managed=true`,
aunque se le pase su identificador. Así, aunque haya un fallo en el control plane, MiniPaaS no puede
parar ni borrar un contenedor que no es suyo.

## 3.5 Flujo de un despliegue

Estrategia **recreate con restauración automática**: como los puertos publicados son fijos, no se
pueden ejecutar a la vez la versión vieja y la nueva (no es posible *blue-green* sin proxy). Se para
la versión anterior, se arranca la nueva y, si no queda sana, se restaura la anterior.

```mermaid
sequenceDiagram
    autonumber
    actor Admin
    participant CP as Control plane
    participant DB as SQLite
    participant AG as Agente
    participant D as Docker

    Admin->>CP: POST /api/apps/{app}/deployments (configuración)
    CP->>CP: Validar configuración (spec/*)
    CP->>DB: Crear despliegue rN (pending) + auditoría
    CP-->>Admin: 202 Accepted (id del despliegue)
    Note over CP: El resto ocurre en segundo plano,<br/>el panel consulta el estado.
    CP->>AG: ensure_network, ensure_volumes, pull_image
    AG->>AG: Revalidar con la política
    AG->>D: Crear red/volúmenes, descargar imagen
    CP->>AG: stop(servicios de r(N-1))
    CP->>AG: create + start(servicios de rN)
    loop hasta timeout
        CP->>AG: inspect(rN)
        AG->>D: estado + health
    end
    alt rN sano
        CP->>AG: remove(contenedores de r(N-1))
        CP->>DB: rN = active, r(N-1) = superseded
    else rN falla
        CP->>AG: remove(rN) y start(r(N-1))
        CP->>DB: rN = failed (+ motivo)
    end
```

Los volúmenes nunca se borran en un redespliegue: solo al eliminar la aplicación y si el usuario lo
confirma expresamente.

### Rollback: versión de la aplicación frente a datos

Un *rollback* (manual o la restauración automática anterior) **recupera la versión de la
aplicación** —imagen y configuración de una revisión anterior—, pero **no recupera los datos
persistentes**: los volúmenes se reutilizan en el estado en que estén. Si la versión nueva modificó
los datos (por ejemplo, migró el esquema de una base de datos), la versión anterior podría no ser
compatible con ellos. El panel lo advertirá antes de confirmar un *rollback*. MiniPaaS no hace
instantáneas de volúmenes; la exportación manual de un volumen (RF-43, opcional) sería una copia de
seguridad, no un *rollback* de datos.

Para ejecutar los despliegues en segundo plano se usará un único *worker* dentro del control plane
(una cola en memoria procesada por una tarea de `asyncio`), con un candado por aplicación para que
no haya dos despliegues simultáneos de la misma aplicación. No se necesita Celery/Redis a esta
escala. Si el control plane se reinicia a mitad de un despliegue, al arrancar marca como `failed`
los despliegues que quedaron `pending/deploying` y el sincronizador muestra el estado real.

## 3.6 API del agente (borrador)

API HTTP interna, accesible solo desde la red Docker interna de MiniPaaS, autenticada con un token
compartido generado en la instalación. Operaciones previstas (lista cerrada):

| Operación | Descripción | Comprobaciones de la política |
|---|---|---|
| `POST /networks/ensure` | Crea la red privada de una aplicación si no existe | Nombre con prefijo y etiquetas |
| `POST /volumes/ensure`, `DELETE /volumes/{name}` | Crea / borra un volumen con nombre | Prefijo `minipaas-`, etiqueta `managed` |
| `POST /images/pull` | Descarga una imagen | Formato de referencia válido; registros permitidos (configurable) |
| `POST /services` | Crea el contenedor de un servicio a partir de una `ServiceRequest` de alto nivel | El agente construye la configuración (ver abajo) |
| `POST /containers/{id}/{start,stop,restart}`, `DELETE /containers/{id}` | Ciclo de vida | Etiqueta `managed` |
| `GET /containers?app=` | Lista contenedores de una aplicación | Filtra por etiqueta |
| `GET /containers/{id}/logs`, `/stats`, `/inspect` | Lectura de logs, consumo y estado | Etiqueta `managed`; `tail` acotado |
| `GET /host/metrics` | CPU, memoria y disco del host | Solo lectura |

**Principio aprobado: el agente construye la configuración de Docker; nunca la recibe.** La
`ServiceRequest` que acepta `POST /services` **no es una configuración de Docker**: describe el
servicio en términos de MiniPaaS (aplicación, servicio, imagen, variables, puertos internos y del
rango, volúmenes por nombre lógico y ruta interna, límites, health check, política de reinicio). No
existe ningún campo por el que pasar opciones de Docker (`privileged`, `cap_add`, `network_mode`,
`pid`, `ipc`, `devices`, montajes *bind*, `security_opt`, `sysctls`…), y cualquier campo desconocido
provoca el rechazo. Es el agente quien, con valores fijados en su código, traduce esa petición a la
llamada al SDK de Docker. En concreto, el agente aplica siempre:

- `no-new-privileges`, eliminación de capacidades innecesarias cuando la imagen lo permita;
- límites de memoria y CPU obligatorios (con valores por defecto);
- solo volúmenes con nombre del propio prefijo, nunca rutas del host;
- solo puertos del host dentro del rango configurado (p. ej. 20000–20999) y en la interfaz
  configurada;
- conexión únicamente a la red privada de su aplicación.

El agente **no ofrece ninguna operación de ejecución de comandos** (`exec`) ni acceso a terminal.

## 3.7 Monitorización

| Dato | Origen | Forma de obtenerlo |
|---|---|---|
| Estado del contenedor | Docker | `inspect` bajo demanda + sincronizador periódico (≈15 s) |
| Salud | `HEALTHCHECK` de Docker definido en la spec / plantilla | Campo `State.Health` |
| CPU y memoria por servicio | API de estadísticas de Docker | Bajo demanda; muestreo opcional cada 30–60 s guardado en SQLite con retención de 24 h |
| Logs | API de logs de Docker | Últimas N líneas (N acotado), sin almacenarlos |
| Métricas del host | `psutil` en el agente (lee `/proc` del contenedor, que refleja el host para CPU/memoria) | Bajo demanda |

La métrica de disco del host requiere decidir qué ruta se monta en solo lectura para medirla; se
resolverá en la Fase 8 (posiblemente usando la información de Docker sobre el uso de disco, `system df`).

## 3.8 Despliegue de la propia plataforma

MiniPaaS se desplegará como un proyecto Docker Compose con dos contenedores:

```yaml
# Borrador ilustrativo, no definitivo
services:
  controlplane:
    user: "10001:10001"          # no root
    ports: ["127.0.0.1:8000:8000"]  # o la IP de la LAN; se decidirá en la Fase 13
    volumes: ["minipaas-data:/data"]
    networks: [minipaas-internal, default]
    # SIN socket de Docker
  agent:
    volumes: ["/var/run/docker.sock:/var/run/docker.sock"]
    networks: [minipaas-internal]   # red interna: sin salida ni puertos publicados
    read_only: true
    security_opt: ["no-new-privileges:true"]
networks:
  minipaas-internal:
    internal: true
```

> El agente necesita leer/escribir el socket de Docker. Ejecutarlo como no-root requiere que su
> usuario pertenezca al grupo propietario del socket (GID del grupo `docker` del host). Esto se
> documentará en la Fase 3. Sigue siendo el componente más sensible del sistema y así se
> reconoce en el modelo de amenazas (`04-seguridad.md`).

## 3.9 Entornos

| Entorno | Dónde | Uso |
|---|---|---|
| Desarrollo | Máquina local (Docker 29, Compose 5, Python 3.14 detectados) | Desarrollo y pruebas. Proyecto Compose `minipaas-dev`. |
| Integración | Máquina local, mismo Docker, recursos etiquetados `minipaas.test=true` y limpiados tras cada test | Tests automáticos contra Docker real |
| Producción | Servidor doméstico Ubuntu | Solo en la Fase 13 y con autorización expresa |

Las versiones del servidor real (Ubuntu, Docker, puertos ocupados, RAM/CPU) están pendientes de
recopilar y condicionan la Fase 13.

## 3.10 Implementación de la Fase 2: persistencia, sesión y aplicaciones

> Estado: **implementado y verificado** (2026-11-15).

### Esquema real (migración `0001_initial.sql`)

```mermaid
erDiagram
    USERS ||--o{ SESSIONS : "abre"
    USERS |o--o{ AUDIT_EVENTS : "origina (ON DELETE SET NULL)"
    APPLICATION_STATUSES ||--o{ APPLICATIONS : "clasifica"

    USERS {
        int id PK
        text username UK "3-64, sin distinguir mayúsculas"
        text password_hash "Argon2id"
        text created_at
        text updated_at
    }
    SESSIONS {
        int id PK
        text token_hash UK "SHA-256 del identificador de la cookie"
        int user_id FK "ON DELETE CASCADE"
        text csrf_token "token sincronizador"
        text created_at
        text last_seen_at "caducidad por inactividad (30 min)"
        text expires_at "caducidad absoluta (8 h)"
        text revoked_at "NULL si sigue activa"
    }
    APPLICATION_STATUSES {
        text code PK "draft"
        text description "Sin desplegar"
    }
    APPLICATIONS {
        int id PK
        text slug UK "3-40, inmutable"
        text name "1-100"
        text description "0-500"
        text status FK "draft"
        text created_at
        text updated_at
    }
    AUDIT_EVENTS {
        int id PK
        text occurred_at "UTC"
        text event_type "auth.login, application.create..."
        text outcome "success | failure"
        int user_id FK "nullable"
        text resource_type "sin FK: sobrevive al borrado"
        text resource_id
        text client_ip
        text metadata "JSON sin datos sensibles"
    }
    SCHEMA_MIGRATIONS {
        int version PK
        text name
        text applied_at
    }
```

Relaciones: un usuario tiene muchas sesiones (se borran con él); los eventos de auditoría apuntan
opcionalmente al usuario y guardan el recurso afectado como texto, para conservar el rastro aunque el
recurso se elimine; cada aplicación tiene un estado lógico de la tabla de códigos (ADR-023). Las
aplicaciones todavía no se relacionan con usuarios: con un único administrador no aporta nada, y la
auditoría ya registra quién hizo cada operación. El modelo está preparado para que la Fase 3 añada
servicios y despliegues que referencien `applications.id`.

### Módulos del control plane

| Capa | Módulos | Responsabilidad |
|---|---|---|
| Rutas | `api/health.py`, `api/auth.py`, `api/applications.py`, `api/deps.py` | HTTP: validación de entrada (Pydantic, `schemas.py`), códigos de estado, cookies; dependencias de conexión, sesión y CSRF |
| Servicios | `services/auth.py`, `services/applications.py`, `services/audit.py` | Casos de uso y reglas: transacciones, auditoría, errores de dominio |
| Seguridad | `security/passwords.py`, `security/sessions.py`, `security/csrf.py`, `security/rate_limit.py` | Argon2id, sesiones, CSRF y origen, límite de intentos |
| Datos | `repositories/*.py`, `db/connection.py`, `db/migrations.py`, `db/migrations/*.sql` | SQL explícito, conexiones, transacciones, migraciones |
| Utilidades | `clock.py`, `config.py`, `manage.py` | Reloj inyectable (tests de caducidad), configuración, CLI de administración |

`main.py` solo ensambla: crea los servicios, aplica las migraciones al arrancar (`lifespan`), registra
los routers, el middleware de cabeceras y los estáticos. Las rutas no contienen SQL y los repositorios
no deciden transacciones: las abre el servicio, de modo que la operación y su evento de auditoría de
éxito se confirman o se deshacen juntos (ADR-022).

### Flujo de inicio de sesión

```mermaid
sequenceDiagram
    autonumber
    actor A as Administrador
    participant P as Panel (JS)
    participant API as api/auth.py
    participant S as AuthService
    participant DB as SQLite

    A->>P: usuario y contraseña
    P->>API: POST /api/auth/login (JSON)
    API->>API: comprobar Origin
    API->>S: login(...)
    S->>S: ¿bloqueado por intentos? (429)
    S->>DB: buscar usuario
    S->>S: Argon2id verify (hash ficticio si no existe)
    alt credenciales incorrectas
        S->>DB: auditoría auth.login_failed (transacción propia)
        API-->>P: 401 mensaje genérico
    else correctas
        S->>DB: BEGIN IMMEDIATE, revocar sesión previa, crear sesión (hash), auditoría auth.login, COMMIT
        API-->>P: 200 csrf_token + Set-Cookie HttpOnly
    end
    P->>API: POST /api/applications + X-CSRF-Token
    API->>DB: sesión válida y token CSRF correcto
```

### Persistencia en el entorno Docker

La base de datos (`/data/minipaas.sqlite3`, modo WAL) está en el volumen con nombre `minipaas-data` del
control plane; la imagen crea `/data` con propietario UID 10001 para que el volumen se inicialice con
los permisos correctos. El sistema de archivos raíz sigue en solo lectura. El agente no cambia en esta
fase y no tiene acceso a la base de datos.
