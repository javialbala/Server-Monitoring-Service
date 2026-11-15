# Documentación de MiniPaaS

| Documento | Contenido | Estado |
|---|---|---|
| [01-vision-y-alcance.md](01-vision-y-alcance.md) | Problema, objetivo, alcance, restricciones, usuarios | Aprobado (2026-11-15) |
| [02-requisitos.md](02-requisitos.md) | Requisitos funcionales y no funcionales con prioridad y fase | Aprobado (2026-11-15) |
| [03-arquitectura.md](03-arquitectura.md) | Componentes, modelo de dominio, flujo de despliegue, API del agente | Aprobado (2026-11-15) |
| [04-seguridad.md](04-seguridad.md) | Modelo de amenazas, riesgos, cumplimiento de reglas de seguridad | Aprobado (2026-11-15) |
| [05-estrategia-pruebas.md](05-estrategia-pruebas.md) | Niveles de prueba y cómo se prueba cada componente | Aprobado (2026-11-15) |
| [06-roadmap.md](06-roadmap.md) | Fases, criterios de aceptación y dependencias | Aprobado (2026-11-15) |
| [07-estado-del-arte.md](07-estado-del-arte.md) | NIST SP 800-145, Docker, OpenShift, Cloud Foundry, Stackato, PaaS ligeras | Primera versión |
| [08-estructura-proyecto.md](08-estructura-proyecto.md) | Estructura de directorios prevista | Aprobado (2026-11-15) |
| [decisiones.md](decisiones.md) | Registro de decisiones técnicas (ADR) | Vivo |
| [registro-pruebas.md](registro-pruebas.md) | Evidencias de las pruebas ejecutadas | Vivo |
| [bibliografia.md](bibliografia.md) | Fuentes, licencias de terceros, uso de IA | Vivo |
| [informes/](informes/) | Informes de cierre de fase para Gemini | Uno por fase |

Entregable de la asignatura conservado sin modificar en la raíz del repositorio:
[`formato_preguntas.md`](../formato_preguntas.md) (plantilla del cuestionario GIFT; se completará en
un archivo aparte en la Fase 13).

Documentos previstos para fases posteriores: `api.md` (Fase 2), `guia-instalacion.md` (Fases 1 y
13), `guia-uso.md` (Fase 10).

## Convenciones

- Se distingue siempre entre **propuesto**, **implementado** y **verificado**.
- Las decisiones importantes se registran en `decisiones.md` antes de implementarse.
- Las pruebas solo se registran como superadas si se han ejecutado, con su comando y resultado.
