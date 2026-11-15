# MiniPaaS

**Plataforma PaaS ligera y autohospedada para desplegar y gestionar aplicaciones en contenedores
desde un panel web.**

Trabajo de la asignatura *Gestión de Sistemas de Archivos y Servicios Distribuidos* (GSASD).
Título provisional: *«Diseño e implementación de una plataforma PaaS ligera para el despliegue y
gestión de aplicaciones distribuidas»*.

> **Estado actual: Fase 1 (estructura y entorno aislado) terminada, pendiente de aprobación.**
> Existen el control plane y el agente en versión mínima: se comunican de forma autenticada y el
> panel muestra el estado del sistema. **Todavía no se pueden desplegar aplicaciones**; las
> capacidades descritas abajo son objetivos de las fases siguientes.

## ¿Qué es?

MiniPaaS permite a una persona desplegar, configurar, monitorizar y administrar aplicaciones en un
servidor doméstico sin tener que usar Docker desde la terminal. El usuario trabaja con
**aplicaciones y despliegues**; la plataforma se encarga de los contenedores, redes, volúmenes y
límites de recursos.

Capacidades objetivo: desplegar desde una imagen o una plantilla, variables de entorno y secretos,
puertos, almacenamiento persistente, redes privadas por aplicación, logs, health checks, métricas,
límites de recursos, historial de despliegues y vuelta atrás a una versión anterior de la aplicación
(la vuelta atrás no revierte los datos persistentes).

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

## Puesta en marcha (desarrollo local)

Requisitos: Linux, Docker Engine con Compose y [uv](https://docs.astral.sh/uv/).

```bash
uv sync && uv run pytest -m "not integration"        # tests
bash scripts/prepare_dev_env.sh                      # token y GID de Docker (una vez)
docker compose --env-file deploy/.env -f deploy/compose.dev.yaml up -d --build --wait
```

Panel: <http://127.0.0.1:8000>. Detalles y verificación del aislamiento en
[docs/guia-desarrollo.md](docs/guia-desarrollo.md). La instalación en el servidor se documentará en
la Fase 13.

## Seguridad

La plataforma no usa contenedores privilegiados, no da acceso al socket de Docker al componente
expuesto a la red, no permite ejecutar comandos arbitrarios y solo actúa sobre recursos etiquetados
como propios. Ver [docs/04-seguridad.md](docs/04-seguridad.md).
