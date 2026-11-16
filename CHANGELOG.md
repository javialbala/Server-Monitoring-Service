# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Las versiones se
corresponden con las fases del proyecto y con la renovación.

## [Renovación: plataforma de monitorización] — 2026-11-16 (pendiente de aprobación)

Cambio de objetivo aprobado por el usuario (ADR-036): de PaaS a plataforma web ligera de
**monitorización y consulta de solo lectura**. Rama `renovacion-monitorizacion`, creada desde la
Fase 2. La Fase 3 (rama `fase-03-motor-despliegue`) no se aprobó y se conserva intacta.

### Añadido

- Agente de solo lectura: `GET /health`, `/metrics` (CPU, RAM, disco, SO, kernel, hostname, uptime,
  temperaturas) y `/containers` (contenedores en ejecución, con proyecto y servicio de Compose).
- Métricas con la biblioteca estándar leyendo `/proc`, `/sys` y `statvfs`, sin `psutil`.
- Montaje del `/` del anfitrión en `/hostfs`, solo lectura y sin submontajes.
- Panel con tarjetas de métricas y tabla de contenedores, actualizados cada 5 s con pausa en
  pestaña oculta.
- Contraseña única con CLI `manage set-password` (hash Argon2id en `/data/password_hash`).
- `scripts/e2e_monitor.sh` (29 comprobaciones) y `scripts/e2e_ui.py` (11, con Playwright vía `uvx`).
- ADR-036 a ADR-041; informe `docs/informes/renovacion-monitorizacion.md`.

### Cambiado

- Sesiones en memoria; el límite de intentos de login pasa a ser solo por IP.
- Documentación (01 a 08, api, guía) reescrita; las ADR obsoletas quedan marcadas como sustituidas.
- 48 tests (antes 214 en la Fase 2); 1 492 líneas de código fuente (antes 2 967).

### Eliminado

- SQLite, migraciones, repositorios, auditoría en BD, aplicaciones, usuarios (`create-admin`),
  `MINIPAAS_DB_PATH` y `scripts/e2e_phase2.sh`.
- Sin cambios en dependencias (`pyproject.toml`, `uv.lock` y `deploy/requirements`).

## [Fase 2] — 2026-11-15 (pendiente de aprobación)

### Añadido

- SQLite con migraciones versionadas propias (`db/migrations/0001_initial.sql`), WAL, claves
  foráneas y transacciones explícitas; volumen persistente `minipaas-data`.
- Modelo de aplicaciones sin Docker (slug inmutable, estado lógico `draft`) y API REST CRUD.
- Autenticación de un único administrador: Argon2id, sesiones en servidor con identificador
  guardado como hash, caducidad, revocación, renovación y límite de intentos.
- Protección CSRF (token sincronizador + `Origin`) y auditoría transaccional sin secretos.
- CLI `python -m minipaas.controlplane.manage` (`migrate`, `db-version`, `create-admin`).
- Panel: inicio de sesión, lista, alta, detalle con edición y borrado, navegación y cierre de sesión.
- `scripts/e2e_phase2.sh`; `verify_dev_env.sh` pasa a 12 comprobaciones; `docs/api.md`;
  ADR-016 a ADR-024; 214 tests.

### Cambiado

- Dependencias separadas por componente (extras `controlplane` y `agent`); `uv sync --all-extras`.
- `/docs` y `/redoc` desactivados (dependían de un CDN).

## [Fase 1] — 2026-11-15 (aprobada)

### Añadido

- Paquete `minipaas` (`src/`) con `common`, `controlplane` y `agent` en versión mínima.
- Agente: `GET /health` autenticado con token; comprobación de Docker; sin documentación OpenAPI.
- Control plane: `GET /api/health`, cabeceras de seguridad y panel «Estado del sistema».
- Token compartido como *secret* de archivo (ADR-014).
- Dockerfiles con usuarios sin privilegios y `deploy/compose.dev.yaml` con red interna, socket solo
  en el agente, `read_only`, `cap_drop: ALL` y `no-new-privileges`.
- Scripts `prepare_dev_env.sh` y `verify_dev_env.sh`.
- 32 tests unitarios y de API, 1 de integración; CI con GitHub Actions.
- `docs/guia-desarrollo.md`; ADR-013 (uv), ADR-014 (token), ADR-015 (Python 3.12).

### Cambiado (revisión del equipo)

- Token: una copia por componente con permisos `600` y propietario el UID de su contenedor,
  directorio `700` (antes un único archivo `644`). `prepare_dev_env.sh --rotate` para renovarlo.
- Imágenes construidas desde `uv.lock` exportado con hashes (`deploy/requirements/*.txt`,
  `pip --require-hashes`), sin instalar el paquete ni descargar `hatchling`.
- `scripts/export_requirements.sh` y comprobación en el CI de que coincide con `uv.lock`.
- `verify_dev_env.sh` pasa de 7 a 10 comprobaciones (permisos del secret).

## [Fase 0] — 2026-11-15 (aprobada)

### Cambiado (tras la revisión del equipo)

- ADR-002, 007, 008, 009 y 010 pasan a *Aceptadas*, con matices.
- ADR-002: el agente construye internamente la configuración de Docker a partir de una
  `ServiceRequest` de alto nivel y nunca acepta parámetros de Docker (antes `RuntimeSpec`).
- ADR-011: se distingue el *rollback* de la versión de la aplicación (sí) del de los datos
  persistentes (no); actualizados RF-16, RF-17, RF-43, arquitectura, riesgos y pruebas.
- ADR-010: un único usuario administrador; roles fuera del alcance inicial.
- RNF-07: el consumo < 250 MB queda como objetivo de diseño hasta poder medirlo.
- Se versiona `formato_preguntas.md` sin modificaciones para que no se pierda.
- Informe de la Fase 0 actualizado con aprobaciones, identificadores de commits y resultado real del
  *push*.

### Añadido

- Documentación inicial: visión y alcance, requisitos, arquitectura, seguridad y riesgos, estrategia
  de pruebas, roadmap, estado del arte, estructura del proyecto.
- Registro de decisiones técnicas (ADR-001 a ADR-012).
- Registro de pruebas, bibliografía e informe de la Fase 0.
- `.gitignore` inicial.
