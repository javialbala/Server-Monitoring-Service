# API de la plataforma

> Estado: **implementado y verificado en la renovación** (2026-11-16): `tests/panel`, `tests/agent`,
> `scripts/e2e_monitor.sh` y `scripts/e2e_ui.py`. La API de la etapa PaaS (aplicaciones, auditoría,
> `/api/auth/*`) ya no existe.

Hay dos APIs: la del **panel** (la ve el navegador) y la **interna del agente** (solo la ve el panel).
Ninguna tiene `/docs` ni `/redoc`.

## 1. API del panel (puerto 8000, `http://127.0.0.1:8000` en desarrollo)

### Convenciones

| Aspecto | Regla |
|---|---|
| Formato | JSON |
| Autenticación | Cookie `minipaas_session` (`HttpOnly`, `SameSite=Strict`, `Path=/`; `Secure` si `MINIPAAS_COOKIE_SECURE=true`) |
| CSRF | El cierre de sesión exige la cabecera `X-CSRF-Token` con el token de la sesión |
| Origen | Las peticiones no seguras (`POST`...) con cabecera `Origin` distinta del propio origen reciben 403 |
| Errores | `{"detail": "mensaje en español"}`; los errores de validación (422) usan el formato de Pydantic |
| Caché | Las respuestas de `/api/` llevan `Cache-Control: no-store` |
| Cabeceras | CSP `default-src 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` |
| Archivos estáticos | Se sirven en `/` (panel web) |

### Rutas

| Método y ruta | Protección | Respuestas |
|---|---|---|
| `GET /api/health` | pública | 200 `{"status": "ok"}` (healthcheck del contenedor) |
| `GET /api/session` | pública | 200 `{"authenticated": bool, "csrf_token": str\|null}` |
| `POST /api/login` | pública | 204 + cookie · 401 `Contraseña incorrecta` · 422 · 429 + `Retry-After` · 503 `No hay contraseña configurada` |
| `POST /api/logout` | sesión + CSRF | 204 · 401 sin sesión · 403 sin token CSRF |
| `GET /api/metrics` | sesión | 200 (JSON del agente) · 401 · 502 `El agente no responde` |
| `GET /api/containers` | sesión | 200 (JSON del agente) · 401 · 502 |

Cuerpo de `POST /api/login`: `{"password": "..."}` (1 a 128 caracteres; la contraseña no se recorta).
Tras 5 fallos en 15 minutos desde una IP se responde 429 aunque la contraseña sea correcta.
Cada login correcto crea un identificador de sesión nuevo y revoca el anterior del mismo navegador.
Una sesión caduca a los 30 minutos de inactividad o a las 8 horas de su creación.

## 2. API interna del agente (puerto 8001, solo en la red interna)

Todas las rutas son `GET` y exigen `Authorization: Bearer <token>` (401 `No autorizado` si falta o es
incorrecto, sin distinguir cuál). Sin documentación OpenAPI.

### `GET /health`

```json
{"status": "ok", "docker": {"reachable": true, "server_version": "29.9.2"}}
```

Si Docker no responde: `"reachable": false, "server_version": null` (sigue siendo 200).

### `GET /metrics`

```json
{
  "collected_at": "2026-11-16T10:00:00Z",
  "hostname": "servidor",
  "os": {"name": "Ubuntu 24.04.1 LTS", "kernel": "6.8.0-45-generic", "architecture": "x86_64"},
  "uptime_seconds": 12345,
  "cpu": {"percent": 12.5, "cores": 8, "model": "Intel(R) ..."},
  "memory": {"total_bytes": 0, "used_bytes": 0, "available_bytes": 0, "percent": 0.0},
  "disk": {"path": "/", "total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "percent": 0.0},
  "temperatures": [{"sensor": "x86_pkg_temp", "celsius": 45.0}]
}
```

(Los valores son de ejemplo.) `hostname`, `os.name`, `uptime_seconds` y `cpu.model` son `null` si no se
pueden leer; `temperatures` es una lista vacía si no hay sensores.

| Cálculo | Regla |
|---|---|
| CPU % | `100 × (1 − Δidle / Δtotal)` con dos lecturas de `/proc/stat` separadas 0,5 s; `idle = idle + iowait`; 1 decimal |
| RAM | `usada = MemTotal − MemAvailable`; `porcentaje = usada / total × 100` |
| Disco | `statvfs`: `total = f_blocks·f_frsize`, `libre = f_bavail·f_frsize`, `usado = (f_blocks − f_bfree)·f_frsize`, `porcentaje = usado / (usado + libre) × 100` (como `df`) |
| Temperatura | `/sys/class/thermal/thermal_zone*/temp` en milésimas de grado → °C |

### `GET /containers`

```json
{
  "collected_at": "2026-11-16T10:00:00Z",
  "containers": [
    {"id": "abc123def456", "name": "jellyfin", "image": "jellyfin/jellyfin:latest",
     "state": "running", "status": "Up 3 hours", "created_at": "2026-11-01T08:00:00Z",
     "ports": [{"container_port": 8096, "protocol": "tcp", "host_ip": "0.0.0.0", "host_port": 8096}],
     "compose_project": "media", "compose_service": "jellyfin"}
  ]
}
```

Solo contenedores en ejecución, ordenados por nombre. Un puerto no publicado tiene `host_ip` y
`host_port` a `null`. Si Docker no responde: 503 `{"detail": "Docker no está disponible"}`.

## 3. Ejemplo con `curl` (panel)

```bash
B=http://127.0.0.1:8000
curl -s -c cookies.txt -H 'Content-Type: application/json' \
     -d '{"password":"<tu contraseña>"}' $B/api/login -i       # 204 + cookie
curl -s -b cookies.txt $B/api/metrics
curl -s -b cookies.txt $B/api/containers
```

(Escribir la contraseña en la línea de órdenes la deja en el historial de la shell; en el panel no
ocurre.)
