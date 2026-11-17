# 7. Pruebas

> Estado del documento: **actualizado tras simplificar el despliegue (2026-11-16)**. Contiene la
> estrategia de pruebas y el registro de las pruebas **realmente ejecutadas** en la etapa vigente. El
> registro de las Fases 0 a 2 está archivado en
> [historico/registro-pruebas-etapa-paas.md](historico/registro-pruebas-etapa-paas.md). Regla: no se
> registra como superada ninguna prueba que no se haya ejecutado, y todo lo no ejecutado figura como
> pendiente.

## 7.1 Niveles de prueba

| Nivel | Qué prueba | Herramienta | Necesita Docker | Cuándo |
|---|---|---|---|---|
| **Unitarias del agente** | Cálculo de métricas con directorios falsos (`/proc`, `/sys`, `hostfs`, `disks`, `net/dev`) y conversión de contenedores | `pytest` | No | Siempre (local y CI) |
| **API del agente** | Rutas solo `GET`, 503 sin detalles, `/metrics` con un anfitrión falso | `pytest` + `TestClient`, cliente Docker falso | No | Siempre |
| **API del panel** | Login, cookie, 429, CSRF, `Origin`, caducidad de sesión, 401, 502, cabeceras y arranque con `APP_PASSWORD` | `pytest` + `TestClient`, agente falso | No | Siempre |
| **Integración** | Agente contra Docker real: contenedor ajeno detectado, detenido incluido, métricas coherentes | `pytest -m integration` (3 tests) | Sí | Local (el CI las excluye) |
| **Extremo a extremo** | Sistema completo en un proyecto Compose aparte (`sms-e2e`): contraseña, aislamiento, métricas frente al anfitrión, contenedores, solo lectura, sesión, bloqueo | `bash scripts/e2e_monitor.sh` (46 comprobaciones) | Sí | Local |
| **Navegador** | Recorrido del panel real con Chromium: indicadores frente a la API, gráficas, tooltip, pausa, responsive, logout, consola | `scripts/e2e_ui.py` con Playwright vía `uvx` (22 comprobaciones) | Sí | Local |
| **Estilo y sintaxis** | Formato, errores comunes y reglas de seguridad (`S`); sintaxis de los módulos JavaScript | `ruff check`, `ruff format --check`, `node --check` | No | Siempre |

No hay pruebas automáticas del JavaScript aparte de `node --check` (sintaxis) y el recorrido en
navegador: la lógica de `history.js` y de `format.js` se ejercita solo a través de él.

## 7.2 Cómo se prueba cada parte

| Parte | Pruebas clave |
|---|---|
| Métricas | CPU con dos lecturas falsas (incluido sin cambios → 0 %), RAM, disco con `statvfs`, uptime, modelo ausente, `os-release` en `/etc` o `/usr/lib` |
| Discos | El raíz más los extra ordenados por nombre; omitido el que está en el mismo `st_dev`; sin directorio `/disks`, solo el raíz |
| Temperatura | `coretemp` usa «Package id 0» y no los núcleos; `k10temp` con «Tctl» y sin etiquetas; alternativa `x86_pkg_temp`; sin sensores → `null`; valores absurdos descartados |
| Red | Suma de interfaces reales, sin `lo`, `veth*`, `br-*`, `docker*`, `virbr*`; archivo ilegible → `null` |
| Contenedores | Conversión de puertos, nombre sin barra, ordenación (en ejecución primero, luego por nombre), detenidos incluidos, salud deducida del texto, etiquetas de Compose, una sola llamada de lectura |
| Solo lectura | Todas las rutas del agente son `GET`; sin `/docs`; el cliente falso solo admite lo previsto; en el E2E, `docker events` no registra eventos de modificación |
| Autenticación | Contraseña correcta/incorrecta, 5 fallos → 429 incluso con la contraseña correcta, cookie `HttpOnly`/`SameSite=Strict`, caducidad por inactividad y absoluta |
| CSRF | Logout sin token → 403, `Origin` ajeno → 403 |
| `APP_PASSWORD` | Ausente, vacía, corta o larga → el arranque sale con `SystemExit(1)` sin escribir la contraseña en el log (`caplog`); login 204 con la configurada y 401 con otra. En el E2E: sin contraseña el panel sale con código 1 y lo explica sin traceback; la contraseña no está en los logs; cambiarla y ejecutar `up -d` da 204 con la nueva y 401 con la antigua |
| Aislamiento | En el E2E: el agente responde solo desde la red interna, no desde el anfitrión y sin salida a Internet; el panel no tiene el socket; ningún contenedor corre como root; raíz de solo lectura; `/hostfs` de solo lectura y sin submontajes |
| Navegador | Número y arco de los indicadores = API, un indicador por disco, una temperatura, filas = contenedores, detenidos marcados, sin botones de modificación, ≥ 3 muestras en gráficas, tooltip, pausa, sin scroll horizontal, logout, sin errores de consola/CSP |

## 7.3 Reglas de las pruebas con Docker

- Solo contra el **Docker local**, nunca contra el servidor real.
- Los proyectos Compose de prueba (`sms-e2e` y el de la prueba de navegador) son distintos del que usa
  quien instala el servicio (`server-monitoring`) y se eliminan al terminar.
- Los contenedores de prueba son pequeños y llevan una etiqueta propia; se eliminan al terminar.

## 7.4 Pruebas implementadas

