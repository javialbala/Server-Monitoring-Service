# API del control plane

> Estado: **implementado y verificado** en las Fases 2 y 3 (2026-11-15). Solo incluye las rutas que
> existen. La API interna del agente está en `src/minipaas/common/agent_protocol.py` (ADR-029).

La API REST la sirve el control plane en el mismo origen que el panel (`http://127.0.0.1:8000` en
desarrollo). FastAPI genera además la especificación OpenAPI en `/openapi.json`. Las páginas
interactivas `/docs` y `/redoc` están **desactivadas** porque cargan recursos de un CDN (prohibido en
el proyecto y bloqueado por la CSP). La API interna del agente **no** forma parte de esta API ni se
expone.

## Convenciones

| Aspecto | Regla |
|---|---|
| Formato | JSON en peticiones y respuestas (`Content-Type: application/json`) |
| Autenticación | Cookie de sesión `minipaas_session` (`HttpOnly`, `SameSite=Strict`, `Path=/`; `Secure` con HTTPS) |
| CSRF | `POST`, `PATCH` y `DELETE` autenticados exigen la cabecera `X-CSRF-Token` con el token de la sesión |
| Origen | Toda petición no segura con cabecera `Origin` distinta del propio origen recibe 403 |
| Errores | `{"detail": "mensaje en español"}`; los errores de validación de Pydantic (422) devuelven `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| Caché | Todas las respuestas de `/api/` llevan `Cache-Control: no-store` |
| Fechas | ISO 8601 en UTC con segundos, p. ej. `2026-11-15T17:47:03+00:00` |

### Códigos de error comunes

| Código | Significado |
|---|---|
| 401 | `Sesión no iniciada o caducada` (y se borra la cookie si era inválida) |
| 403 | `Token CSRF ausente o no válido` u `Origen de la petición no permitido` |
| 404 | Recurso inexistente |
| 409 | Conflicto (identificador repetido) |
| 422 | Datos no válidos |
| 429 | Demasiados intentos de inicio de sesión (cabecera `Retry-After` en segundos) |

## Estado

### `GET /api/health` — público

```json
{"status": "ok", "agent": {"reachable": true}, "docker": {"reachable": true}}
```

`status` es `"degraded"` si el agente o Docker no responden. Siempre 200.

## Autenticación

### `GET /api/auth/session` — público

Lo usa el panel al cargar para decidir qué pantalla mostrar.

```json
{"authenticated": true, "setup_required": false, "user": {"username": "admin"}, "csrf_token": "…"}
```

Sin sesión: `authenticated: false`, `user: null`, `csrf_token: null`. `setup_required` es `true`
mientras no exista ningún administrador.

### `POST /api/auth/login` — público

```json
{"username": "admin", "password": "…"}
```

| Respuesta | Cuerpo |
|---|---|
| 200 + `Set-Cookie` | `{"user": {"username": "admin"}, "csrf_token": "…"}` |
| 401 | `{"detail": "Usuario o contraseña incorrectos"}` (idéntico exista o no el usuario) |
| 429 + `Retry-After` | `{"detail": "Demasiados intentos fallidos. Inténtalo de nuevo más tarde."}` |

Cada login crea un identificador de sesión nuevo y revoca el anterior del mismo navegador.

### `POST /api/auth/logout` — sesión + CSRF

204. Revoca la sesión en el servidor y borra la cookie.

### `GET /api/auth/me` — sesión

```json
{"username": "admin", "created_at": "2026-11-15T17:40:12+00:00"}
```

## Aplicaciones

Representación de una aplicación (el identificador numérico interno no se expone):

```json
{
  "slug": "mi-blog",
  "name": "Mi blog",
  "description": "WordPress para el blog familiar",
  "status": "draft",
  "status_label": "Sin desplegar",
  "created_at": "2026-11-15T17:47:03+00:00",
  "updated_at": "2026-11-15T17:47:03+00:00"
}
```

| Campo | Reglas |
|---|---|
| `name` | 1–100 caracteres |
| `slug` | `^[a-z][a-z0-9-]{1,38}[a-z0-9]$`, sin `--`; opcional al crear (se deriva del nombre); **inmutable** |
| `description` | 0–500 caracteres |
| `status` | Estado lógico; en esta fase solo `draft` («Sin desplegar») |

| Método y ruta | Protección | Respuestas |
|---|---|---|
| `GET /api/applications` | sesión | 200 `{"items": [ … ]}`, más recientes primero |
| `POST /api/applications` | sesión + CSRF | 201 aplicación · 409 identificador repetido · 422 |
| `GET /api/applications/{slug}` | sesión | 200 · 404 `Aplicación no encontrada` |
| `PATCH /api/applications/{slug}` | sesión + CSRF | 200 · 404 · 422 (incluido intentar cambiar `slug`) |
| `DELETE /api/applications/{slug}` | sesión + CSRF | 204 · 404 |

Cuerpo de `POST`: `{"name": "...", "slug": "..." | null, "description": "..."}`.
Cuerpo de `PATCH`: `{"name"?: "...", "description"?: "..."}`. Se rechazan campos desconocidos.

## Ejemplo con `curl`

```bash
B=http://127.0.0.1:8000
curl -s -c cookies.txt -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"<tu contraseña>"}' $B/api/auth/login   # devuelve csrf_token
curl -s -b cookies.txt $B/api/applications
curl -s -b cookies.txt -H 'Content-Type: application/json' -H "X-CSRF-Token: <csrf_token>" \
     -d '{"name":"Mi blog"}' $B/api/applications
