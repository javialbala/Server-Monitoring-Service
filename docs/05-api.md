# 5. API

> Estado: **implementado y probado** (contrato v2, 2026-11-16): `tests/panel`, `tests/agent`,
> `scripts/e2e_monitor.sh` y `scripts/e2e_ui.py`. Los valores de los ejemplos son ilustrativos.
> Implementación en [04-backend.md](04-backend.md).

Hay dos APIs: la del **panel** (la ve el navegador) y la **interna del agente** (solo la ve el panel).
Ninguna tiene `/docs`, `/redoc` ni `/openapi.json`. No existe ninguna ruta que modifique Docker.

## 5.1 API del panel (puerto 8000; `http://IP-DEL-SERVIDOR:8000`)

### Convenciones

| Aspecto | Regla |
|---|---|
| Formato | JSON |
| Autenticación | Cookie `sms_session` (`HttpOnly`, `SameSite=Strict`, `Path=/`; `Secure` si `SMS_COOKIE_SECURE=true`) |
| CSRF | `POST /api/logout` exige la cabecera `X-CSRF-Token` con el token de la sesión |
| Origen | Las peticiones `POST`/`PUT`/`PATCH`/`DELETE` con cabecera `Origin` distinta del propio origen reciben 403 |
| Errores | `{"detail": "mensaje en español"}`; los de validación (422) usan el formato de Pydantic |
| Caché | Las respuestas de `/api/` llevan `Cache-Control: no-store` |
| Cabeceras | CSP `default-src 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` |
| Archivos estáticos | Se sirven en `/` (interfaz web, fuentes, iconos) |

### Rutas

| Método y ruta | Protección | Respuestas |
|---|---|---|
| `GET /api/health` | pública | 200 `{"status": "ok"}` (la usa el *healthcheck* del contenedor) |
| `GET /api/session` | pública | 200 `{"authenticated": bool, "csrf_token": str \| null}` |
| `POST /api/login` | pública | 204 + cookie · 401 `Contraseña incorrecta` · 422 · 429 + `Retry-After`· 403 `Origin` ajeno |
| `POST /api/logout` | sesión + CSRF | 204 · 401 sin sesión · 403 sin token CSRF o `Origin` ajeno |
| `GET /api/metrics` | sesión | 200 (JSON del agente, tal cual) · 401 `Sesión no iniciada o caducada` · 502 `El agente no responde` |
| `GET /api/containers` | sesión | 200 (JSON del agente, tal cual) · 401 · 502 `El agente no responde` |

Cuerpo de `POST /api/login`: `{"password": "..."}` (1 a 128 caracteres; la contraseña no se recorta;
cualquier otro campo da 422). Tras 5 fallos en 15 minutos desde una IP se responde 429 aunque la
contraseña sea correcta. Cada login correcto crea un identificador de sesión nuevo y revoca el
anterior del mismo navegador. Una sesión caduca a los 30 minutos de inactividad o a las 8 horas de su
creación.

### Códigos de error

| Código | Cuándo |
|---|---|
| 401 | Sin sesión o caducada; contraseña incorrecta en el login |
| 403 | Falta o no coincide el token CSRF; `Origin` ajeno |
| 422 | Cuerpo del login inválido (vacío, más de 128 caracteres o con campos de más) |
| 429 | Demasiados intentos fallidos (cabecera `Retry-After` en segundos) |
| 502 | El agente no responde, devuelve un error o un JSON inválido (también cuando Docker falla) |

## 5.2 API interna del agente (puerto 8001, solo en la red interna)

Todas las rutas son `GET` y **no tienen autenticación**: el agente solo es alcanzable desde la red
`internal` de Compose, sin puertos publicados (ADR-051).

### `GET /health`

```json
{"status": "ok", "docker": {"reachable": true, "server_version": "29.9.2"}}
```

Si Docker no responde: `"reachable": false, "server_version": null` (sigue siendo 200).

### `GET /metrics`

```json
{
  "collected_at": "2026-11-16T10:00:00.123Z",
  "hostname": "servidor",
  "os": {"name": "Ubuntu 24.04.1 LTS", "kernel": "6.8.0-45-generic", "architecture": "x86_64"},
  "uptime_seconds": 12345,
  "cpu": {"percent": 12.5, "cores": 8, "model": "Intel(R) Core(TM) i7-8550U CPU @ 1.80GHz"},
  "memory": {"total_bytes": 16637489152, "used_bytes": 7584000000, "available_bytes": 9053489152, "percent": 45.6},
  "disks": [
    {"name": "Sistema", "path": "/", "total_bytes": 255000000000, "used_bytes": 160000000000, "free_bytes": 95000000000, "percent": 62.7},
    {"name": "datos", "path": "/disks/datos", "total_bytes": 1000000000000, "used_bytes": 400000000000, "free_bytes": 600000000000, "percent": 40.0}
  ],
  "temperature": {"celsius": 46.0, "sensor": "coretemp: Package id 0"},
  "network": {
    "rx_bytes": 123456789, "tx_bytes": 45678901,
    "interfaces": [{"name": "enp0s31f6", "rx_bytes": 123456789, "tx_bytes": 45678901}]
  }
}
```

