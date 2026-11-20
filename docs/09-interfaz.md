# 9. Interfaz

> Estado del documento: **rediseño «Arcane» (2026-11-17)**. Describe el código de
> `src/server_monitor/panel/web/` tal como está. Lo probado en navegador figura en
> [07-pruebas.md](07-pruebas.md); las limitaciones, al final de este documento.

La interfaz es HTML, CSS y JavaScript (módulos ES) **sin framework, sin compilación y sin
librerías**. Todo se sirve desde el propio panel porque la CSP es `default-src 'self'`: no puede haber
scripts ni estilos en línea, ni atributos `style=""` en el HTML, ni recursos externos. Los estilos
dinámicos se asignan desde JavaScript (`element.style`) o con atributos SVG.

## 9.1 Decisiones de diseño

### Concepto

Un **dashboard de operaciones oscuro** con barra lateral fija y contenido en tarjetas: lo importante
(contenedores, CPU, RAM, disco, Docker e imágenes) a primera vista. La interfaz es de **solo lectura**:
no hay botones para iniciar, parar ni borrar contenedores. El acento púrpura se usa para la marca, la
navegación activa y los elementos destacados; el verde, ámbar y rojo se reservan para estados.

### Paleta (tokens en `:root` de `css/styles.css`)

| Uso | Token | Valor |
|---|---|---|
| Fondo principal | `--bg-main` | `#111113` |
| Fondo de la barra lateral | `--bg-sidebar` | `#161618` |
| Superficie de tarjetas | `--bg-card` | `#1a1a1d` |
| Superficie al pasar el ratón | `--bg-card-hover` | `#222226` |
| Píldora oscura | `--bg-pill-dark` | `#252529` |
| Bordes | `--border-subtle` / `--border-sidebar` | `#27272a` / `#262629` |
| Texto principal / secundario / atenuado | `--text-primary` / `--text-secondary` / `--text-muted` | `#f4f4f5` / `#a1a1aa` / `#71717a` |
| Acento | `--accent-purple` | `#8b5cf6` |
| Acento claro (texto) | `--accent-purple-text` | `#a78bfa` |
| Acento fuerte (hover) | `--accent-purple-strong` | `#7c3aed` |
| Fondo de acento | `--accent-purple-bg` | `rgba(139, 92, 246, 0.14)` |
| Degradado azul (Docker Engine) | `--grad-blue` | `rgba(37, 99, 235, 0.22) → #1a1a1d` |
| Degradado verde (Containers) | `--grad-green` | `rgba(16, 185, 129, 0.20) → #1a1a1d` |
| Degradado púrpura (Images) | `--grad-purple` | `rgba(139, 92, 246, 0.22) → #1a1a1d` |
| Estado correcto | `--status-green-*` | fondo `rgba(16, 185, 129, 0.15)`, texto `#34d399` |
| Aviso | `--status-amber-*` | fondo `rgba(245, 158, 11, 0.15)`, texto `#fbbf24` |
| Neutro | `--status-neutral-*` | fondo `rgba(255, 255, 255, 0.08)`, texto `#a1a1aa` |

Los degradados de las tres tarjetas de Docker van de su color a `#1a1a1d` al 75 %.

### Tipografía

**IBM Plex Sans** (400, 500 y 600) para el texto e **IBM Plex Mono** (400 y 500) para cifras,
nombres de imagen, repositorios y datos técnicos. Archivos `woff2` latinos autoalojados en `web/fonts/`
(paquetes `@fontsource/ibm-plex-sans@5.2.8` y `@fontsource/ibm-plex-mono@5.2.7`, licencia SIL OFL 1.1,
© IBM Corp.; texto en `web/fonts/OFL.txt`). Se declaran con `@font-face` y `font-display: swap`.
Las cifras usan `font-variant-numeric: tabular-nums`.

Tamaños principales: cuerpo 14 px; títulos de sección 18 px/600; valor de KPI 24 px/700; etiquetas de
la barra lateral 11 px; texto de tablas 13 px.

### Iconos y marca

