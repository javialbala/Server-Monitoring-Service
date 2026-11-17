# 6. Seguridad y riesgos

> Estado del documento: **actualizado en la fase de rediseño de interfaz y limpieza (2026-11-16)**.
> Cada medida indica si está verificada por una prueba ejecutada (ver [07-pruebas.md](07-pruebas.md))
> o es solo de diseño. Las pruebas se han hecho en local; **no** en el servidor Ubuntu real. El
> detalle de implementación está en [04-backend.md](04-backend.md).

## 6.1 Activos a proteger

1. **El anfitrión** y los servicios que ya ejecuta (el activo más importante).
2. **El socket de Docker** (equivale a root en el anfitrión).
3. **La contraseña** del panel y las sesiones.
4. La **información** que muestra el panel (nombres de contenedores, imágenes, puertos, versión del
   kernel, discos, temperatura): útil para un atacante, aunque no son secretos de aplicaciones.

## 6.2 Modelo de amenazas resumido

| # | Amenaza | Vector | Medida | Estado |
|---|---|---|---|---|
| T1 | Control de Docker desde el componente expuesto | Fallo en el panel | El panel no tiene el socket; solo el agente | Verificado (E2E) |
| T2 | Un atacante usa el agente para modificar Docker | Llamar al agente directamente o abusar de él | Agente en red interna sin puertos publicados, token Bearer en todas las rutas, solo rutas `GET`, solo dos consultas de lectura a Docker (`containers(all=True)` y `version`), sin ejecución de comandos | Verificado (tests del agente; `docker events` sin eventos de modificación en el E2E) |
| T3 | Acceso no autorizado al panel | Adivinar la contraseña | Argon2id, 5 fallos en 15 min por IP → 429, contraseña de 4 a 128 caracteres | Verificado |
| T4 | Robo o fijación de sesión | Cookie robada, identificador previsible | Token de 256 bits, guardado como SHA-256; cookie `HttpOnly`, `SameSite=Strict`, `Secure` configurable; identificador nuevo en cada login; caducidad 30 min de inactividad y 8 h absolutas | Verificado (tests; el flag `Secure` solo se prueba como atributo) |
| T5 | CSRF | Web ajena que haga peticiones | Token por sesión en `X-CSRF-Token` (logout) y rechazo de `Origin` ajeno en métodos no seguros | Verificado |
| T6 | XSS | Nombre de contenedor o imagen con HTML | Datos solo con `textContent`/`createElement`, sin `innerHTML`; CSP `default-src 'self'` (fuentes, iconos y gráficas son propios: sin recursos externos); `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` | Verificado (cabeceras en test; revisión del JS) |
| T7 | Inyección de comandos | Datos del usuario en comandos | No se ejecutan comandos: solo la API de Docker y lecturas de archivos | Verificado por revisión |
| T8 | Escritura en el anfitrión | Montajes del agente | `/hostfs` en solo lectura y sin submontajes; `/host/net/dev` (un único archivo) y `/disks/*` en solo lectura; proceso no root | Verificado `/hostfs` (E2E); `/host/net/dev` (E2E y contenedor efímero); `/disks/*` sin probar con disco real |
| T8b | El agente lee más de lo previsto | Discos y archivos del anfitrión visibles para el agente | Los discos extra los declara el administrador en Compose (nada se descubre solo); solo se leen rutas fijas | Diseño (ADR-044) |
| T9 | Fuga de la contraseña | Registros, argumentos, disco | Llega por la variable `APP_PASSWORD` (nunca como argumento); en disco solo el hash Argon2id (`/data/password_hash`, 600); ni el log ni los mensajes de error la escriben | Verificado en tests (hash, `caplog`) y en el E2E (el archivo y `docker compose logs` no la contienen) |
| T9b | Contraseña visible en el entorno del contenedor | `docker inspect` | Riesgo **aceptado**: quien lee el entorno ya tiene acceso a Docker (equivalente a root). El valor vive en `deploy/.env` (no versionado, permisos 600), no en el YAML | Diseño (ADR-049); riesgo residual |
| T9c | Cambio de contraseña involuntario | Editar `.env` por error | Un valor distinto del guardado impide arrancar salvo `APP_PASSWORD_RESET=true` | Verificado (tests y E2E) |
| T10 | Fuga de detalles internos | Mensajes de error | 502/503 genéricos; el detalle solo va al log | Verificado en tests |
| T11 | Documentación de API como superficie | `/docs`, `/openapi.json` | Desactivadas en panel y agente | Verificado |
| T12 | Exposición del panel a Internet | Publicar el puerto | Por defecto escucha solo en `127.0.0.1`; HTTPS pendiente (proxy) | Diseño |