| Campo | Significado y casos especiales |
|---|---|
| `collected_at` | Instante de la medición, UTC con milisegundos. El navegador lo usa para calcular velocidades |
| `hostname`, `os.name`, `uptime_seconds`, `cpu.model` | `null` si no se pueden leer |
| `cpu.percent` | Medición de 0,5 s (por eso la consulta tarda ~0,5 s) |
| `memory.percent` | `(MemTotal − MemAvailable) / MemTotal × 100` |
| `disks` | Siempre el raíz primero («Sistema», `/`); luego los de `/disks/<nombre>` ordenados por nombre. Los del mismo sistema de archivos que el raíz se omiten |
| `temperature` | Paquete del procesador; **`null`** si no hay sensor fiable |
| `network` | Contadores **acumulados desde el arranque** (suma de las interfaces de la lista, sin `lo`, `veth*`, `br-*`, `docker*`, `virbr*`); **`null`** si no se puede leer el archivo. No es una velocidad |

| Cálculo | Regla |
|---|---|
| CPU % | `100 × (1 − Δidle / Δtotal)` con dos lecturas de `/proc/stat` separadas 0,5 s; `idle = idle + iowait`; 1 decimal |
| RAM | `usada = MemTotal − MemAvailable`; `porcentaje = usada / total × 100` |
| Disco | `statvfs`: `total = f_blocks·f_frsize`, `libre = f_bavail·f_frsize`, `usado = (f_blocks − f_bfree)·f_frsize`, `porcentaje = usado / (usado + libre) × 100` (como `df`) |
| Temperatura | `coretemp` «Package id 0» o `k10temp` «Tctl» en `/sys/class/hwmon`; si no, `thermal_zone` `x86_pkg_temp`. Milésimas de grado → °C; se descartan ≤ 0 y > 150 °C |
| Velocidad de red | **La calcula el navegador**: `Δbytes / Δ(collected_at)` entre dos muestras |

Los campos `disk` (singular) y `temperatures` (lista) de la versión anterior **ya no existen**.

### `GET /containers`

```json
{
  "collected_at": "2026-11-16T10:00:00.456Z",
  "containers": [
    {"id": "abc123def456", "name": "jellyfin", "image": "jellyfin/jellyfin:latest",
     "state": "running", "status": "Up 3 hours (healthy)", "health": "healthy",
     "created_at": "2026-11-01T08:00:00Z",
     "ports": [
       {"container_port": 8096, "protocol": "tcp", "host_ip": "0.0.0.0", "host_port": 8096},
       {"container_port": 8096, "protocol": "tcp", "host_ip": "::", "host_port": 8096}
     ],
     "compose_project": "media", "compose_service": "jellyfin"},
    {"id": "0f9e8d7c6b5a", "name": "backup", "image": "alpine:3.20",
     "state": "exited", "status": "Exited (0) 2 days ago", "health": null,
     "created_at": "2026-11-10T09:30:00Z", "ports": [],
     "compose_project": null, "compose_service": null}
  ]
}
```

| Campo | Significado |
|---|---|
| `state` | `running`, `exited`, `paused`, `restarting`, `created`, `dead` o `removing` (tal cual lo da Docker) |
| `status` | Texto de Docker, en inglés (`Up 3 hours`, `Exited (0) 2 days ago`...) |
| `health` | `healthy`, `unhealthy`, `starting` o `null`; se deduce del texto de `status` |
| `ports` | Un puerto no publicado tiene `host_ip` y `host_port` a `null`. Un puerto publicado en IPv4 e IPv6 aparece repetido (`0.0.0.0` y `::`) |
| `compose_project`, `compose_service` | Etiquetas de Compose, o `null` |

**Orden:** primero los contenedores en ejecución y después el resto; dentro de cada grupo, por nombre.
Se listan **todos** los contenedores (en marcha y detenidos) con una sola llamada de lectura a
Docker. Si Docker no responde: 503 `{"detail": "Docker no está disponible"}`.

## 5.3 Ejemplo con `curl` (panel)

```bash
B=http://127.0.0.1:8000
curl -s -c cookies.txt -H 'Content-Type: application/json' \
     -d '{"password":"<tu contraseña>"}' $B/api/login -i       # 204 + cookie
curl -s -b cookies.txt $B/api/metrics
curl -s -b cookies.txt $B/api/containers
```

(Escribir la contraseña en la línea de órdenes la deja en el historial de la shell; en el panel no
ocurre.)
