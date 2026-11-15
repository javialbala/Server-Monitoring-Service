# 4. Seguridad y riesgos

> Estado del documento: **aprobado por el equipo (2026-11-15)**. Las medidas descritas son de
> diseño; ninguna está implementada ni verificada todavía.

## 4.1 Activos a proteger

1. **El servidor anfitrión** y sus servicios existentes (el activo más importante).
2. **El socket de Docker** (equivale a acceso root al host).
3. Las aplicaciones desplegadas y sus **datos persistentes**.
4. Los **secretos** de las aplicaciones (variables marcadas como secretas).
5. Las credenciales de acceso al panel.

## 4.2 Superficie de ataque y modelo de amenazas

| # | Amenaza | Vector | Mitigación de diseño |
|---|---|---|---|
| A1 | Escalada al host mediante un contenedor privilegiado | Formulario o API que permita `privileged`, montajes `/`, `cap_add`, `network_mode: host` | El agente nunca recibe parámetros de Docker: recibe una `ServiceRequest` de alto nivel y construye él mismo la configuración con valores seguros fijos; rechaza campos desconocidos; tests específicos (ADR-002). |
| A2 | Acceso al socket de Docker desde el componente expuesto | Vulnerabilidad en el control plane | Solo el agente monta el socket; el control plane no lo tiene; agente sin puertos expuestos en una red `internal`. |
| A3 | MiniPaaS afecta a servicios existentes del servidor | Error de programación o petición manipulada que actúe sobre otros contenedores | Etiqueta `minipaas.managed=true` comprobada en el agente en cada operación; nombres con prefijo; rango de puertos reservado. |
| A4 | Acceso no autorizado al panel | Sin autenticación, fuerza bruta, robo de sesión | Login obligatorio, hash Argon2/bcrypt, limitación de intentos, cookie `HttpOnly`+`SameSite=Strict`, caducidad de sesión. |
| A5 | CSRF desde otra web | Navegador del administrador autenticado | `SameSite=Strict` + token CSRF en peticiones que modifican estado. |
| A6 | XSS en el panel | Nombres, logs o variables con HTML/JS | Escapar siempre en el frontend (`textContent`, nunca `innerHTML` con datos); cabecera CSP restrictiva. |
| A7 | Inyección de comandos | Construir comandos de shell con datos del usuario | No se ejecutan comandos de shell: se usa la API de Docker (SDK). No hay operación `exec`. |
| A8 | Path traversal / montaje de rutas del host | Campo «ruta del volumen» manipulado | Solo volúmenes con nombre; la ruta del contenedor se valida (absoluta, sin `..`, fuera de rutas del sistema como `/proc`). |
| A9 | Agotamiento de recursos (DoS local) | Aplicación sin límites que consume toda la RAM/CPU | Límites obligatorios por servicio y cuota global (Fase 9). |
| A10 | Fuga de secretos | Mostrar variables secretas en API, logs o auditoría | La API nunca devuelve secretos; el log de auditoría registra *qué* cambió, no los valores. |
| A11 | Imágenes maliciosas | El usuario despliega una imagen comprometida | Fuera del control técnico total. Mitigaciones: contenedores sin privilegios, aislados en su red, con límites; lista de registros permitidos configurable; aviso en la documentación. |
| A12 | Token del agente filtrado | Lectura de la configuración | Token generado en la instalación, fuera del repositorio, y el agente sigue aplicando su política aunque la petición venga autenticada. |
| A13 | Exposición del panel a Internet | Publicar el puerto del panel sin protección | Por defecto escucha solo en `127.0.0.1` o la LAN; HTTPS mediante proxy si se expone (Fase 13). |

### Estado de las mitigaciones tras la Fase 2

| # | Estado | Cómo se ha implementado y verificado |
|---|---|---|
| A2 | Implementado y verificado (Fase 1) | El control plane no tiene el socket; `verify_dev_env.sh` lo comprueba |
| A4 | **Implementado y verificado** | Login obligatorio en todas las rutas privadas; Argon2id (ADR-019); 5 fallos en 15 min → 429 (ADR-024); cookie `HttpOnly`, `SameSite=Strict`; identificador guardado como SHA-256; caducidad de 30 min de inactividad y 8 h absolutas; revocación al cerrar sesión; identificador nuevo en cada login (ADR-018). Tests en `tests/api/test_auth_api.py` y E2E |
| A5 | **Implementado y verificado** | Token sincronizador por sesión en `X-CSRF-Token` y rechazo de `Origin` ajeno (ADR-021). Tests en `tests/api/test_csrf_api.py` y E2E |
| A6 | **Implementado y verificado** (frontend) | Datos dinámicos solo con `textContent`/`createElement`; sin `innerHTML`; CSP `default-src 'self'` (comprobado: la CSP bloquea incluso la evaluación de código de la herramienta de pruebas del navegador); `/docs` y `/redoc` desactivados por depender de un CDN |
| A10 | **Implementado y verificado** (auditoría) | Los metadatos de auditoría rechazan claves sensibles; los fallos de login no guardan el usuario escrito; las modificaciones guardan nombres de campo, no valores. Un test recorre todos los eventos y comprueba que no contienen contraseña, cookie ni token CSRF |
| A13 | Implementado en desarrollo | Panel solo en `127.0.0.1`; `MINIPAAS_COOKIE_SECURE=true` disponible para HTTPS. La exposición real se decidirá en la Fase 13 |

