# Informe de cierre — Fase 0: Análisis, requisitos, arquitectura y documentación inicial

> Informe autocontenido para Gemini (memoria académica y presentación).
> Proyecto: **MiniPaaS** — *«Diseño e implementación de una plataforma PaaS ligera para el despliegue
> y gestión de aplicaciones distribuidas»*. Asignatura: Gestión de Sistemas de Archivos y Servicios
> Distribuidos (GSASD).

---

## A. Identificación

| Campo | Valor |
|---|---|
| Fase | 0 — Análisis, requisitos, arquitectura y documentación inicial |
| Fecha | 2026-11-15 |
| Objetivo | Analizar el punto de partida, definir alcance y requisitos, diseñar la arquitectura, elegir tecnologías, identificar riesgos, definir la estrategia de pruebas, ajustar el roadmap y crear la documentación base. |
| Estado | **Completada y aprobada por el equipo (2026-11-15)**, con los matices del apartado B.6. Fase 1 no iniciada: requiere autorización expresa. |

Importante: en esta fase **no se ha implementado código** ni se ha desplegado ningún servicio. Todo
lo descrito sobre la plataforma es **diseño propuesto**, no funcionalidad implementada.

---

## B. Trabajo realizado

### B.1 Análisis del repositorio de partida

- Repositorio `javialbala/server-monitoring-service` en GitHub, clonado en local.
- Estado encontrado: rama `main` **sin ningún commit**; remoto vacío (sin ramas); un único archivo sin
  seguimiento, `formato_preguntas.md`.
- `formato_preguntas.md` es la **plantilla del cuestionario de la asignatura**: 10 preguntas en
  formato GIFT de Moodle, 4 opciones por pregunta, una correcta (`=`) y tres incorrectas
  (`~%-50%`), categoría `$CATEGORY: $course$/Valor por defecto para Gestion de Archivos y Servicios
  Distribuidos/<Trabajo>-<Apellidos>`. Se ha identificado como **entregable obligatorio** y se ha
  incorporado a la Fase 13. Por indicación del equipo se ha **versionado sin ninguna modificación**
  en su ubicación original (commit `8dc4833`), verificando que su SHA-256 es idéntico antes y después
  (`af7d4826…f694`).
- No existía código del antiguo *Server Control Center* en el repositorio: el proyecto parte de cero.
- Entorno local de desarrollo verificado: Python 3.14.8, Docker 29.9.2, Docker Compose 5.6.1; el
  usuario pertenece al grupo `docker`.

### B.2 Documentos creados

| Archivo | Contenido |
|---|---|
| `README.md` | Presentación del proyecto, estado actual, arquitectura en una frase, enlaces |
| `CHANGELOG.md` | Registro de cambios por fase |
| `.gitignore` | Exclusión de entornos, cachés, bases de datos locales y secretos (`.env`, claves) |
| `docs/README.md` | Índice de la documentación y convenciones |
| `docs/01-vision-y-alcance.md` | Problema, objetivo, definición de aplicación/despliegue, alcance dentro/fuera, restricciones, usuarios |
| `docs/02-requisitos.md` | 34 requisitos funcionales y 17 no funcionales con prioridad MoSCoW y fase prevista |
| `docs/03-arquitectura.md` | Componentes, revisión de la arquitectura de partida, modelo de dominio, convenciones Docker, flujo de despliegue, API del agente, monitorización, despliegue de la plataforma, entornos |
| `docs/04-seguridad.md` | Activos, modelo de amenazas (13 amenazas), riesgo residual, riesgos de proyecto, cumplimiento de las reglas de seguridad |
| `docs/05-estrategia-pruebas.md` | Niveles de prueba, pruebas por componente, reglas de integración, CI |
| `docs/06-roadmap.md` | Roadmap ajustado con criterios de aceptación y dependencias |
| `docs/07-estado-del-arte.md` | NIST SP 800-145, Docker, OpenShift, Cloud Foundry, Stackato, PaaS ligeras, conceptos de GSASD |
| `docs/08-estructura-proyecto.md` | Estructura de directorios propuesta y justificación |
| `docs/decisiones.md` | 12 decisiones técnicas en formato ADR |
| `docs/registro-pruebas.md` | Registro de validaciones ejecutadas |
| `docs/bibliografia.md` | Fuentes, licencias de terceros y declaración de uso de IA |
| `docs/informes/fase-00.md` | Este informe |
| `formato_preguntas.md` | Plantilla del cuestionario GIFT, versionada **sin modificar** |

