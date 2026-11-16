# 8. Estructura del proyecto

> Estado del documento: **actualizado en la renovación (2026-11-16)**. Refleja los archivos que
> existen realmente en la rama `renovacion-monitorizacion`.

```text
server-monitoring-service/
├── README.md                     Presentación y puesta en marcha
├── CHANGELOG.md                  Registro de cambios
├── formato_preguntas.md          Plantilla del cuestionario de la asignatura (no se modifica)
├── pyproject.toml, uv.lock       Dependencias (sin cambios respecto a la Fase 2)
├── src/minipaas/
│   ├── common/secrets.py         Lectura y validación del token compartido
│   ├── agent/                    Proceso con acceso a Docker (solo lectura)
│   │   ├── main.py               API: /health, /metrics, /containers (token en todas)
│   │   ├── host_metrics.py       CPU, RAM, disco, SO, uptime, temperaturas
│   │   ├── containers.py         Lista de contenedores en ejecución
│   │   └── config.py             Token y MINIPAAS_HOSTFS
│   └── controlplane/             Panel (sin socket Docker)
│       ├── main.py               App FastAPI, cabeceras de seguridad, estáticos
│       ├── routes.py             Rutas /api/*
│       ├── config.py             Variables de entorno
│       ├── agent_client.py       Cliente HTTP del agente
│       ├── manage.py             CLI: set-password
│       ├── security/             passwords, sessions, rate_limit, csrf
│       └── web/                  index.html, css/, favicon.svg, js/ (api, app, dom, format, session, views/login, views/dashboard)
├── deploy/
│   ├── Dockerfile.controlplane, Dockerfile.agent
│   ├── compose.dev.yaml          Entorno local de desarrollo
│   ├── requirements/             Dependencias con hashes exportadas de uv.lock
│   └── .env.example              Ejemplo de deploy/.env
├── scripts/
│   ├── prepare_dev_env.sh        Tokens y DOCKER_GID
│   ├── verify_dev_env.sh         Comprobaciones de aislamiento (heredado, pendiente de reejecutar)
│   ├── export_requirements.sh    Exporta uv.lock con hashes
│   ├── e2e_monitor.sh            Prueba extremo a extremo (29 comprobaciones)
│   └── e2e_ui.py                 Prueba en navegador con Playwright (11 comprobaciones)
├── tests/
│   ├── agent/                    Métricas, contenedores, API del agente, integración con Docker
│   ├── panel/                    Autenticación, API del panel
│   └── unit/test_secrets.py
├── .github/workflows/ci.yml      ruff + pytest (sin integración)
└── docs/
    ├── README.md                 Índice
    ├── 01 … 08                   Visión, requisitos, arquitectura, seguridad, pruebas, roadmap, estado del arte, estructura
    ├── decisiones.md             Registro de decisiones (ADR 001–041)
    ├── registro-pruebas.md       Evidencias de las pruebas
    ├── api.md                    API del panel y del agente
    ├── guia-desarrollo.md        Entorno local
    ├── bibliografia.md
    └── informes/                 fase-00, fase-01, fase-02 y renovacion-monitorizacion
```

## Justificación

- **Un único paquete Python con dos puntos de entrada** (panel y agente) empaquetados en dos imágenes:
  cada contenedor ejecuta solo lo suyo, y el código común (el token) no se duplica.
- **El agente tiene solo tres módulos con lógica** (`host_metrics`, `containers`, `main`): cada uno se
  explica en una pantalla.
- **El panel dentro del proceso `controlplane`**: los archivos estáticos los sirve FastAPI; no hay
  servidor web ni compilación adicional.
- **Nombre `minipaas` y `controlplane`** conservados por historia; renombrarlos es una decisión del
  equipo (pendiente).
- **Sin `db/`, `repositories/`, `services/` ni `api/`**: desaparecieron con SQLite y las aplicaciones.

## Historia

La estructura de la etapa PaaS (con `db/`, `repositories/`, `services/`, `spec/`, `templates/` y un
agente con política y `docker_runtime.py`) está en el historial de Git. La rama
`fase-03-motor-despliegue` conserva la estructura de la Fase 3.