| Ubicación | Qué cubre |
|---|---|
| `tests/agent/test_host_metrics.py` | Funciones de lectura de `/proc`, `/sys`, `hostfs`, discos, temperatura y red |
| `tests/agent/test_containers.py` | Conversión de los datos de Docker, orden, salud |
| `tests/agent/test_agent_api.py` | Rutas, métricas con anfitrión falso, 503 |
| `tests/agent/test_agent_docker_integration.py` | 3 tests con Docker real (marcador `integration`) |
| `tests/panel/test_auth.py` | Login, 429, CSRF, `Origin`, sesiones, limitador |
| `tests/panel/test_startup.py` | Arranque con `APP_PASSWORD` inválida (sin escribirla en el log) y login con la configurada |
| `tests/panel/test_api.py` | Rutas protegidas, reenvío al agente, 502, estáticos con CSP |
| `scripts/e2e_monitor.sh` | 46 comprobaciones de extremo a extremo (incluye contraseña y aislamiento) |
| `scripts/e2e_ui.py` | 22 comprobaciones en navegador |

## 7.5 Integración continua

El *workflow* de GitHub Actions ejecuta la sincronización de `deploy/requirements` con `uv.lock`,
`ruff check`, `ruff format --check` y `pytest -m "not integration" --cov=server_monitor`; **excluye** las
pruebas de integración y no ejecuta el E2E ni la prueba de navegador. **No se ha ejecutado el CI en
GitHub** para esta rama (no se ha hecho *push*).

## 7.6 Registro de la simplificación del despliegue (2026-11-16)

Entorno: máquina local CachyOS, Docker 29.9.2, Compose 5.6.1, rama `rediseno-interfaz-limpieza`.
**No se usó el servidor Ubuntu real.**

| # | Prueba | Comando | Resultado real |
|---|---|---|---|
| S.1 | Lint | `uv run ruff check .` | Sin errores |
| S.2 | Formato | `uv run ruff format --check .` | 55 archivos ya formateados |
| S.3 | Suite completa | `uv run pytest -q` | **51 passed**, 1 aviso (deprecación de httpx en el `TestClient` de Starlette; no es un fallo) |
| S.4 | Validez del Compose | `docker compose config -q` | Válido |
| S.5 | Extremo a extremo con Docker real | `bash scripts/e2e_monitor.sh` | **46 OK**, «E2E correcto.» |
| S.6 | Recorrido en navegador | `scripts/e2e_ui.py` en un proyecto Compose aislado | **22 OK**, «UI correcta.» |

El script del E2E usa un archivo *override* temporal con `!override` (requiere Compose 2.24 o superior)
para fijar la contraseña de prueba, un puerto local y el GID del socket sin tocar `docker-compose.yml`.

**Qué comprueba el E2E (46):** sin contraseña el panel sale con código 1 y lo explica sin traceback; la
contraseña no aparece en los logs; cambiar `APP_PASSWORD` y ejecutar `up -d` da 204 con la nueva y 401
con la antigua; el agente responde solo desde la red interna, no desde el anfitrión y sin salida a
Internet; el panel no tiene el socket; ningún contenedor corre como root; raíz de solo lectura; `/hostfs`
de solo lectura y sin submontajes; métricas iguales a las del anfitrión (CPU, RAM, uptime, *hostname* y
SO, disco raíz, red sin `lo`/`veth`/`docker`, temperatura); contenedores ajenos detectados, incluidos los
detenidos y con el mismo número que `docker ps -a`; sesión y CSRF; 429 tras 5 fallos incluso con la
contraseña correcta; las consultas no generan eventos de modificación en `docker events`.

**Qué comprueba el navegador (22):** error con contraseña incorrecta; número y arco de CPU y RAM iguales
a los de la API; un indicador por disco; una sola temperatura general; filas de contenedores iguales a
la API y detenidos marcados; sin botones de modificación; la hora de actualización cambia sola; al menos
3 muestras en las gráficas; tooltip; pausa con la pestaña oculta (se **simula** con `visibilitychange`);
sin scroll horizontal a 1024 y 390 px; logout; sin errores de JavaScript ni de CSP en la consola.

### Pendiente de ejecutar o de comprobar

| Pendiente | Motivo |
|---|---|
| Servidor Ubuntu real (instalación siguiendo el README) | Sin autorización; solo se probó en CachyOS |
| CI en GitHub | Sin *push* |
| Desplazamiento de la gráfica con la ventana de 10 min llena | Requiere 10 min reales en el navegador |
| Tooltip en pantalla táctil | No probado |
| Consumo de memoria y CPU; contraste y daltonismo automatizados | No medidos |

## 7.7 Registros anteriores

Las cifras de etapas anteriores (renovación: 48 tests, E2E de 29 y navegador de 11 comprobaciones;
rediseño con token y archivo de hash: 68 tests y E2E de 46) corresponden a versiones del código que ya
no existen y no deben compararse con las actuales. Están en el
[informe de la renovación](historico/renovacion-monitorizacion.md).

## 7.8 No probado

- El servidor Ubuntu real (la autorización no se ha pedido ni dado).
- Consumo de memoria y CPU de los contenedores; carga con muchos contenedores.
- Discos extra reales montados en `/disks/*` y sensores `k10temp` (AMD) o `x86_pkg_temp`: solo con
  directorios falsos.
- La presentación en navegador de los estados «Con fallos» y «Arrancando» y del aviso de fallo del agente.