Archivos modificados tras la revisión del equipo: todos los documentos de `docs/`, `README.md` y
`CHANGELOG.md`, para incorporar las aprobaciones y matices (apartado B.6). Archivos eliminados:
ninguno.
Dependencias añadidas: ninguna.

### B.3 Arquitectura propuesta (resumen)

Dos procesos con privilegios distintos sobre Docker Engine:

1. **Control plane** (Python + FastAPI, sin privilegios, sin acceso a Docker): API REST, panel web
   (HTML/CSS/JS), autenticación, validación, gestión de aplicaciones y despliegues, monitorización,
   auditoría, base de datos SQLite.
2. **Agente runtime** (proceso separado, único con acceso al socket de Docker): API interna mínima
   con una lista cerrada de operaciones. **No recibe parámetros de Docker**: recibe una descripción
   de alto nivel del servicio (`ServiceRequest`: imagen, variables, puertos del rango, volúmenes por
   nombre lógico, límites, health check) y **construye él mismo** la configuración de Docker con
   valores seguros fijos. Rechaza campos desconocidos; solo actúa sobre recursos etiquetados
   `minipaas.managed=true`; sin puertos expuestos; sin `exec`.

Comunicación: HTTP sobre una red Docker interna (`internal: true`) con token compartido.

Conceptos del dominio: **Aplicación** (unidad lógica con nombre, 1..N servicios, red privada propia),
**Despliegue** (revisión inmutable y numerada de la configuración completa), **Volumen** (persistente,
sobrevive a los redespliegues), **Usuario**, **Evento de auditoría**.

Flujo de despliegue: estrategia *recreate* con restauración automática (parar revisión anterior →
arrancar la nueva → comprobar salud → si falla, restaurar la anterior), ejecutado en segundo plano
por un *worker* `asyncio` con un candado por aplicación. El *rollback* (manual o automático)
recupera la **versión de la aplicación** (imagen y configuración), **no los datos persistentes**.

### B.4 Decisiones técnicas adoptadas

| ADR | Decisión | Estado |
|---|---|---|
| 001 | Docker Engine en un nodo (no Kubernetes, Swarm ni Podman) | Aceptada |
| 002 | Agente propio como única vía hacia Docker; construye la configuración, nunca acepta parámetros Docker | **Aceptada con matices** |
| 003 | SDK oficial de Docker para Python (no CLI ni Compose generado) | Aceptada |
| 004 | Python + FastAPI + Pydantic | Aceptada |
| 005 | SQLite con `sqlite3` estándar y SQL explícito (sin ORM) | Aceptada |
| 006 | Panel HTML/CSS/JS sin framework ni compilación; Chart.js local | Aceptada |
| 007 | Aplicaciones multi-servicio con red privada por aplicación | **Aceptada** |
| 008 | Acceso por rango de puertos 20000–20999; proxy inverso opcional | **Aceptada** |
| 009 | Despliegue desde imágenes y plantillas propias (sin Compose arbitrario ni builds) | **Aceptada** |
| 010 | Un único usuario administrador, sesiones en servidor, CSRF | **Aceptada con matices** |
| 011 | Despliegue *recreate* con restauración; *rollback* de aplicación, no de datos | Aceptada (matizada) |
| 012 | *Worker* `asyncio` interno (sin Celery/Redis) | Aceptada |