Sprite `web/icons.svg` con iconos de **Lucide** (`lucide-static@1.68.0`, licencia ISC; texto en
`web/icons-LICENSE.txt`), usados con `<use href="/icons.svg#nombre">`. La interfaz usa 23 símbolos:
`layout-dashboard`, `box`, `image`, `network`, `database`, `palette`, `package`, `globe`,
`scroll-text`, `settings`, `chevrons-up-down`, `chevron-right`, `user`, `ship`, `cpu`, `memory-stick`,
`hard-drive`, `triangle-alert`, `circle-alert`, `lock-keyhole`, `server`, `layers` y `log-out`. El
sprite conserva algunos iconos sin uso de la versión anterior. Son decorativos
(`aria-hidden`): el significado siempre va en texto.

La **marca** es la letra «A» dentro de un cuadrado redondeado (`#252236`, texto `#a78bfa`) y el
`favicon.svg` reproduce el mismo motivo.

### Estructura de la pantalla

La pantalla autenticada tiene dos zonas:

1. **Barra lateral** (248 px, `#161618`, fija):
   - Marca «Arcane» y versión `v1.0.2`.
   - Selector de entorno «Local Docker» con la ruta `unix:///var/run/docker.sock`, icono púrpura y
     doble cheurón.
   - Navegación agrupada:
     - **Management**: `Dashboard` (activo), `Containers`, `Compose Projects` (no disponible),
       `Images`, `Networks` (no disponible) y `Volumes` (no disponible).
     - **Customization**: `Template Settings` y `Container Registries`, ambos no disponibles.
     - **Environments**: `Environment Management`, no disponible.
     - **Administration**: `Event Log` y `Settings` (con cheurón), ambos no disponibles.

     `Dashboard`, `Containers` e `Images` desplazan la vista a su sección y actualizan el elemento
     activo; el resto solo se muestra, sin acción.
   - Pie: estado de conexión, hora de última actualización, usuario «Administrador» y botón de cerrar
     sesión.
2. **Contenido principal** (fondo `#111113`, relleno 24 px 32 px 48 px):
   - **System Overview**: cuatro tarjetas iguales (`Running Containers`, `CPU Usage`, `Memory Usage`,
     `Disk Usage`). Cada una tiene icono circular púrpura, título, subtítulo, valor grande, barra de
     progreso centrada al 65 % del ancho y una nota inferior.
   - **Docker Details**: tres tarjetas con degradado:
     - `Docker Engine`: plataforma (`linux • arquitectura`) y versión real del servidor Docker.
     - `Containers`: insignias `total N` y `stopped N`, y `N running`.
     - `Images`: número total de imágenes.
   - **Resources**: dos paneles lado a lado:
     - `Containers`: columnas `Name`, `Image`, `State`, `Status`; cinco filas visibles y botón
       `View All →`.
     - `Images`: columnas `Repository`, `Status`, `Tag`, `Size`; cinco filas visibles, ordenadas de
       mayor a menor tamaño, y botón `View All →`.

### Estados

| Elemento | Estados |
|---|---|
| Conexión | Pendiente (`Conectando…`), correcto (`Conectado`) y errores diferenciados: `Agente sin respuesta`, `Sin conexión`, `Error al actualizar` |
| Aviso superior | Banner con el motivo y, si había datos anteriores, la hora de la última actualización correcta |
| Contenedor | `Running` (verde), `Starting` (`health: starting`, ámbar), `Unhealthy` (rojo), `Paused` y `Restarting` (ámbar), `Stopped`, `Created` y `Removing` (neutro), `Dead` (rojo) |
| Imagen | `In Use` (verde) y `Unused` (ámbar) |
| Docker Engine | Versión real; `Offline` si el agente responde pero Docker no; `—` si no hay dato |

La hora de última actualización se muestra en formato `HH:MM:SS` y tiene `title="Última actualización"`.
El estado nunca se comunica solo por color: siempre lleva texto.

### Responsive

- **≤ 1100 px**: KPIs en dos columnas; Docker Details y Resources pasan a una columna.
- **≤ 900 px**: la barra lateral deja de ser fija y pasa a una cabecera horizontal; se ocultan los
  grupos de navegación y el estado de conexión; el pie se alinea a la derecha.
- **≤ 640 px**: KPIs en una columna; se reduce el relleno; las tablas recortan textos largos con
  puntos suspensivos; se oculta el nombre de usuario.

### Accesibilidad

