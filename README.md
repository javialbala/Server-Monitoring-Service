# MiniPaaS

**Plataforma PaaS ligera y autohospedada para desplegar y gestionar aplicaciones en contenedores
desde un panel web.**

Trabajo de la asignatura *Gestión de Sistemas de Archivos y Servicios Distribuidos* (GSASD).
Título provisional: *«Diseño e implementación de una plataforma PaaS ligera para el despliegue y
gestión de aplicaciones distribuidas»*.

> **Estado actual: Fase 0 — análisis y arquitectura.** Todavía no hay código: el repositorio contiene
> la documentación de requisitos, arquitectura y planificación. Nada de lo que se describe a
> continuación está implementado aún.

## ¿Qué es?

MiniPaaS permite a una persona desplegar, configurar, monitorizar y administrar aplicaciones en un
servidor doméstico sin tener que usar Docker desde la terminal. El usuario trabaja con
**aplicaciones y despliegues**; la plataforma se encarga de los contenedores, redes, volúmenes y
límites de recursos.

Capacidades objetivo: desplegar desde una imagen o una plantilla, variables de entorno y secretos,
puertos, almacenamiento persistente, redes privadas por aplicación, logs, health checks, métricas,
límites de recursos, historial de despliegues y vuelta atrás.

## Arquitectura en una frase

Un **control plane** sin privilegios (FastAPI + SQLite + panel web) decide *qué* hay que hacer, y un
**agente** aislado, el único con acceso a Docker, ejecuta solo una lista cerrada de operaciones
seguras sobre recursos que pertenecen a MiniPaaS. Detalles en
[docs/03-arquitectura.md](docs/03-arquitectura.md).

## Tecnologías previstas

Python · FastAPI · Pydantic · SQLite · Docker Engine (SDK de Python) · Docker Compose ·
HTML/CSS/JavaScript · Chart.js. Justificación en [docs/decisiones.md](docs/decisiones.md).

## Documentación

Índice completo en [docs/README.md](docs/README.md).

## Requisitos e instalación

Se documentarán en la Fase 1 (entorno de desarrollo local) y en la Fase 13 (instalación en el
servidor). Requisito previsto: Linux con Docker Engine y Docker Compose.

## Seguridad

La plataforma no usa contenedores privilegiados, no da acceso al socket de Docker al componente
expuesto a la red, no permite ejecutar comandos arbitrarios y solo actúa sobre recursos etiquetados
como propios. Ver [docs/04-seguridad.md](docs/04-seguridad.md).
