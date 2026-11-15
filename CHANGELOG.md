# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Las versiones se
corresponden con las fases del proyecto.

## [Fase 1] — 2026-11-15 (pendiente de aprobación)

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
- Registro de pruebas, bibliografía e informe de la Fase 0 para Gemini.
- `.gitignore` inicial.
