# 2. Requisitos

> Estado del documento: **actualizado en la fase de rediseño de interfaz y limpieza (2026-11-16)**.
> Solo requisitos vigentes. Los identificadores `RF-M..` y `RNF-M..` (M de monitorización) no se
> confunden con los de la etapa PaaS, archivados en
> [historico/etapa-paas.md](historico/etapa-paas.md).
>
> Prioridad (MoSCoW): **M** = imprescindible, **S** = debería, **C** = podría.
> Estado: **Verificado** = hay una prueba ejecutada con resultado real (ver [07-pruebas.md](07-pruebas.md));
> **Parcial** = una parte verificada y otra no; **Pendiente** = no verificado todavía.
> Todas las verificaciones se hicieron en local (CachyOS); ninguna en el servidor Ubuntu real.

## 2.1 Requisitos funcionales

### Acceso

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M01 | El panel y los datos exigen iniciar sesión con una contraseña única (4–128 caracteres). | M | Verificado |
| RF-M02 | La contraseña se escribe en `APP_PASSWORD` del servicio `panel` de `docker-compose.yml` (4–128 caracteres), sin valor por defecto: si falta, está vacía o no es válida, el panel no arranca (código 1) y el log lo explica. Solo se calcula su hash en memoria; nada se guarda en disco y nunca se registra. | M | Verificado (tests y E2E con Docker real) |
| RF-M05 | Cambiar la contraseña consiste en editar `APP_PASSWORD` y ejecutar `docker compose up -d`; la antigua deja de valer y las sesiones abiertas se cierran. | M | Verificado (tests y E2E con Docker real) |
| RF-M03 | El usuario puede cerrar sesión; la sesión caduca a los 30 min de inactividad y a las 8 h como máximo. | M | Verificado (caducidad con reloj simulado) |
| RF-M04 | Los accesos (correctos, fallidos, bloqueos, cierres) se registran sin contraseñas. | S | Implementado; sin prueba automática del contenido del registro |

### Métricas del servidor anfitrión

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M10 | Mostrar el uso de CPU en porcentaje, el número de núcleos y el modelo. | M | Verificado |
| RF-M11 | Mostrar la memoria RAM: total, usada, disponible y porcentaje. | M | Verificado |
| RF-M12 | Mostrar el disco raíz del anfitrión y los discos extra que el administrador declare en `/disks/<nombre>` (solo lectura): total, usado, libre y porcentaje (como `df`), con un indicador por disco. Los discos del mismo sistema de archivos que el raíz no se repiten. | M | Verificado el raíz (E2E contra `df`) y el indicador por disco (navegador). Discos extra: solo con directorios falsos; **sin disco extra real montado** |
| RF-M13 | Mostrar sistema operativo, kernel, arquitectura, *hostname* y tiempo en marcha. | M | Verificado |
| RF-M14 | Mostrar **una sola** temperatura general: la del paquete del procesador (Intel `coretemp`, AMD `k10temp` o `x86_pkg_temp`); «No disponible» si no hay sensor fiable. | S | Verificado con `coretemp` en el equipo local (E2E ±5 °C). `k10temp` y `x86_pkg_temp`: solo con directorios falsos |
| RF-M15 | Los valores mostrados corresponden al **anfitrión**, no al contenedor del agente. | M | Verificado |
| RF-M16 | Mostrar la velocidad de red (bajada y subida) del anfitrión, calculada en el navegador a partir de contadores acumulados, excluyendo `lo`, `veth*`, `br-*`, `docker*` y `virbr*`. | S | Verificado: interfaces reales del anfitrión y suma coherente (E2E); gráfica dibujada con muestras reales (navegador). El valor numérico de la velocidad **no se ha contrastado** con una herramienta externa |

### Contenedores

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M20 | Listar **todos** los contenedores (en ejecución y detenidos) con nombre, imagen, estado, puertos y fecha de creación, con una sola llamada de lectura a Docker. | M | Verificado (E2E: mismo número que `docker ps -a`) |
| RF-M21 | Incluir los contenedores creados fuera de la plataforma. | M | Verificado |
| RF-M22 | Mostrar el proyecto y el servicio de Compose (etiquetas `com.docker.compose.*`) cuando existan. | S | Verificado |
| RF-M23 | Un contenedor que se detiene sigue apareciendo, marcado como detenido; los que están en ejecución van primero. | M | Verificado (E2E y navegador) |
| RF-M24 | Deducir la salud (`healthy`, `unhealthy`, `starting`) del texto de estado y mostrar «Con fallos» y «Arrancando» de forma diferenciada. | S | Verificado en tests de la conversión; **la presentación de «Con fallos» y «Arrancando» no se ha probado en navegador** |
| RF-M25 | Agrupar los puertos publicados en IPv4 e IPv6 como uno solo. | C | Implementado; verificado solo por revisión (sin prueba automática de `formatPorts`) |

