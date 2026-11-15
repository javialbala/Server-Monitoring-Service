# 2. Requisitos

> Estado del documento: **aprobado por el equipo (2026-11-15)** con los matices de `decisiones.md`.
> Ningún requisito está implementado todavía.
>
> Prioridad (MoSCoW): **M** = imprescindible, **S** = debería, **C** = podría (si hay tiempo).
> La columna *Fase* indica en qué fase del roadmap se prevé implementarlo.

## 2.1 Requisitos funcionales

### Autenticación y acceso

| ID | Requisito | Prioridad | Fase |
|---|---|---|---|
| RF-01 | El panel y la API exigen iniciar sesión con usuario y contraseña. Existe un único usuario administrador, creado en la instalación (ADR-010). | M | 2 |
| RF-02 | El usuario puede cerrar sesión; las sesiones caducan tras un tiempo de inactividad. | M | 2 |
| RF-03 | Las operaciones relevantes (crear, desplegar, detener, eliminar…) quedan registradas en un log de auditoría consultable. | M | 2–3 |

### Aplicaciones y despliegues

| ID | Requisito | Prioridad | Fase |
|---|---|---|---|
| RF-10 | Listar las aplicaciones con su estado (en ejecución, detenida, desplegando, con errores). | M | 2–3 |
| RF-11 | Crear una aplicación indicando un nombre válido y su configuración. | M | 2 |
| RF-12 | Ver el detalle de una aplicación: servicios, configuración, despliegue actual, estado. | M | 3 |
| RF-13 | Desplegar una aplicación a partir de una imagen de un registro de contenedores. | M | 3–4 |
| RF-14 | Desplegar una aplicación a partir de una plantilla predefinida (p. ej. web estática, WordPress+MariaDB). | M | 4 |
| RF-15 | Cada despliegue queda registrado con número de revisión, configuración, fecha y resultado. | M | 4 |
| RF-16 | Volver a desplegar la versión de la aplicación (imagen y configuración) de una revisión anterior (*rollback* de aplicación). **No revierte los datos de los volúmenes**; el panel lo advierte antes de confirmar (ADR-011). | S | 4 |
| RF-17 | Si un despliegue nuevo falla al arrancar, la plataforma restaura automáticamente la versión anterior de la aplicación (con la misma limitación respecto a los datos que RF-16). | S | 4 |
| RF-18 | Iniciar, detener y reiniciar una aplicación completa. | M | 3 |
| RF-19 | Eliminar una aplicación, preguntando si se conservan o borran sus volúmenes. | M | 3, 6 |
| RF-20 | Una aplicación puede estar formada por varios servicios que se comunican entre sí por nombre. | S | 7 |

### Configuración

| ID | Requisito | Prioridad | Fase |
|---|---|---|---|
| RF-30 | Definir variables de entorno por servicio. | M | 5 |
| RF-31 | Marcar variables como secretas: no se muestran en la interfaz ni en logs una vez guardadas. | S | 5 |
| RF-32 | Publicar puertos de un servicio hacia el exterior dentro de un rango permitido. | M | 5 |
| RF-33 | Detectar conflictos de puertos antes de desplegar. | M | 5 |

### Almacenamiento

| ID | Requisito | Prioridad | Fase |
|---|---|---|---|
| RF-40 | Asociar volúmenes persistentes con nombre a una ruta del contenedor. | M | 6 |
| RF-41 | Los volúmenes sobreviven a redespliegues, reinicios y actualizaciones de imagen. | M | 6 |
| RF-42 | Listar los volúmenes de una aplicación con su tamaño ocupado. | S | 6 |
| RF-43 | Exportar una copia (archivo `.tar.gz`) de un volumen. Es una copia de seguridad manual, no un mecanismo de *rollback* de datos. | C | 6 |

### Redes y acceso

| ID | Requisito | Prioridad | Fase |
|---|---|---|---|
| RF-50 | Cada aplicación tiene su propia red privada aislada de las demás. | M | 7 |
| RF-51 | El panel muestra la URL o puerto por el que se accede a cada aplicación. | M | 7 |
| RF-52 | Acceso por nombre (`app.dominio`) mediante proxy inverso. | C | 7 |

### Monitorización

