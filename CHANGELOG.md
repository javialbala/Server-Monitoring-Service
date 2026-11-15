# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Las versiones se
corresponden con las fases del proyecto.

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
