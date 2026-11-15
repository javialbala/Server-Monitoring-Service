# 5. Estrategia de pruebas

> Estado del documento: **aprobado por el equipo (2026-11-15)**; el apartado 5.5 recoge las pruebas
> implementadas hasta la Fase 2.

## 5.1 Niveles de prueba

| Nivel | Qué prueba | Herramienta | Necesita Docker | Cuándo se ejecuta |
|---|---|---|---|---|
| **Unitarias** | Validación de especificaciones (`spec/*`), política del agente, conversión configuración → `ServiceRequest` y construcción de la configuración Docker en el agente, utilidades | `pytest` | No | Siempre (local y CI) |
| **API** | Endpoints del control plane: autenticación, CSRF, permisos, códigos de estado, auditoría | `pytest` + `TestClient` de FastAPI, con un **agente falso** en memoria | No | Siempre (local y CI) |
| **Agente** | Endpoints del agente con un cliente Docker simulado | `pytest` + doble de prueba del SDK | No | Siempre |
| **Integración** | Flujo real contra Docker: crear, arrancar, redesplegar, *rollback*, volúmenes, redes, límites, recursos ajenos protegidos | `pytest -m integration` | Sí (local) | Manualmente y antes de cerrar cada fase |
| **Extremo a extremo (panel)** | Recorridos principales del panel | Lista de comprobación manual; Playwright opcional en la Fase 12 | Sí | Fases 10 y 12 |
| **Seguridad** | Intentos de abuso: campos peligrosos, rutas, puertos fuera de rango, sin sesión, CSRF, XSS en nombres/logs | `pytest` (unitarias + integración) + revisión manual | Parcial | Cada fase con superficie nueva; auditoría en la Fase 11 |
| **Rendimiento / consumo** | RAM y CPU de MiniPaaS en reposo y bajo uso; tiempo de despliegue | `docker stats`, scripts de medición | Sí | Fase 12 |
| **Estilo** | Formato y errores comunes | `ruff check`, `ruff format --check` | No | Siempre |

## 5.2 Cómo se prueba cada componente

| Componente | Pruebas clave |
|---|---|
| Validación (`spec/`) | Nombres válidos/ inválidos (mayúsculas, `..`, longitud), referencias de imagen, puertos fuera de rango o duplicados, rutas de volumen prohibidas, límites ausentes → valores por defecto. |
| Política del agente | Rechazo de campos desconocidos (incluido cualquier intento de pasar parámetros de Docker como `privileged`, `cap_add`, `binds`, `network_mode`); comprobación de que la configuración que construye el agente nunca contiene opciones peligrosas; rechazo de operaciones sobre recursos sin `minipaas.managed=true`; aplicación de `no-new-privileges` y límites. |
| Servicio de despliegues | Despliegue correcto; fallo de imagen inexistente; fallo de arranque → restauración de la versión anterior de la aplicación; candado por aplicación; recuperación tras reinicio a mitad de despliegue; *rollback* que recupera la imagen y configuración anteriores **sin alterar el contenido de los volúmenes** (se comprueba que un dato escrito por la versión nueva sigue presente, para verificar que el comportamiento documentado es el real). |
| API | 401 sin sesión, 403 sin token CSRF, 422 con datos inválidos, 404 con recursos inexistentes, secretos nunca devueltos, eventos de auditoría generados. |
| Monitorización | Formato de métricas; `tail` acotado; comportamiento si el contenedor no existe. |
| Persistencia | Esquema creado desde cero; migraciones de versión; integridad referencial. |
| Panel | Login, crear desde plantilla, ver estado, ver logs, detener, eliminar con confirmación, mensajes de error comprensibles, uso en pantalla estrecha. |

## 5.3 Reglas de las pruebas de integración

- Solo se ejecutan contra el **Docker local**, nunca contra el servidor real.
- Usan imágenes pequeñas y públicas (por ejemplo `nginx:alpine`, `busybox`, `traefik/whoami`).
- Todo recurso creado lleva además la etiqueta `minipaas.test=true` y un sufijo único; una
  *fixture* de `pytest` lo elimina al terminar, aunque el test falle.
- Incluyen un test que crea un contenedor **ajeno** (sin etiqueta) y comprueba que MiniPaaS no
  puede pararlo ni borrarlo.

## 5.4 Registro de evidencias