| ID | Requisito | Prioridad | Fase |
|---|---|---|---|
| RF-60 | Consultar los logs recientes de cada servicio. | M | 8 |
| RF-61 | Consultar el consumo actual de CPU y memoria de cada servicio. | M | 8 |
| RF-62 | Mostrar el estado de salud (health check) de cada servicio. | M | 8 |
| RF-63 | Mostrar métricas generales del host (CPU, memoria, disco). | S | 8 |
| RF-64 | Mostrar la evolución reciente (p. ej. última hora) del consumo con gráficas. | C | 8 |

### Recursos y ciclo de vida

| ID | Requisito | Prioridad | Fase |
|---|---|---|---|
| RF-70 | Definir límites de memoria y CPU por servicio (con valores por defecto obligatorios). | M | 9 |
| RF-71 | Definir la política de reinicio de cada servicio. | M | 9 |
| RF-72 | Impedir desplegar si se superaría la cuota total de recursos asignada a la plataforma. | S | 9 |
| RF-73 | Sincronizar el estado registrado con el estado real de Docker (p. ej. tras reiniciar el servidor). | M | 9 |

## 2.2 Requisitos no funcionales

| ID | Categoría | Requisito | Cómo se verificará |
|---|---|---|---|
| RNF-01 | Seguridad | Ningún contenedor de usuario se crea con `privileged`, capacidades añadidas, `network_mode: host`, PID/IPC del host ni montajes del sistema de archivos del host. El agente construye internamente la configuración de Docker y no acepta parámetros de Docker arbitrarios (ADR-002). | Tests unitarios del agente (peticiones con campos extra rechazadas; configuración construida sin opciones peligrosas) + test de integración con `docker inspect`. |
| RNF-02 | Seguridad | Solo el agente tiene acceso al socket de Docker. El control plane y el frontend no. | Revisión de `compose.yaml` + test que comprueba que el contenedor API no ve el socket. |
| RNF-03 | Seguridad | El agente solo opera sobre recursos con la etiqueta `minipaas.managed=true`. | Test de integración: un contenedor ajeno no puede pararse ni borrarse. |
| RNF-04 | Seguridad | Todas las entradas se validan con esquemas estrictos (nombres, imágenes, puertos, rutas). | Tests unitarios con entradas maliciosas. |
| RNF-05 | Seguridad | Contraseñas almacenadas con hash lento (Argon2 o bcrypt); cookies `HttpOnly`, `SameSite=Strict`; protección CSRF en operaciones que modifican estado. | Tests de API. |
| RNF-06 | Seguridad | Los procesos propios de MiniPaaS no se ejecutan como root dentro de sus contenedores (salvo justificación documentada). | `docker inspect` / test. |
| RNF-07 | Rendimiento | **Objetivo de diseño** (no verificado): consumo de MiniPaaS en reposo < 250 MB de RAM y < 5 % de una CPU. Seguirá siendo un objetivo, no un resultado, hasta que se mida. | Medición con `docker stats` en la Fase 12 (y mediciones orientativas desde la Fase 3). |
| RNF-08 | Rendimiento | Las páginas del panel responden en < 1 s en red local (excepto operaciones de despliegue, que son asíncronas). | Medición en la Fase 12. |
| RNF-09 | Fiabilidad | Si MiniPaaS se detiene o reinicia, las aplicaciones desplegadas siguen funcionando. | Test manual/integración. |
| RNF-10 | Fiabilidad | Un despliegue fallido no deja contenedores huérfanos ni deja la aplicación sin servicio si había una versión anterior funcional. | Test de integración con imagen que falla. |
| RNF-11 | Usabilidad | Una persona que no conoce Docker puede desplegar una plantilla en menos de 3 minutos. | Prueba con usuario en la Fase 12. |
| RNF-12 | Usabilidad | Las acciones destructivas piden confirmación; los errores se muestran en lenguaje comprensible. | Revisión de la interfaz. |
| RNF-13 | Mantenibilidad | Código con nombres descriptivos, funciones cortas, documentación de módulos y estilo homogéneo (`ruff`). | `ruff check` en CI, revisión. |
| RNF-14 | Mantenibilidad | Cobertura de tests de la lógica de validación y del agente ≥ 80 %. | `pytest --cov`. |
| RNF-15 | Portabilidad | Se instala con `docker compose up` en Ubuntu con Docker Engine, sin más dependencias en el host. | Prueba en máquina limpia/VM en la Fase 13. |
| RNF-16 | Trazabilidad | Toda operación administrativa queda en el log de auditoría con usuario, fecha, acción y resultado. | Tests de API. |
| RNF-17 | Aislamiento del entorno | Durante el desarrollo, nada se ejecuta contra el servidor real. | Procedimiento documentado. |