### B.5 Cambios en el roadmap

1. Panel web incremental desde la Fase 2; la Fase 10 pasa a ser de experiencia de usuario y pulido.
2. Autenticación en la Fase 2 y agente privilegiado en la Fase 3; la Fase 11 pasa a ser de
   endurecimiento y auditoría de seguridad.
3. Aplicaciones multi-servicio en la Fase 7 (antes, un servicio por aplicación).
4. Cuestionario GIFT añadido a la Fase 13.

Estos cambios del roadmap fueron **aprobados por el equipo** el 2026-11-15.

### B.6 Revisión del equipo: aprobaciones y matices (2026-11-15)

El equipo aprobó la arquitectura general y las ADR 002, 007, 008, 009 y 010, con estos matices,
ya incorporados a la documentación:

| # | Matiz | Dónde se ha reflejado |
|---|---|---|
| 1 | El agente **construye internamente** las configuraciones permitidas y **nunca acepta parámetros de Docker arbitrarios** que permitan elevar privilegios, montar rutas peligrosas o acceder al host. El contrato pasa a llamarse `ServiceRequest` (antes `RuntimeSpec`) para dejar claro que no es una configuración de Docker. | ADR-002; `03-arquitectura.md` §3.6; `04-seguridad.md` (A1); RNF-01; estrategia de pruebas; estructura del proyecto |
| 2 | El *rollback* distingue entre **recuperar la versión de la aplicación** (sí: imagen y configuración de una revisión anterior) y **recuperar los datos persistentes** (no: los volúmenes se reutilizan tal como están). No se promete *rollback* de datos porque no existe un mecanismo real; la exportación de volúmenes (RF-43, opcional) sería una copia de seguridad manual. | ADR-011; `03-arquitectura.md` §3.3 y §3.5; RF-16, RF-17, RF-43; alcance; nuevo riesgo en `04-seguridad.md`; criterio de la Fase 4; prueba específica en la estrategia de pruebas |
| 3 | El consumo < 250 MB es un **objetivo de diseño** hasta que pueda medirse. | RNF-07; `01-vision-y-alcance.md` §1.5; Fase 12 del roadmap |
| 4 | Se empieza con un **único usuario administrador**. | ADR-010; RF-01; `01-vision-y-alcance.md` §1.6 y fuera de alcance |
| 5 | Se mantiene el **rango de puertos 20000–20999** y el **proxy inverso es opcional**. | ADR-008 |

Además, se ha versionado `formato_preguntas.md` sin modificar (ver B.1).
---

## C. Justificación académica y técnica

### C.1 Por qué cada tecnología

- **Docker Engine**: ya presente en el servidor; ligero; API documentada. Construir sobre él la capa
  de aplicaciones/despliegues es el núcleo académico del trabajo. Kubernetes se descarta por consumo y
  porque la PaaS se reduciría a envolver Kubernetes.
- **SDK de Docker para Python**: respuestas estructuradas y ausencia de comandos de shell (elimina la
  inyección de comandos).
- **FastAPI + Pydantic**: validación declarativa de entradas (base de la seguridad), documentación
  OpenAPI automática, soporte asíncrono, ligereza.
- **SQLite**: un solo escritor, pocos datos, cero servicios adicionales; sin ORM para que cada
  consulta sea explicable.
- **HTML/CSS/JS sin framework**: sin cadena de compilación; legible por cualquier miembro del equipo.
- **Chart.js**: gráficas de consumo solo donde aporten información; incluido localmente.

### C.2 Problema que resuelve cada componente

