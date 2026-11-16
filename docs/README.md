# Documentación de MiniPaaS

El proyecto se renovó el 2026-11-16: de PaaS a plataforma de monitorización de solo lectura. Los
documentos están actualizados a ese objetivo y conservan la etapa anterior como historia.

| Documento | Contenido | Estado |
|---|---|---|
| [01-vision-y-alcance.md](01-vision-y-alcance.md) | Problema, objetivo, alcance, motivo del cambio de objetivo | Reescrito (renovación) |
| [02-requisitos.md](02-requisitos.md) | Requisitos funcionales y no funcionales (RF-M, RNF-M); histórico de los de la etapa PaaS | Reescrito (renovación) |
| [03-arquitectura.md](03-arquitectura.md) | Panel, agente, flujo de una actualización, origen de cada dato | Reescrito (renovación) |
| [04-seguridad.md](04-seguridad.md) | Modelo de amenazas, medidas y riesgo residual | Reescrito (renovación) |
| [05-estrategia-pruebas.md](05-estrategia-pruebas.md) | Niveles de prueba y pruebas implementadas | Reescrito (renovación) |
| [06-roadmap.md](06-roadmap.md) | Situación, fases siguientes e historia de las Fases 0–3 | Reescrito (renovación) |
| [07-estado-del-arte.md](07-estado-del-arte.md) | Cloud, Docker, PaaS de referencia y herramientas de monitorización (7.6) | 7.1–7.5 etapa PaaS; 7.6 nuevo |
| [08-estructura-proyecto.md](08-estructura-proyecto.md) | Estructura real de directorios | Actualizado (renovación) |
| [decisiones.md](decisiones.md) | Registro de decisiones técnicas (ADR 001–041; ADR 025–035 son de la Fase 3 no aprobada) | Vivo |
| [registro-pruebas.md](registro-pruebas.md) | Evidencias de las pruebas ejecutadas (Fases 0–2 y renovación) | Vivo |
| [bibliografia.md](bibliografia.md) | Fuentes y licencias de terceros | Vivo |
| [guia-desarrollo.md](guia-desarrollo.md) | Entorno local: tests, Compose, contraseña, pruebas extremo a extremo | Actualizado (renovación) |
| [api.md](api.md) | API del panel y API interna del agente | Actualizado (renovación) |
| [informes/](informes/) | Informes de cierre: `fase-00`, `fase-01`, `fase-02` y [renovacion-monitorizacion](informes/renovacion-monitorizacion.md) | Uno por etapa |

El informe y las ADR 025–035 de la Fase 3 solo existen en la rama `fase-03-motor-despliegue`, que no
se aprobó y se conserva intacta.

Entregable de la asignatura conservado sin modificar en la raíz del repositorio:
[`formato_preguntas.md`](../formato_preguntas.md) (plantilla del cuestionario GIFT).

Documentos previstos: `guia-instalacion.md` (despliegue en el servidor Ubuntu real, con autorización).

## Convenciones

- Se distingue siempre entre **propuesto**, **implementado** y **verificado**.
- Las decisiones importantes se registran en `decisiones.md`.
- Las pruebas solo se registran como superadas si se han ejecutado, con su comando y resultado.
