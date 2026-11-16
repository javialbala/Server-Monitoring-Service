# 1. Visión y alcance

> Estado del documento: **reescrito en la renovación (2026-11-16)**, con el cambio de objetivo
> aprobado por el usuario (ADR-036). El objetivo original (PaaS) se conserva en el apartado 1.7 como
> historia del proyecto.

## 1.1 Problema

Un servidor doméstico con Docker ejecuta servicios que se crean de formas distintas (`docker run`,
Compose, otras herramientas). Para saber si el servidor está sano hay que entrar por terminal y usar
varios comandos (`top`, `free`, `df`, `docker ps`...). No hay una vista única y sencilla con el
estado del servidor y de todos sus contenedores.

## 1.2 Objetivo

Construir una **plataforma web ligera de monitorización y consulta** (el proyecto sigue llamándose
MiniPaaS por razones históricas) que muestre, tras iniciar sesión:

1. **Métricas del servidor anfitrión:** CPU, RAM, disco, sistema operativo, kernel, *hostname*,
   tiempo en marcha (*uptime*) y temperaturas.
2. **Contenedores Docker en ejecución:** nombre, imagen, estado, puertos, fecha de creación y
   proyecto/servicio de Docker Compose, **incluidos los creados fuera de la plataforma**.

La plataforma es **solo de lectura**: no crea, inicia, para, borra ni modifica contenedores, imágenes
ni volúmenes. Debe ser **funcional, sencilla y segura**, y su código debe poder ser comprendido,
explicado y demostrado por el equipo.

## 1.3 Motivo del cambio de objetivo

El objetivo original era una PaaS completa (catálogo, despliegues, revisiones, *rollback*,
volúmenes, redes, límites). Era demasiado amplio y complejo para un proyecto universitario que el
equipo debe entender y defender: la Fase 3 sola ya tenía unas 7 700 líneas de código y faltaban
diez fases. El 2026-11-16 el usuario aprobó reducirlo a monitorización de solo lectura (ADR-036),
priorizando lo funcional, lo sencillo y lo seguro.

## 1.4 Alcance

### Dentro del alcance

| Área | Incluido |
|---|---|
| Acceso | Inicio de sesión con una contraseña única, cierre de sesión, caducidad de sesión |
| Métricas del anfitrión | CPU (%, núcleos, modelo), RAM, disco raíz, SO, kernel, arquitectura, *hostname*, uptime, temperaturas |
| Contenedores | Lista de los **en ejecución**: nombre, imagen, estado, puertos, creación, proyecto y servicio de Compose |
| Actualización | Consulta automática cada 5 s, con pausa si la pestaña no está visible |
| Seguridad | Agente de solo lectura aislado, token, Argon2id, límite de intentos, CSRF, CSP |

### Fuera del alcance (decisión consciente)

| Excluido | Motivo |
|---|---|
| Crear, iniciar, parar, reiniciar o borrar contenedores, imágenes y volúmenes | Es el núcleo del cambio de objetivo: solo lectura. |
| Desplegar aplicaciones, plantillas, revisiones, *rollback* | Eran el objetivo PaaS (Fases 3 a 9 originales). |
| Contenedores parados o historial de métricas | No pedido; el panel muestra el estado actual. |
| Red del anfitrión (tráfico, interfaces) | Requeriría `network_mode: host` para el agente, que se evita (ver problemas pendientes). |
| Logs de contenedores, alertas, notificaciones | No pedido. |
| Varios usuarios y roles | Una única contraseña. |
| Multi-nodo, Kubernetes | Un solo servidor. |
| HTTPS propio | Se podrá poner delante un proxy; `MINIPAAS_COOKIE_SECURE=true` ya está disponible. |

### Criterio de éxito

Una plataforma que funcione, sea estable y segura dentro de su alcance, ejecutable en el servidor
doméstico, con interfaz sencilla, arquitectura coherente, código legible y documentación suficiente
para defenderla académicamente.

## 1.5 Restricciones

- **No poner en riesgo el servidor real.** Todo el desarrollo y las pruebas se hacen en local. A
  fecha de esta renovación **no** se ha probado en el servidor Ubuntu real.
- **Solo lectura**, también en el código: el agente únicamente consulta (ADR-037).
- **Recursos limitados.** Objetivo de diseño de bajo consumo (RNF-07), todavía sin medir.
- **Tecnologías comprensibles.** Cada pieza debe poder explicarse en la defensa; sin dependencias
  nuevas respecto a la Fase 2.
- **Proyecto académico de duración limitada.** Se prioriza un núcleo pequeño y sólido.

## 1.6 Usuarios

| Rol | Descripción |
|---|---|
| Administrador | Persona que consulta el estado del servidor. Es el **único usuario**: comparte una contraseña única. |

## 1.7 Historia: el objetivo original (Fases 0 a 3)

Hasta la Fase 2 el proyecto se planteaba como una **PaaS ligera** autohospedada para desplegar y
administrar aplicaciones en contenedores (título provisional: *«Diseño e implementación de una
plataforma PaaS ligera para el despliegue y gestión de aplicaciones distribuidas»*). Las Fases 0 a 2
(análisis, estructura y entorno, control plane con SQLite y autenticación) fueron aprobadas y **se conservan**: la renovación reutiliza su estructura de dos procesos,
la autenticación, el CSRF, las cabeceras, el entorno Docker y la integración continua. La Fase 3
(motor de despliegue) se desarrolló en la rama `fase-03-motor-despliegue`, que se conserva intacta
pero no se aprobó. Los informes `docs/informes/fase-00.md` a `fase-02.md` describen esa etapa.
El informe de la renovación es `docs/informes/renovacion-monitorizacion.md`.