| Componente | Problema |
|---|---|
| Control plane | Ofrecer una abstracción de «aplicación» y «despliegue» sobre contenedores, con autenticación y validación. |
| Agente runtime | Aislar el privilegio de Docker (equivalente a root) del componente expuesto a la red. |
| Módulos `spec/` (almacenamiento, red, recursos) | Traducir configuración de alto nivel a una especificación de runtime segura y validada. |
| Revisiones de despliegue inmutables | Historial, trazabilidad y vuelta atrás a una versión anterior de la aplicación (no de sus datos). |
| Etiquetas `minipaas.managed` | Garantizar que la plataforma nunca toca servicios ajenos del servidor. |
| Sincronizador de estado | Detectar diferencias entre estado deseado y real (reconciliación simplificada). |

### C.3 Alternativas consideradas (principales)

- Acceso a Docker: socket en el backend (descartado: inseguro), *docker-socket-proxy* (descartado:
  filtra rutas pero no el contenido; permitir crear contenedores permitiría crearlos privilegiados),
  agente como servicio *systemd* (más intrusivo en el servidor), Docker *rootless* (complementario,
  se evaluará en la Fase 11).
- Runtime: Kubernetes/K3s, Docker Swarm, Podman.
- Persistencia: SQLAlchemy/SQLModel, PostgreSQL.
- Frontend: React/Vue/Svelte, HTMX.
- Tareas en segundo plano: Celery + Redis, RQ.
- Acceso a aplicaciones: puertos frente a proxy inverso (Caddy/Traefik).
- Autenticación: HTTP Basic, JWT, OIDC frente a sesiones en servidor.

### C.4 Ventajas e inconvenientes de la solución

Ventajas: diseñada para ser ligera (objetivo de diseño < 250 MB de RAM, **todavía sin medir**),
comprensible, segura por diseño (mínimo privilegio y defensa en profundidad; el agente construye la
configuración de Docker), protege los servicios existentes, historial de despliegues con vuelta atrás
a versiones anteriores de la aplicación.

Inconvenientes / limitaciones: un solo nodo (sin alta disponibilidad ni escalado horizontal), breve
corte de servicio en cada despliegue (*recreate*), el agente sigue siendo un componente crítico, los
contenedores comparten kernel con el host, los volúmenes locales de Docker no tienen cuota de tamaño,
URLs con puerto si no se usa proxy inverso, y el *rollback* **no revierte los datos persistentes**
(una versión anterior podría no ser compatible con datos modificados por la nueva), un solo usuario
administrador.

### C.5 Conceptos de GSASD aplicados

Modelos de servicio cloud (NIST: MiniPaaS es una PaaS de nube privada), servicios distribuidos (apps
multi-servicio comunicadas por red y DNS; control plane ↔ agente), almacenamiento persistente
(volúmenes, separación datos/cómputo), redes (bridge aisladas, DNS interno, puertos, red interna del
plano de control), virtualización ligera (namespaces, cgroups, capacidades; comparación con máquinas
virtuales), gestión de recursos (límites con cgroups), monitorización (métricas, logs, health checks,
estado deseado frente a real), seguridad (mínimo privilegio, modelo de amenazas), tolerancia a fallos
(restauración automática, políticas de reinicio).

Correspondencia con las características esenciales del NIST: autoservicio bajo demanda (sí), amplio
acceso por red (sí), agrupación de recursos (sí), elasticidad rápida (**parcial**, sin autoescalado),
servicio medido (sí, monitorización por aplicación).

---

## D. Pruebas y resultados

No hay código, por lo que no hay pruebas automáticas. Validaciones **ejecutadas realmente**:

| # | Validación | Comando | Resultado real |
|---|---|---|---|
| 0.1 | Estado del repositorio | `git status`, `git log`, `git ls-remote origin` | `main` sin commits; remoto sin referencias; solo `formato_preguntas.md` sin seguimiento |
| 0.2 | Herramientas locales | `python3 --version`, `docker --version`, `docker compose version` | Python 3.14.8; Docker 29.9.2; Compose 5.6.1 |
| 0.3 | Acceso a Docker | `docker info`, `id -nG` | Demonio accesible; usuario en grupo `docker`; Docker *rootful* con seccomp |
| 0.4 | Enlaces internos | Script Python de comprobación de enlaces relativos | 1.ª ejecución: 2 rotos (directorio `informes/` aún inexistente; ejemplo literal detectado como enlace) → corregidos. 2.ª ejecución: **0 rotos** |
| 0.5 | Secretos | `grep -rniE` con patrones de credenciales y claves privadas | **Sin coincidencias** |
| 0.6 | Diagramas Mermaid | Revisión manual | Se detectó y corrigió un `;` que rompía el diagrama de secuencia. **Pendiente** comprobar el renderizado en GitHub |