### Actualización e interfaz

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M30 | Los datos se actualizan solos cada 5 s. | M | Verificado (navegador) |
| RF-M31 | La actualización se pausa con la pestaña oculta, se reanuda al volver y se detiene al cerrar sesión o con un 401. | S | Verificado (navegador; la pestaña oculta se simula con `visibilitychange`) |
| RF-M32 | Si el agente o Docker fallan, el panel lo indica con un estado de conexión y un mensaje comprensible, conservando los últimos datos. | S | Parcial: 502/503 verificados en tests de API; el aviso de la interfaz no se ha probado en navegador |
| RF-M33 | Mostrar la versión de Docker, el total de contenedores (en ejecución y detenidos) y el número de imágenes, junto a las tablas de contenedores e imágenes. | S | Verificado (navegador y API) |

### Solo lectura

| ID | Requisito | Prioridad | Estado |
|---|---|---|---|
| RF-M40 | La plataforma no crea, inicia, para, borra ni modifica contenedores, imágenes ni volúmenes, ni ofrece controles para ello. | M | Verificado (tests del agente, `docker events` en el E2E y ausencia de botones en el navegador) |

## 2.2 Requisitos no funcionales

| ID | Categoría | Requisito | Cómo se verifica | Estado |
|---|---|---|---|---|
| RNF-M01 | Seguridad | El panel (expuesto al navegador) no tiene el socket de Docker. | E2E: el panel no ve el socket | Verificado |
| RNF-M02 | Seguridad | El agente solo tiene rutas `GET`, no tiene puertos publicados ni salida a Internet (solo lo alcanza el panel, por la red interna) y solo consulta a Docker `containers(all=True)` y `version`. | Tests del agente y E2E (agente inaccesible desde el anfitrión y sin Internet) | Verificado |
| RNF-M03 | Seguridad | Ningún contenedor propio es privilegiado, usa root, ni capabilities; sistema de archivos de solo lectura; `no-new-privileges`. | `docker-compose.yml`; E2E (`e2e_monitor.sh`) | Verificado |
| RNF-M04 | Seguridad | Los montajes del anfitrión (`/hostfs`, `/host/net/dev`, `/disks/*`) son de solo lectura; `/hostfs` sin submontajes. | E2E | Verificado `/hostfs`; `/host/net/dev` se comprobó en un contenedor efímero (se leen las interfaces reales) y en el E2E; `/disks/*` sin probar con un disco real |
| RNF-M05 | Seguridad | Contraseña con Argon2id; cookie `HttpOnly`, `SameSite=Strict`, `Secure` configurable; límite de 5 fallos en 15 min por IP. | Tests del panel y E2E | Verificado |
| RNF-M06 | Seguridad | CSRF por sesión en el cierre de sesión y comprobación de `Origin` en métodos no seguros. | Tests del panel y E2E | Verificado |
| RNF-M07 | Seguridad | CSP `default-src 'self'` sin recursos externos (fuentes e iconos autoalojados), sin `innerHTML` con datos del servidor, sin `/docs`. | Test de cabeceras; navegador sin errores de CSP; revisión del JS | Verificado |
| RNF-M08 | Mantenibilidad | Código sencillo y pequeño (788 líneas de Python), comentarios en español, sin librerías de JavaScript y sin dependencias nuevas de Python. | `ruff`; `node --check`; revisión | Verificado |
| RNF-M09 | Mantenibilidad | Pruebas automáticas suficientes y rápidas. | `uv run pytest` (51 tests) | Verificado |
| RNF-M10 | Rendimiento | Una consulta de métricas tarda del orden de 0,5 s (medición de CPU). | Diseño (ADR-040); sin medición formal | Pendiente de medir |
| RNF-M11 | Rendimiento | **Objetivo de diseño:** consumo bajo de RAM y CPU. Sin cifra verificada. | Medir con `docker stats` | Pendiente |
| RNF-M12 | Portabilidad | Funciona con `docker compose up -d --build` en Linux con Docker Engine 25 o superior (API 1.44). | Probado en CachyOS; **no** en Ubuntu | Parcial |
| RNF-M13 | Aislamiento del entorno | El desarrollo y las pruebas no tocan el servidor real. | Procedimiento | Cumplido |
| RNF-M14 | Usabilidad | Interfaz clara, adaptable a pantallas estrechas (sin scroll horizontal a 1024 y 390 px), con mensajes de error en español. | Navegador (`e2e_ui.py`) | Verificado en 1024 y 390 px |
| RNF-M15 | Accesibilidad | Estado nunca solo por color, foco visible, `prefers-reduced-motion`; los valores numéricos y los estados se muestran también como texto. | Revisión del CSS y JS | Parcial: implementado y revisado; no hay auditoría automática |

## 2.3 Requisitos retirados de la etapa PaaS

Los requisitos de la etapa PaaS (RF-01 a RF-73 y RNF-01 a RNF-17) ya no son vigentes: ver
[historico/etapa-paas.md](historico/etapa-paas.md).