## 6.3 Medidas por componente

**Panel.** Usuario no root (UID 10001), `read_only`, `tmpfs` en `/tmp`, `cap_drop: ALL`,
`no-new-privileges`, sin socket, sin `privileged`. Escribe solo en `/data`. Usuario `sms-panel`.

**Agente.** Usuario `sms-agent`, UID 10002, `read_only`, `cap_drop: ALL`, `no-new-privileges`, red `internal`, sin
`ports`. El socket se monta sin `:ro` porque `:ro` no limitaría la API (ADR-037); la solo-lectura la
garantiza el código. `/hostfs` de solo lectura y no recursivo (ADR-038); `/proc/1/net/dev` montado como un único archivo de solo lectura (ADR-046); discos extra en `/disks/<nombre>` de solo lectura (ADR-044). El grupo `docker` se añade
con `group_add`.

**Secretos.** El token compartido está en archivos con permisos 600, una copia por componente
(`panel_token` y `agent_token`, ADR-014).

## 6.4 Riesgo residual reconocido

- **El socket de Docker sigue dando acceso equivalente a root al agente.** Si se compromete el
  agente, se compromete el anfitrión. Se reduce con un agente mínimo, sin puertos, no root y con
  token. Mejora posible (decisión futura, añadiría una dependencia o componente): un proxy del
  socket que solo permita lecturas.
- **Sesiones y limitador en memoria**, válidos solo para un proceso de uvicorn; se pierden al
  reiniciar el panel. Un atacante no puede provocar ese reinicio.
- **IP del cliente detrás de un proxy inverso.** El límite usa la IP de la conexión; con un proxy
  habría que tomarla de una cabecera de confianza.
- **Contraseña mínima de 4 caracteres** (decisión del equipo). Argon2id y el límite de intentos
  reducen el riesgo, pero es una contraseña débil si el panel se expone a Internet. Recomendación:
  usar una larga.
- **El panel funciona por HTTP en local.** Con HTTPS hay que poner `SMS_COOKIE_SECURE=true`.
- **El agente puede leer los archivos de `/hostfs` legibles por todos los usuarios.** Solo se leen
  rutas fijas (`/etc/os-release`, `/etc/hostname` y el disco), pero el montaje es amplio. Mitigado por solo lectura y no root.
- **Los contenedores comparten el kernel** con el anfitrión.
- **La red muestra el total del anfitrión**, incluidas interfaces como `tailscale0` (VPN): el tráfico físico y el de VPN se suman.
- **Bloqueo por terceros:** quien alcance el panel puede provocar 5 fallos y bloquear su IP; no el
  acceso de otras IP (el límite es por IP).

## 6.5 Reglas obligatorias del proyecto y cumplimiento

| Regla | Cumplimiento |
|---|---|
| Sin `privileged: true` | Cumplida: ningún contenedor propio lo usa |
| Sin `network_mode: host` | Cumplida: la red del anfitrión se lee de un único archivo montado en solo lectura (ADR-046) |
| Sin montar `/` del host con escritura | Cumplida: se monta en solo lectura y sin submontajes (ADR-038); los discos extra también en solo lectura |
| Sin comandos arbitrarios desde la interfaz | Cumplida: no hay `exec` ni shell |
| Sin acceso indiscriminado al socket | Solo el agente, con consultas fijas |
| No ejecutar todo como root | Ambos procesos son no root |
| Validar entradas | Esquemas de Pydantic (login) y longitud de contraseña |
| Proteger operaciones administrativas | Sesión, CSRF, límite de intentos |
| Separar componentes privilegiados | Panel / agente |
| Registrar accesos | Logger `server_monitor.access` |

## 6.6 Riesgos técnicos y del proyecto

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Afectar al servidor real durante el desarrollo | Baja | Muy alto | Desarrollo solo local; ninguna conexión al servidor sin autorización; solo lectura |
| Diferencias entre CachyOS/Docker 29 y Ubuntu | Media | Medio | Probar primero en una VM Ubuntu o con autorización antes del servidor real |
| Datos del anfitrión que no coinciden en otro sistema (p. ej. `/etc/os-release` ausente) | Baja | Bajo | El agente devuelve `null` y el panel muestra «No disponible» |
| Complejidad que el equipo no pueda defender | Baja | Alto | Código acotado (unas 2 500 líneas de `src/`, la mayor parte de interfaz), sin dependencias nuevas |
| Pendientes de verificación (`verify_dev_env.sh` con el entorno renombrado, servidor real) | Media | Medio | Reejecutar antes de dar la fase por cerrada (ver [07-pruebas.md](07-pruebas.md)) |