Validaciones adicionales tras la revisión del equipo (2026-11-15):

| # | Validación | Comando | Resultado real |
|---|---|---|---|
| 0.7 | Integridad de `formato_preguntas.md` | `sha256sum formato_preguntas.md` antes de versionarlo; `git show HEAD:formato_preguntas.md \| sha256sum`; `git diff --quiet HEAD -- formato_preguntas.md` | Hash idéntico en disco y en Git: `af7d48262e8296a301435dc448af91f58bd84bbef21520ea3a6ef6b12d26f694`; sin diferencias |
| 0.8 | *Push* al remoto | `git push -u origin main` y `git push -u origin fase-00-analisis` (HTTPS) | **Fallido** en todos los intentos: `fatal: could not read Username for 'https://github.com': terminal prompts disabled`. No hay credenciales HTTPS configuradas ni CLI `gh`. Ver apartado F |
| 0.9 | Coherencia tras los cambios | Comprobación de enlaces relativos y búsqueda de restos del nombre antiguo `RuntimeSpec` | 15 archivos, 17 enlaces relativos, **0 rotos**; `RuntimeSpec` solo aparece como nombre antiguo; ninguna ADR queda en estado *Propuesta*; búsqueda de secretos **sin coincidencias** |

Errores encontrados y corregidos: los dos enlaces de la validación 0.4 y el `;` del diagrama de
secuencia (0.6).

Pruebas pendientes: renderizado de diagramas en GitHub; verificación de las afirmaciones marcadas
*(verificar)* en el estado del arte.

No se ha realizado ninguna conexión ni operación sobre el servidor real.

---

## E. Arquitectura y código

No hay código todavía. Módulos **previstos** (estructura completa en `docs/08-estructura-proyecto.md`):

| Módulo previsto | Responsabilidad |
|---|---|
| `minipaas.common.service_request` | Contrato `ServiceRequest` entre control plane y agente: descripción de alto nivel, sin ningún parámetro de Docker |
| `minipaas.common.naming` | Prefijos y etiquetas de los recursos Docker |
| `minipaas.controlplane.api` | Rutas REST |
| `minipaas.controlplane.services` | Aplicaciones, despliegues, monitorización, auditoría |
| `minipaas.controlplane.spec` | Validación y traducción: almacenamiento, red, recursos |
| `minipaas.controlplane.db` | SQLite, esquema, migraciones, repositorios |
| `minipaas.controlplane.security` | Contraseñas, sesiones, CSRF |
| `minipaas.controlplane.agent_client` | Cliente HTTP del agente |
| `minipaas.controlplane.web` | Panel web estático |
| `minipaas.agent.policy` | Política de seguridad del agente |
| `minipaas.agent.docker_runtime` | Llamadas al SDK de Docker |
| `minipaas.agent.host_metrics` | Métricas del host |

Flujo principal: navegador → API del control plane (sesión + CSRF) → validación `spec/` → registro
del despliegue en SQLite → *worker* → cliente del agente → agente (revalidación + comprobación de
etiqueta) → Docker. El estado real vuelve por el mismo camino (lectura), y un sincronizador compara
estado deseado y real.

Diagramas incluidos en `docs/03-arquitectura.md` (formato Mermaid): componentes, modelo entidad-
relación y secuencia de despliegue. `docs/06-roadmap.md`: dependencias entre fases.

