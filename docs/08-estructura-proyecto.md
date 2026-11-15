# 8. Estructura del proyecto

> Estado del documento: **aprobado (2026-11-15)**. Tras la Fase 1 existen: `pyproject.toml`,
> `uv.lock`, `src/minipaas/{common,controlplane,agent}` (versión mínima), `tests/{unit,api,integration}`,
> `deploy/` (Dockerfiles, `compose.dev.yaml`, `.env.example`), `scripts/` (preparación y
> verificación del entorno) y `.github/workflows/ci.yml`. Los elementos marcados con una fase
> posterior todavía no existen.

```text
minipaas/                         (raíz del repositorio)
├── README.md                     Presentación, objetivos, puesta en marcha
├── CHANGELOG.md                  Registro de cambios por fase
├── LICENSE                       (pendiente de decisión)
├── pyproject.toml                Dependencias, configuración de ruff y pytest   [Fase 1]
├── src/
│   └── minipaas/
│       ├── common/               Código compartido por control plane y agente   [Fase 1–3]
│       │   ├── service_request.py Esquema ServiceRequest (contrato control plane ↔ agente) [Fase 3]
│       │   ├── naming.py         Prefijo y etiquetas (minipaas-*, minipaas.managed)   [Fase 1 ✔]
│       │   └── secrets.py        Lectura y validación del token compartido            [Fase 1 ✔]
│       ├── controlplane/         Proceso sin privilegios                        [Fase 1–2 ✔]
│       │   ├── main.py           Ensamblado de la app FastAPI y arranque         [✔]
│       │   ├── config.py         Configuración desde variables de entorno        [✔]
│       │   ├── clock.py          Reloj inyectable (UTC)                          [Fase 2 ✔]
│       │   ├── schemas.py        Esquemas Pydantic de entrada y salida           [Fase 2 ✔]
│       │   ├── manage.py         CLI: migrate, db-version, create-admin          [Fase 2 ✔]
│       │   ├── api/              Rutas: health, auth, applications, deps         [Fase 2 ✔] (+ despliegues, monitorización: fases 3–8)
│       │   ├── services/         Casos de uso: auth, applications, audit         [Fase 2 ✔] (+ deployments, monitoring)
│       │   ├── repositories/     SQL explícito: users, sessions, applications, audit [Fase 2 ✔]
│       │   ├── db/               Conexión, transacciones, migraciones (*.sql)    [Fase 2 ✔]
│       │   ├── security/         Contraseñas, sesiones, CSRF, límite de intentos [Fase 2 ✔]
│       │   ├── spec/             Validación y traducción: storage, networking, resources [Fases 3–9]
│       │   ├── agent_client.py   Cliente HTTP del agente                         [Fase 1 ✔]
│       │   └── web/              Panel: index.html, favicon.svg, css/, js/ (+ js/views/) [Fases 1–2 ✔]
│       └── agent/                Proceso con acceso a Docker                    [Fase 3]
│           ├── main.py           API mínima del agente
│           ├── policy.py         Política de seguridad (lista blanca, revalidación)
│           ├── docker_runtime.py Llamadas al SDK de Docker
│           └── host_metrics.py   Métricas del host
├── templates/                    Plantillas de aplicaciones (YAML propio)        [Fase 4]
├── deploy/
│   ├── Dockerfile.controlplane                                                   [Fase 1]
│   ├── Dockerfile.agent
│   ├── compose.dev.yaml          Entorno local de desarrollo                     [Fase 1 ✔]
│   ├── .env.example              Ejemplo de deploy/.env (DOCKER_GID)             [Fase 1 ✔]
│   ├── requirements/             Dependencias con hashes exportadas de uv.lock   [Fase 1 ✔]
│   └── compose.yaml              Despliegue en el servidor                       [Fase 13]
├── tests/
│   ├── unit/                     Sin Docker
│   ├── api/                      Control plane con agente falso
│   └── integration/              Docker local real (marcador `integration`)
├── scripts/                      prepare_dev_env, verify_dev_env, export_requirements, e2e_phase2 [✔]
├── .github/workflows/ci.yml      ruff + pytest                                   [Fase 1]
└── docs/
    ├── README.md                 Índice de la documentación
    ├── 01-vision-y-alcance.md
    ├── 02-requisitos.md
    ├── 03-arquitectura.md
    ├── 04-seguridad.md
    ├── 05-estrategia-pruebas.md
    ├── 06-roadmap.md
    ├── 07-estado-del-arte.md
    ├── 08-estructura-proyecto.md
    ├── decisiones.md             Registro de decisiones técnicas (ADR)
    ├── registro-pruebas.md       Evidencias de pruebas por fase
    ├── bibliografia.md           Fuentes y licencias de terceros
    ├── api.md                    Documentación de la API                         [Fase 2]
    ├── guia-desarrollo.md        Entorno local de desarrollo                     [Fase 1 ✔]
    ├── guia-instalacion.md       Instalación en el servidor                      [Fase 13]
    ├── guia-uso.md                                                               [Fase 10]
    └── informes/
        └── fase-00.md            Informe de cierre para Gemini (uno por fase)
```

## Justificación

- **Un único paquete Python (`minipaas`) con dos puntos de entrada** (control plane y agente),
  empaquetados en dos imágenes distintas. Así el contrato `ServiceRequest` se define una sola vez en
  `common/` y no se duplica, pero cada contenedor solo ejecuta lo suyo.
- **Disposición `src/`**: evita importar accidentalmente el código sin instalar y es la práctica
  recomendada por la *Python Packaging User Guide*.
- **`spec/` separado de `services/`**: la validación es pura (sin E/S), por lo que se prueba con
  tests unitarios rápidos; la orquestación (con E/S) se prueba con dobles de prueba.
- **El panel dentro del control plane**: se sirve como ficheros estáticos por FastAPI; no requiere un
  servidor web ni un proceso de compilación adicional.
- **Chart.js se incluye en `vendor/`** con su licencia (MIT) en lugar de cargarlo desde un CDN, para
  que el panel funcione sin Internet y sin peticiones a terceros.
- **`templates/` fuera del código**: las plantillas son datos; se pueden añadir sin tocar Python.
