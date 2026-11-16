# 2. Requisitos

> Estado del documento: **reescrito en la renovación (2026-11-16)**. Los requisitos nuevos usan los
> identificadores `RF-M..` y `RNF-M..` (M de monitorización) para no confundirse con los de la etapa
> PaaS, que se conservan en el apartado 2.4 como historia.
>
> Prioridad (MoSCoW): **M** = imprescindible, **S** = debería, **C** = podría.
> Estado: **Verificado** = hay prueba ejecutada con resultado real (ver `registro-pruebas.md`);
> **Pendiente** = no verificado todavía.

## 2.1 Requisitos funcionales

### Acceso

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M01 | El panel y los datos exigen iniciar sesión con una contraseña única (4–128 caracteres). | M | Verificado |
| RF-M02 | La contraseña se establece desde la línea de órdenes (`manage set-password`), nunca con valor por defecto ni como argumento. | M | Verificado |
| RF-M03 | El usuario puede cerrar sesión; la sesión caduca a los 30 min de inactividad y a las 8 h como máximo. | M | Verificado (caducidad con reloj simulado) |
| RF-M04 | Los accesos (correctos, fallidos, bloqueos, cierres) se registran sin contraseñas. | S | Implementado; sin prueba automática del contenido del log |

### Métricas del servidor anfitrión

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M10 | Mostrar el uso de CPU en porcentaje, el número de núcleos y el modelo. | M | Verificado |
| RF-M11 | Mostrar la memoria RAM: total, usada, disponible y porcentaje. | M | Verificado |
| RF-M12 | Mostrar el disco raíz del anfitrión: total, usado, libre y porcentaje (como `df`). | M | Verificado |
| RF-M13 | Mostrar sistema operativo, kernel, arquitectura, *hostname* y tiempo en marcha. | M | Verificado |
| RF-M14 | Mostrar las temperaturas disponibles (lista vacía si no hay sensores). | S | Verificado |
| RF-M15 | Los valores mostrados corresponden al **anfitrión**, no al contenedor del agente. | M | Verificado |

### Contenedores

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M20 | Listar los contenedores **en ejecución** con nombre, imagen, estado, puertos y fecha de creación. | M | Verificado |
| RF-M21 | Incluir los contenedores creados fuera de la plataforma. | M | Verificado |
| RF-M22 | Mostrar el proyecto y el servicio de Compose (etiquetas `com.docker.compose.*`) cuando existan. | S | Verificado |
| RF-M23 | Un contenedor que se para deja de aparecer. | M | Verificado |

### Actualización e interfaz

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M30 | Los datos se actualizan solos cada 5 s. | M | Verificado (navegador) |
| RF-M31 | La actualización se pausa con la pestaña oculta, se reanuda al volver y se detiene al cerrar sesión o con un 401. | S | Verificado (navegador) |
| RF-M32 | Si el agente o Docker fallan, el panel lo indica con un mensaje comprensible. | S | Parcial: 502/503 verificados en tests de API; el aviso «No se pudo actualizar» de la interfaz no se ha probado en navegador |

### Solo lectura

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M40 | La plataforma no crea, inicia, para, borra ni modifica contenedores, imágenes ni volúmenes. | M | Verificado (tests del agente y `docker events` en el E2E) |

## 2.2 Requisitos no funcionales

| ID | Categoría | Requisito | Cómo se verifica | Estado |
|---|---|---|---|---|
| RNF-M01 | Seguridad | El panel (expuesto al navegador) no tiene el socket de Docker. | E2E: el panel no ve el socket | Verificado |
| RNF-M02 | Seguridad | El agente solo tiene rutas `GET`, exige token Bearer en todas y solo consulta a Docker `containers(status=running)` y `version`. | Tests del agente | Verificado |
| RNF-M03 | Seguridad | Ningún contenedor propio es privilegiado, usa root, ni capabilities; sistema de archivos de solo lectura; `no-new-privileges`. | `compose.dev.yaml`; `verify_dev_env.sh` (de la etapa anterior) | Parcial: configuración revisada; `verify_dev_env.sh` pendiente de reejecutar |
| RNF-M04 | Seguridad | El montaje del anfitrión es de solo lectura y sin submontajes. | E2E | Verificado |
| RNF-M05 | Seguridad | Contraseña con Argon2id; cookie `HttpOnly`, `SameSite=Strict`, `Secure` configurable; límite de 5 fallos en 15 min por IP. | Tests del panel y E2E | Verificado |
| RNF-M06 | Seguridad | CSRF por sesión en el cierre de sesión y comprobación de `Origin` en métodos no seguros. | Tests del panel y E2E | Verificado |
| RNF-M07 | Seguridad | CSP `default-src 'self'`, sin `innerHTML` con datos del servidor, sin `/docs`. | Test de cabeceras; revisión del JS | Verificado |
| RNF-M08 | Mantenibilidad | Código sencillo y pequeño, comentarios en español, sin dependencias nuevas. | `ruff`; revisión | Verificado |
| RNF-M09 | Mantenibilidad | Pruebas automáticas suficientes y rápidas. | `uv run pytest` (48 tests) | Verificado |
| RNF-M10 | Rendimiento | Una consulta de métricas tarda del orden de 0,5 s (medición de CPU). | Diseño (ADR-040); sin medición formal | Pendiente de medir |
| RNF-M11 | Rendimiento | **Objetivo de diseño:** consumo bajo de RAM y CPU. Sin cifra verificada. | Medir con `docker stats` | Pendiente |
| RNF-M12 | Portabilidad | Funciona con `docker compose up` en Linux con Docker Engine 25 o superior (API 1.44). | Probado en CachyOS; **no** en Ubuntu | Parcial |
| RNF-M13 | Aislamiento del entorno | El desarrollo y las pruebas no tocan el servidor real. | Procedimiento | Cumplido |
| RNF-M14 | Usabilidad | Interfaz clara, adaptable a pantallas estrechas, con mensajes de error en español. | Recorrido en navegador | Parcial (mejora planificada) |

## 2.3 Requisitos retirados de la etapa PaaS

Los requisitos RF-10 a RF-73 (aplicaciones, despliegues, configuración, almacenamiento, redes,
recursos) y RNF-01, 03, 04, 08 a 12 y 16 dejan de aplicar. RF-60 a RF-63 (monitorización) quedan
cubiertos, de forma reducida, por RF-M10 a RF-M31.

## 2.4 Historia: requisitos de la etapa PaaS (Fases 0 a 3)

Se conservan como referencia de lo que se planteó en la Fase 0. No son vigentes.

| Grupo | Requisitos | Situación actual |
|---|---|---|
| Autenticación | RF-01 a RF-03 | RF-01 y RF-02 pasan a RF-M01 y RF-M03 (sin usuario); RF-03 (auditoría en BD) sustituido por RF-M04 (log) |
| Aplicaciones y despliegues | RF-10 a RF-20 | Retirados (ADR-036) |
| Configuración | RF-30 a RF-33 | Retirados |
| Almacenamiento | RF-40 a RF-43 | Retirados |
| Redes y acceso | RF-50 a RF-52 | Retirados |
| Monitorización | RF-60 a RF-64 | Cubiertos en parte: métricas del host (RF-63) y estado de contenedores; sin logs ni gráficas |
| Recursos | RF-70 a RF-73 | Retirados |
| Seguridad y calidad | RNF-02, 05, 06, 07, 13, 14, 15, 17 | Se mantienen adaptados como RNF-M01, M05, M03, M11, M08, M09, M12, M13 |

El texto completo de cada requisito está en el historial de Git (documento aprobado el 2026-11-15,
commit anterior a la renovación).