Cada ejecución relevante se anota en `docs/registro-pruebas.md` con fecha, fase, comando, resultado
real y observaciones. Los informes de fase enlazan esas entradas. No se registra como superada
ninguna prueba que no se haya ejecutado.

## 5.5 Pruebas implementadas hasta la Fase 2

| Nivel | Archivos | Qué cubren |
|---|---|---|
| Unitarias | `tests/unit/test_database.py`, `test_migrations.py`, `test_repositories.py` | Creación e inicialización idempotente, versión del esquema, migraciones atómicas (una migración con error no deja cambios), versión futura rechazada, claves foráneas, `CHECK`, WAL, rollback |
| Unitarias | `test_passwords.py`, `test_session_service.py`, `test_rate_limit.py`, `test_audit.py`, `test_slug.py`, `test_manage.py`, `test_settings.py`, `test_secrets.py`, `test_naming.py`, `test_docker_runtime_errors.py` | Argon2id, caducidad absoluta y por inactividad con reloj falso, ventana de intentos, metadatos prohibidos, derivación y validación del slug, CLI de administración, configuración |
| API | `tests/api/test_auth_api.py`, `test_csrf_api.py`, `test_applications_api.py`, `test_audit_api.py`, `test_persistence_api.py`, `test_controlplane_api.py`, `test_agent_api.py` | Login/logout, cookies, 401/403/409/422/429, CSRF y `Origin`, CRUD de aplicaciones, auditoría sin secretos, persistencia tras recrear la aplicación, cabeceras |
| Integración | `tests/integration/test_docker_runtime.py` | `ping` contra el Docker local real |
| Entorno | `scripts/verify_dev_env.sh` | 12 propiedades de aislamiento del entorno Compose |
| Extremo a extremo | `scripts/e2e_phase2.sh` | Flujo completo contra contenedores reales en un proyecto Compose separado |
| Panel | Recorrido con Chromium *headless* (herramienta temporal, no versionada) | Login, errores, alta, duplicado, detalle, borrado con diálogo, estado, móvil y modo oscuro, sesión caducada |

Todas las pruebas que tocan la base de datos usan un archivo temporal (`tmp_path`); ninguna usa la
base de datos de desarrollo.

### Pruebas añadidas en la Fase 3

| Nivel | Archivos | Qué cubren |
|---|---|---|
| API del agente (doble del SDK) | `tests/api/test_agent_api.py` (102), `tests/unit/test_agent_operations.py`, `test_agent_config.py` | Token, rutas inexistentes, catálogo no autorizado o de prueba sin permiso, arquitectura, digest, puertos, variables, campos extra (`privileged`, `command`, `image`), propiedad (sin etiquetas, otra app, otra instancia), idempotencia, configuración construida, errores 502/503, variables nunca en logs |
| Integración del agente con Docker real | `tests/integration/test_agent_docker.py` (7) | Imágenes y digest, redes (`internal` y sin NAT), dos servicios, sonda, acceso desde el host, aislamiento entre apps, sin Internet, endurecimiento por `docker inspect`, detener/arrancar, `test-crash` y `test-unhealthy`, contenedor ajeno protegido, limpieza |
| API del control plane (agente falso) | `test_catalog_api.py`, `test_services_api.py` (41), `test_deployments_api.py`, `test_deploy_failures_api.py`, `test_lifecycle_api.py`; `tests/unit/test_cp_*.py` | Migración 0002 sobre datos de la Fase 2, *trigger* e índice; servicios y puertos; revisiones e idempotencia; motor (éxito, fallos de descarga/creación/arranque/salud, *timeout*, rollback correcto y fallido, sin versión anterior, apagado durante un despliegue); concurrencia con hilos; reinicio y recuperación; detener/arrancar; borrado con agente; auditoría sin valores de variables |
| Extremo a extremo | `scripts/e2e_phase3.sh` + `e2e_phase3.py` | 23 comprobaciones con contenedores reales en un proyecto separado (ver `registro-pruebas.md`) |

## 5.6 Integración continua

Un *workflow* de GitHub Actions que ejecute `ruff` y las pruebas unitarias y de API en cada *push* y
*pull request*. Las pruebas de integración con Docker se ejecutan en local (podrían añadirse a CI
más adelante, ya que los *runners* de GitHub incluyen Docker). Se configurará en la Fase 1.
