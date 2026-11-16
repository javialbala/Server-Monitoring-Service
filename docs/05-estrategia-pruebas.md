# 5. Estrategia de pruebas

> Estado del documento: **reescrito en la renovación (2026-11-16)**. El apartado 5.5 recoge las
> pruebas implementadas y su resultado real; el detalle de cada ejecución está en
> `registro-pruebas.md`.

## 5.1 Niveles de prueba

| Nivel | Qué prueba | Herramienta | Necesita Docker | Cuándo |
|---|---|---|---|---|
| **Unitarias del agente** | Cálculo de métricas con directorios falsos (`/proc`, `/sys`, `hostfs`) y conversión de contenedores | `pytest` | No | Siempre (local y CI) |
| **API del agente** | Token, rutas solo `GET`, 503 sin detalles, `/metrics` con un anfitrión falso | `pytest` + `TestClient`, cliente Docker falso | No | Siempre |
| **API del panel** | Login, cookie, 429, CSRF, `Origin`, caducidad de sesión, 401, 502, cabeceras | `pytest` + `TestClient`, agente falso | No | Siempre |
| **Integración** | Agente contra Docker real: contenedor ajeno detectado, parado ignorado, métricas coherentes | `pytest -m integration` (3 tests) | Sí | Local, antes de cerrar la fase (el CI las excluye) |
| **Extremo a extremo** | Sistema completo en un proyecto Compose aparte: contraseña, métricas frente al anfitrión, contenedores, solo lectura, sesión, bloqueo | `bash scripts/e2e_monitor.sh` (29 comprobaciones) | Sí | Local |
| **Navegador** | Recorrido del panel real: login, tarjetas, actualización, pausa, logout | `scripts/e2e_ui.py` con Playwright vía `uvx` (11 comprobaciones) | Sí | Local |
| **Estilo** | Formato y errores comunes | `ruff check`, `ruff format --check` | No | Siempre |

## 5.2 Cómo se prueba cada parte

| Parte | Pruebas clave |
|---|---|
| Métricas | CPU con dos lecturas falsas (incluido sin cambios → 0 %), RAM, disco con `statvfs`, uptime, modelo ausente, sensores ausentes o ilegibles, `os-release` en `/etc` o `/usr/lib` |
| Contenedores | Conversión de puertos (publicados y no publicados), nombre sin barra, ordenación, etiquetas de Compose, una sola llamada de lectura |
| Solo lectura | Todas las rutas del agente son `GET`; sin `/docs`; el cliente falso solo admite `containers` y `version`; en el E2E, `docker events` no registra eventos de modificación durante las consultas |
| Autenticación | Contraseña correcta/incorrecta, sin contraseña configurada (503), 5 fallos → 429 incluso con la contraseña correcta, cookie `HttpOnly`/`SameSite=Strict`, caducidad por inactividad y absoluta |
| CSRF | Logout sin token → 403, `Origin` ajeno → 403 |
| `set-password` | Rechaza 3 caracteres, acepta 4, guarda el hash y no la contraseña, reemplaza el hash anterior |
| Panel (navegador) | Mensaje de error con contraseña incorrecta, tarjetas visibles, tabla con filas, la hora cambia sola, sin consultas con la pestaña oculta, reanudación, logout |

## 5.3 Reglas de las pruebas con Docker

- Solo contra el **Docker local**, nunca contra el servidor real.
- Los proyectos Compose de prueba (`minipaas-e2e`, `minipaas-ui`) son distintos del de desarrollo
  (`minipaas-dev`) y se eliminan al terminar.
- Los contenedores de prueba son pequeños y llevan una etiqueta propia; se eliminan al terminar.

## 5.4 Registro de evidencias

Cada ejecución relevante se anota en `docs/registro-pruebas.md` con fecha, comando y resultado real.
No se registra como superada ninguna prueba que no se haya ejecutado.

## 5.5 Pruebas implementadas en la renovación

| Ubicación | Qué cubre |
|---|---|
| `tests/agent/test_host_metrics.py` | Funciones de lectura de `/proc`, `/sys` y `hostfs` |
| `tests/agent/test_containers.py` | Conversión de los datos de Docker |
| `tests/agent/test_agent_api.py` | Token, rutas, métricas con anfitrión falso, 503 |
| `tests/agent/test_agent_docker_integration.py` | 3 tests con Docker real (marcador `integration`) |
| `tests/panel/test_auth.py` | Login, 429, CSRF, `Origin`, sesiones, `set-password`, limitador |
| `tests/panel/test_api.py` | Rutas protegidas, reenvío al agente, 502, estáticos con CSP |
| `tests/unit/test_secrets.py` | Lectura y validación del token |
| `scripts/e2e_monitor.sh` | 29 comprobaciones de extremo a extremo |
| `scripts/e2e_ui.py` | 11 comprobaciones en navegador |

Resultado total: **48 tests** (45 sin integración). Cifras y salida en `registro-pruebas.md`.

## 5.6 Integración continua

El *workflow* de GitHub Actions ejecuta `ruff check`, `ruff format --check` y
`pytest -m "not integration"`; **excluye** las pruebas de integración y no ejecuta el E2E ni la
prueba de navegador. No se ha ejecutado el CI en GitHub para esta rama (no se ha hecho *push*).

## 5.7 No probado

- El servidor Ubuntu real (la autorización no se ha pedido ni dado).
- `scripts/verify_dev_env.sh` en esta renovación (pendiente); sus comprobaciones de seguridad están
  cubiertas solo en parte por `e2e_monitor.sh`.
- Consumo de memoria y CPU de los contenedores; carga con muchos contenedores.