## 4.3 Riesgo residual reconocido

- **El agente sigue teniendo el socket de Docker.** Si se compromete el propio agente, se compromete
  el host. Se reduce el riesgo manteniéndolo mínimo, sin puertos publicados, con sistema de archivos
  de solo lectura y sin dependencias innecesarias. Se estudiará **Docker en modo *rootless*** como
  mejora en el servidor (ver ADR-002).
- **Los contenedores comparten kernel con el host.** Es una limitación inherente a los contenedores
  frente a las máquinas virtuales; debe explicarse en la memoria.
- **Bloqueo del administrador por terceros (Fase 2).** El límite de intentos también cuenta por
  nombre de usuario: alguien con acceso a la red del panel puede provocar 5 fallos con el usuario
  `admin` y bloquear su acceso durante 15 minutos. Es el precio de frenar ataques distribuidos desde
  varias IP; el panel solo es accesible desde la máquina o la red local, y un reinicio del control
  plane desbloquea. Se revisará si el panel se expone a Internet.
- **IP del cliente detrás de un proxy (Fase 2).** El límite por IP y la auditoría usan la IP de la
  conexión. Si en la Fase 13 se añade un proxy inverso, todas las peticiones parecerán venir del proxy
  y habrá que tomar la IP de una cabecera de confianza.
- **Contenido de la base de datos (Fase 2).** El archivo SQLite contiene el hash Argon2id de la
  contraseña y los tokens CSRF de las sesiones (los identificadores de sesión, solo como SHA-256).
  Está en un volumen accesible únicamente desde el contenedor del control plane y por root en el host;
  no se cifra en reposo.
- **Los volúmenes locales de Docker no tienen cuota de tamaño.** Una aplicación podría llenar el
  disco. Se mostrará el uso por volumen y se alertará; la cuota estricta queda fuera del alcance.

## 4.4 Riesgos técnicos y del proyecto

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Afectar al servidor real durante el desarrollo | Baja | Muy alto | Desarrollo solo local; ninguna conexión al servidor sin autorización; etiquetas `managed`. |
| Conflicto de puertos con servicios existentes del servidor | Media | Alto | Rango de puertos reservado y configurable; comprobación previa; inventario de puertos del servidor antes de la Fase 13. |
| Diferencias entre el entorno local (CachyOS, Docker 29) y el servidor (Ubuntu, versión desconocida) | Media | Medio | Ejecutar todo en contenedores; fijar versiones de imágenes base; prueba en VM Ubuntu antes de la Fase 13. |
| Hardware limitado del servidor | Media | Medio | Presupuesto de memoria (RNF-07), sin componentes pesados, muestreo de métricas moderado. |
| Alcance excesivo para el tiempo disponible | Alta | Alto | Prioridades MoSCoW; núcleo funcional primero; los «C» solo si sobra tiempo. |
| Expectativa errónea de que un *rollback* recupera los datos | Media | Alto | El *rollback* se define como recuperación de la versión de la aplicación, no de los datos (ADR-011); advertencia en el panel antes de confirmar; documentado en la guía de uso. |
| Complejidad que el equipo no pueda defender | Media | Alto | Código simple, documentación por fase, decisiones registradas. |
| Rate limit de Docker Hub al descargar imágenes | Media | Bajo | Caché local de imágenes; imágenes pequeñas en los tests. |
| Python 3.14 local frente a la imagen de producción | Baja | Bajo | Fijar la versión de Python en la imagen (3.12 o 3.13, la más reciente estable soportada por las dependencias) y probar con ella. |

## 4.5 Reglas obligatorias (del enunciado) y cómo se cumplen

| Regla | Cumplimiento previsto |
|---|---|
| Sin `privileged: true` | Ni MiniPaaS ni las apps lo usan; el agente construye la configuración y no acepta parámetros de Docker. |
| Sin `network_mode: host` injustificado | No se usa. |
| Sin montar `/` del host con escritura | Ningún montaje del host salvo el socket en el agente. |
| Sin comandos arbitrarios desde la interfaz | No hay `exec` ni shell; solo operaciones de lista blanca. |
| Sin acceso indiscriminado al socket | Solo el agente, con API limitada. |
| No ejecutar todo como root | Control plane con usuario sin privilegios; agente sin root si es posible (grupo del socket). |
| Validar entradas | Esquemas Pydantic estrictos en API y agente. |
| Proteger operaciones administrativas | Autenticación + CSRF + auditoría. |
| Separar componentes privilegiados | Control plane / agente. |
| Registrar operaciones y gestionar errores | Log de auditoría + errores explícitos y comprensibles. |
