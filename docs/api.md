# API del control plane

> Estado: **implementado y verificado en la Fase 2** (2026-11-15). Solo incluye las rutas que existen;
> las de despliegue llegarán en fases posteriores.

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
