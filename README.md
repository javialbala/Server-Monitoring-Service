# MiniPaaS

**Plataforma web ligera y autohospedada para monitorizar un servidor y sus contenedores Docker, en
solo lectura.**

Trabajo de la asignatura *Gestión de Sistemas de Archivos y Servicios Distribuidos* (GSASD).

> **Estado actual: renovación a plataforma de monitorización terminada, pendiente de aprobación**
> (rama `renovacion-monitorizacion`). El proyecto empezó como una PaaS para desplegar aplicaciones
> (Fases 0 a 3); el 2026-11-16 se cambió el objetivo a monitorización de solo lectura por ser más
> sencillo, seguro y defendible (ADR-036). Las Fases 0 a 2 se conservan como etapa anterior; la
> Fase 3 está en la rama `fase-03-motor-despliegue`, que no se aprobó y se conserva intacta. Informe:
> [docs/informes/renovacion-monitorizacion.md](docs/informes/renovacion-monitorizacion.md). El nombre
> «MiniPaaS» y el paquete `minipaas` se mantienen por historia.

## ¿Qué es?

Un panel web, protegido con una contraseña, que muestra:

- **El servidor anfitrión:** CPU, RAM, disco, sistema operativo, kernel, *hostname*, tiempo en marcha
  y temperaturas.
- **Los contenedores Docker en ejecución:** nombre, imagen, estado, puertos, fecha de creación y
  proyecto/servicio de Compose, incluidos los creados fuera de la plataforma.

Se actualiza solo cada 5 segundos. **No puede crear, iniciar, parar, borrar ni modificar**
contenedores, imágenes ni volúmenes.

## Arquitectura en una frase

Un **panel** sin acceso a Docker (FastAPI + web estática) pide los datos a un **agente** interno, el
único con el socket de Docker, que solo hace consultas de lectura y lee `/proc`, `/sys` y el `/` del
anfitrión montado en solo lectura. Sin base de datos. Detalles en
[docs/03-arquitectura.md](docs/03-arquitectura.md).

```text
Navegador ──▶ Panel (sin socket) ──token──▶ Agente (solo lectura) ──▶ Docker, /proc, /sys, /hostfs
```

## Tecnologías

Python 3.12 · FastAPI · httpx · argon2-cffi · SDK de Docker · Docker Compose · HTML/CSS/JavaScript
sin framework. Justificación en [docs/decisiones.md](docs/decisiones.md).

## Documentación

Índice completo en [docs/README.md](docs/README.md).

## Puesta en marcha (desarrollo local)

Requisitos: Linux, Docker Engine con Compose y [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras && uv run pytest -q             # tests (48)
bash scripts/prepare_dev_env.sh                      # token y GID de Docker (una vez)
docker compose --env-file deploy/.env -f deploy/compose.dev.yaml up -d --build --wait
docker compose --env-file deploy/.env -f deploy/compose.dev.yaml \
    exec controlplane python -m minipaas.controlplane.manage set-password
```

Panel: <http://127.0.0.1:8000>. No hay contraseña por defecto: se establece con la última orden
(4 a 128 caracteres). La API está descrita en [docs/api.md](docs/api.md); la guía completa y las
pruebas extremo a extremo, en [docs/guia-desarrollo.md](docs/guia-desarrollo.md). Todavía **no se ha
probado en el servidor Ubuntu real**; su instalación requiere autorización expresa.

## Seguridad

El panel no tiene el socket de Docker; el agente (único con el socket) está en una red interna sin
puertos, exige un token y solo hace consultas de lectura. Ningún contenedor es privilegiado ni root.
La contraseña se guarda con Argon2id; hay límite de intentos, cookie `HttpOnly`/`SameSite=Strict`,
CSRF, CSP y sesiones con caducidad. Limitaciones conocidas (el socket de Docker sigue dando acceso
equivalente a root al agente, sesiones en memoria...) en [docs/04-seguridad.md](docs/04-seguridad.md).
