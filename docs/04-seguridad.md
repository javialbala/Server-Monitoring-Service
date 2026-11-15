# 4. Seguridad y riesgos

> Estado del documento: **propuesta de la Fase 0**. Las medidas descritas son de diseño; ninguna
> está implementada ni verificada todavía.

## 4.1 Activos a proteger

1. **El servidor anfitrión** y sus servicios existentes (el activo más importante).
2. **El socket de Docker** (equivale a acceso root al host).
3. Las aplicaciones desplegadas y sus **datos persistentes**.
4. Los **secretos** de las aplicaciones (variables marcadas como secretas).
5. Las credenciales de acceso al panel.

## 4.2 Superficie de ataque y modelo de amenazas

| # | Amenaza | Vector | Mitigación de diseño |
|---|---|---|---|
| A1 | Escalada al host mediante un contenedor privilegiado | Formulario o API que permita `privileged`, montajes `/`, `cap_add`, `network_mode: host` | El esquema de `RuntimeSpec` no contiene esos campos; el agente revalida y rechaza campos desconocidos; tests específicos. |
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

## 4.3 Riesgo residual reconocido

- **El agente sigue teniendo el socket de Docker.** Si se compromete el propio agente, se compromete
  el host. Se reduce el riesgo manteniéndolo mínimo, sin puertos publicados, con sistema de archivos
  de solo lectura y sin dependencias innecesarias. Se estudiará **Docker en modo *rootless*** como
  mejora en el servidor (ver ADR-002).
- **Los contenedores comparten kernel con el host.** Es una limitación inherente a los contenedores
  frente a las máquinas virtuales; debe explicarse en la memoria.
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
| Complejidad que el equipo no pueda defender | Media | Alto | Código simple, documentación por fase, decisiones registradas. |
| Rate limit de Docker Hub al descargar imágenes | Media | Bajo | Caché local de imágenes; imágenes pequeñas en los tests. |
| Python 3.14 local frente a la imagen de producción | Baja | Bajo | Fijar la versión de Python en la imagen (3.12 o 3.13, la más reciente estable soportada por las dependencias) y probar con ella. |

## 4.5 Reglas obligatorias (del enunciado) y cómo se cumplen

| Regla | Cumplimiento previsto |
|---|---|
| Sin `privileged: true` | Ni MiniPaaS ni las apps lo usan; el esquema no lo permite. |
| Sin `network_mode: host` injustificado | No se usa. |
| Sin montar `/` del host con escritura | Ningún montaje del host salvo el socket en el agente. |
| Sin comandos arbitrarios desde la interfaz | No hay `exec` ni shell; solo operaciones de lista blanca. |
| Sin acceso indiscriminado al socket | Solo el agente, con API limitada. |
| No ejecutar todo como root | Control plane con usuario sin privilegios; agente sin root si es posible (grupo del socket). |
| Validar entradas | Esquemas Pydantic estrictos en API y agente. |
| Proteger operaciones administrativas | Autenticación + CSRF + auditoría. |
| Separar componentes privilegiados | Control plane / agente. |
| Registrar operaciones y gestionar errores | Log de auditoría + errores explícitos y comprensibles. |