---

## F. Git

### Ramas

| Rama | Contenido | Estado |
|---|---|---|
| `main` | Solo el commit inicial `cd2b30f` (necesario porque el repositorio no tenía ningún commit y hacía falta una base para la rama de la fase) | Local |
| `fase-00-analisis` | Todos los commits de la Fase 0 | Local. Fusión en `main` tras la aprobación del equipo y cuando el *push* sea posible |

### Commits (identificadores reales)

| Commit | Rama | Mensaje | Contenido |
|---|---|---|---|
| `cd2b30f` | `main` | `chore: inicializa el repositorio con .gitignore` | `.gitignore` |
| `757f2ce` | `fase-00-analisis` | `docs: documentación inicial de la Fase 0` | `README.md`, `CHANGELOG.md` y los 13 documentos de `docs/` (1550 líneas añadidas) |
| `8dc4833` | `fase-00-analisis` | `docs: conserva sin modificar la plantilla del cuestionario GIFT` | `formato_preguntas.md` sin cambios (SHA-256 verificado) |
| `2f98b85` | `fase-00-analisis` | `docs: incorpora las aprobaciones y matices de la revisión de la Fase 0` | 13 archivos: ADR, requisitos, arquitectura, seguridad, pruebas, roadmap, informe, registro |
| *(commit siguiente)* | `fase-00-analisis` | `docs: registra en el informe de la Fase 0 los commits y el resultado del push` | Este apartado F. Un commit no puede contener su propio identificador; se consulta con `git log` |

### Push: **pendiente (fallido, no simulado)**

| Intento | Comando | Resultado real |
|---|---|---|
| 1 (cierre inicial) | `git push -u origin main`; `git push -u origin fase-00-analisis` | `fatal: could not read Username for 'https://github.com': terminal prompts disabled` |
| 2 (revisión del equipo) | `git push -u origin main` | Mismo error |

Causa: el remoto usa HTTPS y en el entorno no hay credenciales configuradas ni la CLI `gh`. Existe
una clave SSH en el equipo, pero la comprobación de autenticación con GitHub por SSH fue denegada
por los permisos del entorno de ejecución, así que no se ha cambiado la configuración del remoto.

Para completar el *push*, el equipo debe autenticarse (por ejemplo, `gh auth login`, un *token* de
acceso personal o autorizar el uso del remoto SSH) y ejecutar:

```bash
git push -u origin main
git push -u origin fase-00-analisis
```

El remoto `origin` (`github.com/javialbala/server-monitoring-service`) sigue **vacío**.

---

## G. Pendientes

### Decisiones resueltas en la revisión (2026-11-15)

ADR-002, 007, 008, 009 y 010 aprobadas con matices; roadmap aprobado; `formato_preguntas.md`
conservado sin modificar y versionado.

### Cuestiones todavía abiertas (no bloquean la Fase 1)

1. Licencia del repositorio.
2. Nombre del repositorio (`server-monitoring-service` ya no describe el proyecto; se propone
   `minipaas`).
3. Credenciales para hacer *push* a GitHub (apartado F).

### Información necesaria del servidor (antes de la Fase 13; útil desde la Fase 5)

Versión de Ubuntu y de Docker, CPU/RAM/disco disponibles, servicios y puertos ya en uso
(especialmente 80/443 y si existe un proxy inverso), y si se accederá solo desde la LAN o también
desde Internet.

### Limitaciones y riesgos

Un solo nodo; corte breve en cada despliegue; el agente es un punto crítico; kernel compartido;
sin cuotas de disco por volumen; alcance amplio para el tiempo disponible (mitigado con MoSCoW).

### Trabajo para la Fase 1

Estructura de directorios, `pyproject.toml`, `ruff`, `pytest`, Dockerfiles, `compose.dev.yaml` con
control plane y agente mínimos comunicándose, CI con GitHub Actions y guía de desarrollo local.