```

(Escribir la contraseña en la línea de órdenes la deja en el historial de la shell; en el panel no
ocurre.)

## Fase 3: catálogo, servicios y despliegues

Todas exigen sesión; las que modifican, además `X-CSRF-Token`. Errores de validación del catálogo:
422 con `detail` en texto.

### Aplicación (campos añadidos)

`"active_revision": int | null` y `"operation_in_progress": bool`. `status` puede ser `draft`
(«Sin desplegar»), `running` («En funcionamiento»), `stopped` («Detenida») o `attention` («Requiere
intervención»). `DELETE /api/applications/{slug}` retira antes sus contenedores y redes mediante el
agente: 409 si hay una operación en curso; 503 si el agente no responde (no se borra nada).

### Catálogo

`GET /api/catalog` → `{"items": [entrada]}` con `id`, `name`, `description`, `version`,
`repository`, `digest`, `architectures`, `internal_ports`, `default_internal_port`, `publishable`,
`env` (`name`, `label`, `help`, `pattern`, `max_length`), `memory_mb` y `cpus` (`default`, `min`,
`max`), `license`, `source`, `limitations`, `test_only`. Las entradas de prueba solo aparecen con
`MINIPAAS_ENABLE_TEST_CATALOG=true`.

### Servicios

```json
{"name": "web", "catalog_id": "whoami", "catalog_name": "Servicio HTTP de prueba (whoami)",
 "internal_port": 80, "publish": true, "host_port": 20000, "env": {"WHOAMI_NAME": "demo"},
 "memory_mb": 32, "cpus": 0.25, "created_at": "…", "updated_at": "…", "protected": false}
```

| Método y ruta | Respuestas |
|---|---|
| `GET /api/applications/{slug}/services` | 200 `{"items": […]}` |
| `POST /api/applications/{slug}/services` | 201 · 409 nombre o puerto ocupado / sin puertos libres · 422 |
| `PATCH /api/applications/{slug}/services/{name}` | 200 · 404 · 409 · 422 (`name` y `catalog_id` no se pueden cambiar) |
| `DELETE /api/applications/{slug}/services/{name}` | 204 · 409 si pertenece a la revisión en funcionamiento (`protected`) |

Cuerpo de alta: `{"name", "catalog_id", "internal_port"?, "publish"? = false, "host_port"? (null =
asignación automática), "env"? = {}, "memory_mb"?, "cpus"?}`. Los valores omitidos toman el valor por
defecto del catálogo.

### Revisiones y despliegues

```json
{"revision": 2, "operation_id": "9b1c…", "status": "rolled_back",
 "status_label": "Fallida · versión anterior recuperada", "is_active": false,
 "previous_revision": 1, "error": "El servicio «broken» se detuvo al arrancar (código 1)",
 "created_at": "…", "started_at": "…", "finished_at": "…",
 "services": [{"name": "web", "catalog_id": "whoami", "catalog_name": "…",
               "image_ref": "traefik/whoami@sha256:…", "internal_port": 80, "host_port": 20000,
               "memory_mb": 32, "cpus": 0.25, "env_names": ["WHOAMI_NAME"]}]}
```

| Método y ruta | Respuestas |
|---|---|
| `POST /api/applications/{slug}/revisions` `{"request_id": "<uuid4>"}` | 201 nueva revisión `pending` · 200 si ese `request_id` ya existía · 409 sin servicios |
| `POST /api/applications/{slug}/revisions/{n}/deploy` | 202 (empieza en segundo plano) · 200 si ya no estaba `pending` · 409 operación en curso o revisión no más reciente |
| `GET /api/applications/{slug}/deployments` | 200 `{"items": […]}`, más reciente primero |
| `GET /api/applications/{slug}/deployments/{n}` | 200 con `"events": [{"occurred_at", "step", "outcome", "message"}]` |

Estados del despliegue: `pending`, `preparing`, `deploying`, `healthy`, `stopped`, `superseded`,
`discarded`, `failed`, `rolling_back`, `rolled_back`, `rollback_failed`, `interrupted` (ADR-028).
El historial nunca devuelve valores de variables de entorno, solo sus nombres.

### Estado real y ciclo de vida

| Método y ruta | Respuestas |
|---|---|
| `GET /api/applications/{slug}/runtime` | 200 `{"agent_reachable", "active_revision", "services": [{"name", "revision", "state", "state_label", "exit_code", "host_port", "access_url"}], "unknown_containers"}`; si el agente no responde, `agent_reachable=false` |
| `POST /api/applications/{slug}/stop` | 200 aplicación · 409 · 503 |
| `POST /api/applications/{slug}/start` | 200 aplicación (espera a la comprobación de salud) · 502 si no arranca (queda «Requiere intervención») · 409 · 503 |
| `POST /api/applications/{slug}/recover` | 200 aplicación · 409 · 503 |
