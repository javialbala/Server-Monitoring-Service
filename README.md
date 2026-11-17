# Server Monitoring Service

**Plataforma web ligera y autohospedada para monitorizar un servidor y sus contenedores Docker, en
solo lectura.**

Trabajo de la asignatura *Gestión de Sistemas de Archivos y Servicios Distribuidos* (GSASD).

> **Estado:** rediseño de interfaz y limpieza terminados y probados en local (rama
> `rediseno-interfaz-limpieza`), **pendientes de aprobación**. Probado en CachyOS con Docker 29.9.2;
> **todavía no se ha probado en el servidor Ubuntu real**. Informe:
> [docs/informes/rediseno-interfaz-limpieza.md](docs/informes/rediseno-interfaz-limpieza.md). El
> proyecto empezó como una PaaS (MiniPaaS) y cambió de objetivo el 2026-11-16; esa etapa está archivada
> en [docs/historico/](docs/historico/etapa-paas.md).

## ¿Qué es?

Un panel web, protegido con una contraseña, que muestra:

- **El servidor anfitrión:** CPU, RAM, uno o varios discos, temperatura general (paquete del
  procesador), velocidad de red, sistema operativo, kernel, *hostname* y tiempo en marcha, con
  indicadores y gráficas de los últimos 10 minutos.
- **Todos los contenedores Docker, en ejecución y detenidos:** nombre, imagen, estado, salud, puertos,
  fecha de creación y proyecto/servicio de Compose, incluidos los creados fuera de la plataforma.

Se actualiza solo cada 5 segundos. **No puede crear, iniciar, parar, borrar ni modificar**
contenedores, imágenes ni volúmenes.

## Arquitectura en una frase

Un **panel** sin acceso a Docker (FastAPI + web estática) pide los datos a un **agente** interno, el
único con el socket de Docker, que solo hace consultas de lectura y lee `/proc`, `/sys` y el `/`, la red
y los discos extra del anfitrión montados en solo lectura. Sin base de datos. Detalles en
[docs/03-arquitectura.md](docs/03-arquitectura.md).

```text
Navegador ──▶ Panel (sin socket) ──token──▶ Agente (solo lectura) ──▶ Docker, /proc, /sys, /hostfs, /disks, /host/net/dev
```

## Tecnologías

Python 3.12 · FastAPI · httpx · argon2-cffi · SDK de Docker · Docker Compose · HTML/CSS/JavaScript y SVG
sin framework ni librerías · fuentes IBM Plex e iconos Lucide autoalojados. Justificación en
[docs/10-decisiones.md](docs/10-decisiones.md).

## Puesta en marcha (desarrollo local)

Requisitos: Linux, Docker Engine con Compose y [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras && uv run pytest -q             # tests (68)
bash scripts/prepare_dev_env.sh                      # token y GID de Docker (crea deploy/.env, 600)
echo 'APP_PASSWORD=pon-aqui-tu-contrasena' >> deploy/.env   # 4 a 128 caracteres
docker compose --env-file deploy/.env -f deploy/compose.dev.yaml up -d --build --wait
```

Panel: <http://127.0.0.1:8000>. La contraseña es la que pusiste en `APP_PASSWORD` (en `deploy/.env`,
que no se versiona). No hay contraseña por defecto: sin `APP_PASSWORD` el panel no arranca. Para
cambiarla más adelante hace falta confirmarlo con `APP_PASSWORD_RESET=true` (ver
[docs/08-guia-desarrollo.md](docs/08-guia-desarrollo.md)). Si tenías el entorno antiguo (`minipaas-dev`), bájalo antes con
`docker compose -p minipaas-dev down`. Para mostrar un disco extra, cómo ejecutar las pruebas extremo a
extremo y los problemas frecuentes, ver [docs/08-guia-desarrollo.md](docs/08-guia-desarrollo.md).

## Documentación

Índice completo en [docs/README.md](docs/README.md). Lo principal:

| Documento | Contenido |
|---|---|
| [docs/03-arquitectura.md](docs/03-arquitectura.md) | Componentes, diagramas y estructura del repositorio |
| [docs/04-backend.md](docs/04-backend.md) | Cómo funciona el agente y el panel, métrica a métrica |
| [docs/05-api.md](docs/05-api.md) | Endpoints y ejemplos JSON |
| [docs/06-seguridad.md](docs/06-seguridad.md) | Amenazas y medidas |
| [docs/09-interfaz.md](docs/09-interfaz.md) | Diseño de la interfaz y sus componentes |

## Seguridad

El panel no tiene el socket de Docker; el agente (único con el socket) está en una red interna sin
puertos, exige un token y solo hace consultas de lectura. Ningún contenedor es privilegiado ni root.
La contraseña se guarda con Argon2id; hay límite de intentos, cookie `HttpOnly`/`SameSite=Strict`, CSRF,
CSP y sesiones con caducidad. Limitaciones conocidas (el socket de Docker sigue dando acceso equivalente
a root al agente, sesiones en memoria...) en [docs/06-seguridad.md](docs/06-seguridad.md).
