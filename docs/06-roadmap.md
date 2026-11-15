# 6. Roadmap

> Estado del documento: **aprobado por el equipo (2026-11-15)**.

## 6.1 Cambios respecto a la planificación inicial

| Cambio | Motivo |
|---|---|
| **El panel web se construye de forma incremental** desde la Fase 2, en lugar de concentrarlo en la Fase 10. La Fase 10 pasa a ser de *experiencia de usuario y pulido*. | Si la interfaz se deja para el final, cada funcionalidad se valida solo por API y se descubren problemas de usabilidad tarde. Además, se puede enseñar progreso real en cada revisión. |
| **La autenticación entra en la Fase 2** y **el agente privilegiado en la Fase 3**. La Fase 11 pasa a ser de *endurecimiento y auditoría*. | La seguridad es un requisito de diseño: no se puede añadir al final sin rehacer la API ni la integración con Docker. |
| **El agente runtime se introduce en la Fase 3** junto con el modelo de aplicaciones. | Es la única vía de acceso a Docker; todas las fases siguientes dependen de él. |
| **Las aplicaciones multi-servicio se implementan en la Fase 7** (redes), con un solo servicio hasta entonces. | Primero se consolida el ciclo completo con un servicio; la red privada por aplicación es la que habilita varios servicios. |
| **El cuestionario GIFT** (10 preguntas, ver `formato_preguntas.md`) se incluye en la Fase 13. | Es un entregable de la asignatura detectado en el repositorio. |

Estos cambios fueron **aprobados por el equipo el 2026-11-15**.

## 6.2 Fases

| Fase | Nombre | Objetivo y entregables principales | Criterio de aceptación |
|---|---|---|---|
| 0 | Análisis y arquitectura | Requisitos, arquitectura, decisiones, riesgos, estrategia de pruebas, documentación inicial. | Documentación revisada y aprobada. |
| 1 | Estructura y entorno aislado | Estructura de directorios, `pyproject.toml`, `ruff`, `pytest`, Dockerfiles, `compose.dev.yaml` con control plane y agente «hola mundo», CI básica, guía de desarrollo. | `docker compose up` local arranca ambos procesos; el control plane llama al agente; CI en verde; el control plane no ve el socket. |
| 2 | Control plane, base de datos y API básica | SQLite + esquema y migraciones, modelo de aplicaciones (sin Docker), autenticación, CSRF, auditoría, esqueleto del panel (login + lista de aplicaciones). | CRUD de aplicaciones por API y panel con sesión; tests de API en verde. |
| 3 | Agente runtime y ciclo de vida básico | Agente con política y lista blanca; cliente del agente; crear/arrancar/parar/eliminar una aplicación de un servicio desde imagen; sincronización de estado. | Despliegue real de `nginx:alpine` en local; tests de política; contenedor ajeno protegido. |
| 4 | Despliegues, imágenes y plantillas | Revisiones inmutables, despliegue en segundo plano, restauración automática ante fallo, *rollback* de la versión de la aplicación (no de los datos), catálogo de plantillas propias. | Redespliegue y *rollback* verificados con test de integración (incluido que los volúmenes no se alteran); advertencia sobre datos visible en el panel; plantilla desplegada desde el panel. |
| 5 | Configuración: variables y puertos | Variables de entorno y secretos; publicación de puertos en rango; detección de conflictos. | Secretos nunca devueltos por la API; conflicto de puertos detectado antes de desplegar. |
| 6 | Almacenamiento persistente | Volúmenes con nombre, persistencia entre despliegues, tamaño ocupado, borrado con confirmación, exportación opcional. | Dato escrito sobrevive a un redespliegue (test). |
| 7 | Redes y aplicaciones multi-servicio | Red privada por aplicación, varios servicios por aplicación, resolución por nombre, URL de acceso; proxy inverso opcional. | Plantilla web + base de datos funcional; dos aplicaciones no se ven entre sí (test). |
| 8 | Monitorización, logs y health checks | Logs, consumo por servicio, health checks, métricas del host, historial corto con Chart.js. | Datos coherentes con `docker stats`; contenedor no sano detectado. |
| 9 | Recursos y ciclo de vida | Límites obligatorios, cuota global, políticas de reinicio, reconciliación tras reinicio del servidor. | Límite efectivo comprobado (`docker inspect`); estado correcto tras reiniciar Docker. |
| 10 | Experiencia de usuario | Revisión completa de la interfaz: coherencia, textos, errores, confirmaciones, accesibilidad básica, diseño adaptable. | Lista de comprobación de usabilidad superada; prueba con un usuario sin conocimientos de Docker. |
| 11 | Endurecimiento y auditoría de seguridad | Revisión del modelo de amenazas, CSP, limitación de intentos, revisión de dependencias, Docker *rootless* (evaluación). | Todas las amenazas del modelo con mitigación verificada o riesgo aceptado documentado. |
| 12 | Pruebas de integración y evaluación | Batería completa de integración, medición de consumo y tiempos, comparación con requisitos (incluida la verificación del objetivo de diseño de < 250 MB, RNF-07). | Informe de evaluación con resultados reales. |
| 13 | Despliegue final, demostración y documentación | Instalación en el servidor (con autorización), guía de instalación y uso, memoria, presentación, cuestionario GIFT. | Plataforma funcionando en el servidor sin afectar a los servicios existentes; demo preparada. |

## 6.3 Dependencias entre fases

```mermaid
flowchart LR
    F0[0 Análisis] --> F1[1 Estructura] --> F2[2 Control plane] --> F3[3 Agente]
    F3 --> F4[4 Despliegues]
    F4 --> F5[5 Configuración]
    F4 --> F6[6 Almacenamiento]
    F5 --> F7[7 Redes]
    F6 --> F7
    F4 --> F8[8 Monitorización]
    F7 --> F9[9 Recursos]
    F8 --> F9
    F9 --> F10[10 UX] --> F11[11 Seguridad] --> F12[12 Evaluación] --> F13[13 Despliegue final]
```

Las fases 5, 6 y 8 son relativamente independientes entre sí una vez terminada la 4.

## 6.4 Procedimiento de cada fase

1. Rama `fase-NN-nombre` creada desde `main`.
2. Objetivos, requisitos y criterios de aceptación concretos.
3. Diseño (actualizando `03-arquitectura.md` y `decisiones.md` si procede).
4. Implementación con commits pequeños.
5. Pruebas y registro en `registro-pruebas.md`.
6. Revisión de seguridad si la fase añade superficie.
7. Actualización de documentación y `CHANGELOG.md`.
8. Informe para Gemini en `docs/informes/`.
9. Presentación de resultados y **espera de aprobación** antes de fusionar en `main` y comenzar la
   siguiente fase.
