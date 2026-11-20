# 11. Estado del arte: herramientas de monitorización comparables

> Estado del documento: **actualizado en la fase de rediseño de interfaz y limpieza (2026-11-16)**.
> Solo recoge las herramientas con las que se compara el proyecto actual. El contexto teórico de la
> etapa PaaS (NIST, contenedores, OpenShift, Cloud Foundry, Dokku, CapRover...) está en
> [historico/estado-del-arte-etapa-paas.md](historico/estado-del-arte-etapa-paas.md). Las descripciones
> son generales y **no se aportan cifras de consumo ni rendimiento**, porque no se han medido. Las
> afirmaciones deben contrastarse con la documentación oficial de cada herramienta antes de citarlas
> en la memoria (ver [bibliografia.md](bibliografia.md)).

## 11.1 Herramientas

| Herramienta | Idea | Diferencia con este proyecto |
|---|---|---|
| **Netdata** | Agente de monitorización en tiempo real con muchísimas métricas, gráficas e historial | Mucho más completo y complejo; este proyecto muestra pocas métricas y solo el último valor, sin histórico |
| **Glances** | Monitor del sistema escrito en Python, con interfaz de terminal y modo web | Similar en espíritu; no está pensado para separar el proceso expuesto del acceso a Docker ni para tener inicio de sesión propio |
| **cAdvisor** | Recoge el uso de recursos de los contenedores (de Google) | Se centra en métricas por contenedor; aquí solo se listan los contenedores (con su estado) y se muestra el estado del anfitrión |
| **Prometheus + node_exporter** | `node_exporter` expone métricas del anfitrión que Prometheus recoge y almacena | Estándar profesional con historial y alertas, pero requiere varios componentes; el montaje `/hostfs` de este proyecto se inspira en el de `node_exporter`, más restringido (sin submontajes) |
| **Portainer** | Interfaz web de gestión de Docker | Permite **crear y modificar** contenedores; este proyecto lo prohíbe expresamente |

## 11.2 Qué aporta este proyecto

Una herramienta pequeña que el equipo puede leer y explicar entera, con un diseño de seguridad explícito
(panel sin socket, agente de solo lectura, montajes de solo lectura, sin dependencias nuevas) y que
muestra en una sola pantalla el anfitrión (CPU, RAM, discos, temperatura, red) y todos los contenedores,
también los creados fuera de ella y los detenidos. No pretende competir en funcionalidad con las
herramientas anteriores, que son más completas: renuncia a las alertas, al historial persistente y a
cualquier acción de escritura.

## 11.3 Plataformas PaaS autoalojadas

Este proyecto no compite con las PaaS autoalojadas (Dokku, Coolify, CapRover, Dokploy), que **despliegan
y gestionan aplicaciones**; él solo **observa** el servidor y sus contenedores. Pueden complementarse:
si la PaaS acepta un `docker-compose.yml` y da acceso al socket Docker del anfitrión, se puede
desplegar este servicio sobre ella. Qué es una PaaS y cómo encaja el proyecto: ver el
[README](../README.md), apartado «Qué es una PaaS».