---

## H. Instrucciones para Gemini

### Qué añadir a la memoria

- **Introducción y motivación** (apartado 1.1 y 1.2 de `01-vision-y-alcance.md`): evolución desde
  *Server Control Center* a una PaaS propia.
- **Marco teórico**: definición NIST SP 800-145 (5 características, 3 modelos de servicio, 4 modelos
  de despliegue), tabla IaaS/PaaS/SaaS, posición de MiniPaaS como PaaS de nube privada y discusión de
  la frontera PaaS/CaaS; fundamentos de contenedores (namespaces, cgroups, imágenes, volúmenes, redes).
- **Estado del arte**: OpenShift, Cloud Foundry, Stackato (histórico), Heroku/12-factor, Dokku,
  CapRover, Coolify, Portainer, y la tabla comparativa.
- **Requisitos**: tablas de requisitos funcionales y no funcionales (se pueden resumir por áreas).
- **Arquitectura**: separación control plane / agente y su justificación de seguridad; modelo de
  dominio; flujo de despliegue *recreate* con restauración; convenciones de etiquetado.
- **Seguridad**: modelo de amenazas y riesgo residual.
- **Metodología**: desarrollo por fases con criterios de aceptación, informes de cierre y registro de
  pruebas.

### Decisiones que debe registrar

Las 12 ADR con su estado. 002, 007, 008, 009 y 010 están **aceptadas** desde el 2026-11-15; 002, 010 y
011 con los matices del apartado B.6. Registrar también el historial de aprobaciones de
`decisiones.md`.

Puntos que deben quedar explícitos en la memoria:

- El agente **construye** la configuración de Docker; nunca recibe parámetros de Docker
  (explicarlo como aplicación del mínimo privilegio y de la validación por lista blanca).
- El *rollback* recupera la **versión de la aplicación**, no los **datos**; explicar por qué
  (los volúmenes son independientes del ciclo de vida de los contenedores) y qué riesgo implica.
- El consumo < 250 MB es un **objetivo de diseño**, no un resultado.
- Un único usuario administrador en esta versión.

### Diagramas que debe crear o actualizar

1. Diagrama de componentes (navegador → control plane → agente → Docker → aplicaciones), resaltando la
   frontera de privilegios.
2. Diagrama entidad-relación (Aplicación, Despliegue, Volumen, Usuario, Evento de auditoría).
3. Diagrama de secuencia del despliegue con restauración automática.
4. Diagrama de dependencias del roadmap.
5. Diagrama IaaS/PaaS/SaaS (pila de responsabilidades) situando MiniPaaS.

### Contenido para la presentación (Canva)

- Diapositiva «¿Qué es MiniPaaS?» con la frase: *el usuario gestiona aplicaciones, no contenedores*.
- Diapositiva «IaaS vs PaaS vs SaaS» con MiniPaaS posicionada.
- Diapositiva «Arquitectura» con el diagrama de componentes y la frontera de privilegios.
- Diapositiva «¿Por qué un agente separado?»: el socket de Docker equivale a root.
- Diapositiva «Comparativa con OpenShift y Cloud Foundry».
- Diapositiva «Roadmap» con las 14 fases.

### Qué NO debe considerar definitivo

- Ninguna funcionalidad está implementada: todo es diseño (aprobado, pero no implementado).
- El objetivo de consumo < 250 MB: no presentarlo como resultado hasta la medición de la Fase 12.
- Ninguna afirmación de recuperación de datos: no existe *rollback* de datos.
- Los datos marcados *(verificar)* en el estado del arte (recursos mínimos de OpenShift de nodo único,
  fecha y destino de la desinversión de Stackato por HPE).
- Los valores numéricos de diseño (rango de puertos 20000–20999, objetivo de 250 MB, intervalos de
  muestreo), que se confirmarán al implementar y medir.
- El nombre «MiniPaaS» y el título del trabajo (provisionales).