- Estructura con `header`, `main`, secciones con `aria-labelledby` y un `<h1>` oculto visualmente.
- Foco visible en todos los elementos interactivos (`:focus-visible`, contorno de 2 px en el acento).
- Iconos decorativos con `aria-hidden`; botones con `aria-label` cuando solo muestran un icono.
- `role="alert"` en los avisos de error y `role="status"` en la hora de actualización.
- Las barras de progreso usan `role="progressbar"` con `aria-valuemin`, `aria-valuemax` y
  `aria-valuenow`.
- `prefers-reduced-motion: reduce`: se desactivan transiciones y animaciones.

## 9.2 Módulos JavaScript (`web/js/`)

| Módulo | Líneas | Qué hace |
|---|---|---|
| `app.js` | 51 | Arranque: consulta la sesión y muestra login o panel; muestra la barra lateral solo con sesión; el 401 de cualquier llamada lleva al login |
| `api.js` | 73 | Cliente `fetch` (JSON, `credentials: same-origin`, cabecera CSRF, manejo del 401) |
| `session.js` | 37 | Estado de sesión en memoria y `load`/`login`/`logout` |
| `dom.js` | 35 | `el()` crea elementos HTML con `textContent`; `svg()` crea elementos SVG; `icon()` inserta un icono del sprite |
| `format.js` | 76 | Formato de bytes, tiempo, fechas y porcentajes |
| `views/login.js` | 65 | Pantalla de contraseña con la marca Arcane y el icono de candado |
| `views/dashboard.js` | 377 | KPIs, Docker Details, tablas de Resources y ciclo de actualización |

### `views/dashboard.js`

`render(root)` construye la pantalla y devuelve la función de parada. Componentes:
`createOverview` (cuatro KPIs), `createDockerDetails` (tres tarjetas) y `createResources` (dos tablas).
Las filas se generan con `el()` y `textContent`; nada se inserta como HTML.

- **Contenedores**: se ordenan por `created_at` descendente y se muestran cinco; `View All` amplía a
  todos y cambia a `Show Less ←`.
- **Imágenes**: el agente las devuelve ordenadas por tamaño descendente; se muestran cinco y `View All`
  amplía la lista.
- Los textos largos (imagen, repositorio, estado) se recortan con CSS y conservan el valor completo en
  `title`.

### Ciclo de actualización

El ciclo vive en `dashboard.js`: cada 5 s (`setTimeout` encadenado, sin solaparse) se consultan cuatro
rutas del panel:

- **Obligatorias**: `/api/metrics` y `/api/containers`. Si fallan, no se actualiza nada y se muestra el
  aviso; los datos anteriores permanecen visibles.
- **Opcionales**: `/api/images` y `/api/docker`. Si fallan, se ignora su resultado (`null`) y el resto
  del panel sigue funcionando.

Con la pestaña oculta (`document.hidden`) no se programa la siguiente consulta; al volver
(`visibilitychange`) se actualiza al instante y se reanuda el ciclo. Al cerrar sesión o al recibir 401
se llama a la función de parada devuelta por `render`.

## 9.3 Estado de lo implementado y probado

| Aspecto | Estado |
|---|---|
| Cuatro KPIs con los valores de la API (contenedores, CPU, RAM, disco) | **Probado** en navegador real con agente simulado |
| Tres tarjetas de Docker Details con versión, totales e imágenes | **Probado** |
| Tablas de contenedores e imágenes con cinco filas y `View All` | **Probado** |
| Actualización automática, pausa con pestaña oculta y reanudación | **Probado** |
| Sin scroll horizontal a 1024 y 390 px; sin errores de consola ni de CSP | **Probado** |
| Cerrar sesión y pérdida de sesión en el servidor | **Probado** |
| Navegación por anclas y estado activo del menú | **Implementado**; el E2E comprueba el menú, no el desplazamiento suave |
| Selector de entorno y elementos de navegación no disponibles | **Solo visual**; no abren menús ni cambian de pantalla |
| Fidelidad pixel a pixel con la imagen de referencia | **No verificada automáticamente**; el modelo de desarrollo no puede leer imágenes |
| Tema claro | **No implementado** (solo oscuro) |
| Gráficas históricas | **Eliminadas** en el rediseño; la nueva pantalla no muestra series temporales |
