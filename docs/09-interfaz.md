# 9. Interfaz

> Estado del documento: **nuevo en la fase de rediseño de interfaz y limpieza (2026-11-16)**. Describe
> el código de `src/server_monitor/panel/web/` tal como está. Lo que se ha probado en navegador
> real figura en [07-pruebas.md](07-pruebas.md); las limitaciones, al final de este documento.

La interfaz es HTML, CSS y JavaScript (módulos ES) **sin framework, sin compilación y sin
librerías**. Todo se sirve desde el propio panel porque la CSP es `default-src 'self'`: no puede haber
scripts ni estilos en línea, ni atributos `style=""` en el HTML, ni recursos externos. Los estilos
dinámicos se asignan desde JavaScript (`element.style`) o con atributos SVG.

## 9.1 Decisiones de diseño

### Concepto

Un tema **oscuro y sobrio**, de panel de operaciones: lo importante (CPU, RAM, discos, contenedores) a
primera vista; el color solo para el **estado** (normal, alto, crítico, detenido) y siempre
acompañado de texto, nunca como único indicador.

### Paleta (tokens en `:root` de `css/styles.css`)

| Uso | Token | Valor |
|---|---|---|
| Fondo | `--bg` | `#0e1115` |
| Superficie (tarjetas) | `--surface` | `#151920` |
| Superficie elevada | `--surface-2` | `#1b2028` |
| Línea | `--line` / `--line-strong` | `#252b34` / `#343c48` |
| Texto principal / secundario / atenuado | `--text` / `--text-2` / `--muted` | `#e6e9ee` / `#b0b8c4` / `#8c95a2` |
| Acento (enlaces, foco, marca) | `--accent` | `#7aaef7` |
| Estado correcto | `--ok` | `#3fb97a` |
| Aviso | `--warn` | `#e2a93b` |
| Crítico | `--crit` | `#f0645f` |
| Detenido | `--stopped` | `#6b7480` |
| Serie CPU / RAM | `--s-cpu` / `--s-ram` | `#3b8beb` / `#d6578a` |
| Serie bajada / subida | `--s-rx` / `--s-tx` | `#1fa2ae` / `#9085e9` |
| Discos | `--s-disk` | `#a3afbf` |

Los colores se eligieron con contraste AA sobre las superficies y de forma que las parejas de series
(CPU/RAM y bajada/subida) se distingan también con daltonismo. Esa validación se hizo al diseñarlos;
no forma parte de la batería automática de pruebas.

### Tipografía

**IBM Plex Sans** (pesos 400, 500 y 600) para el texto e **IBM Plex Mono** (400 y 500) para cifras,
nombres de imagen, hostname y ejes. Archivos `woff2` latinos, autoalojados en `web/fonts/` (paquetes
`@fontsource/ibm-plex-sans@5.2.8` y `@fontsource/ibm-plex-mono@5.2.7`, licencia SIL OFL 1.1, © IBM
Corp.; texto en `web/fonts/OFL.txt`). Se declaran con `@font-face` y `font-display: swap`, y se precargan
dos en `index.html`. Las cifras usan `font-variant-numeric: tabular-nums` para que no «bailen» al
actualizarse.

### Iconos y marca

14 iconos de **Lucide** (`lucide-static@1.68.0`, licencia ISC; texto en `web/icons-LICENSE.txt`)
agrupados en un *sprite* `web/icons.svg` y usados con `<use href="/icons.svg#nombre">`: `server`,
`cpu`, `memory-stick`, `hard-drive`, `thermometer`, `clock`, `arrow-down`, `arrow-up`, `layers`,
`log-out`, `lock-keyhole`, `triangle-alert`, `monitor` y `circle-alert` (más la marca: 15 símbolos en
total; en la limpieza se quitaron cuatro sin uso). Son decorativos (`aria-hidden`): el significado siempre va en texto. La **marca** es
propia (símbolo `logo` del sprite): un arco de 270° con un punto central, que repite el indicador
circular; el mismo dibujo es el `favicon.svg`.

### Estructura de la pantalla (de arriba abajo)

1. **Cabecera**: marca, nombre del producto y *hostname*; a la derecha, estado de la conexión
   (Conectado / Agente sin respuesta / Sin conexión con el panel / Error al actualizar), hora de la última
   actualización y botón «Cerrar sesión».
2. **Indicadores**: CPU, Memoria RAM y **un indicador por disco**. Cada uno es un círculo de 270° con el
   porcentaje y una lista de datos (núcleos y modelo; usada, disponible y total; usado, libre y total).
3. **Evolución**: una gráfica con CPU y RAM, y otra con la velocidad de red (bajada y subida).
4. **Sistema**: *hostname*, sistema operativo, kernel, arquitectura, tiempo encendido y **temperatura
   general** («No disponible» si el agente no tiene sensor del paquete del procesador).
5. **Contenedores**: tabla con nombre (y servicio de Compose si difiere), estado, imagen, puertos,
   proyecto de Compose y fecha de creación. Cabecera con el resumen («N en ejecución · M detenidos · K con
   fallos»). Sin ningún botón de modificación.

El ancho máximo del contenido es 1440 px.

### Estados

| Elemento | Estados |
|---|---|
| Indicador / temperatura | Normal, **Alto** (ámbar) y **Crítico** (rojo); el estado se escribe también en texto en el indicador («Alto», «Crítico») |
| Contenedor | **En ejecución** (verde), **Arrancando** (`health: starting`, ámbar), **Con fallos** (`unhealthy`, rojo), **En pausa** y **Reiniciando** (ámbar), **Detenido**, **Creado** y **Eliminándose** (gris), **Muerto** (rojo). Debajo se muestra el texto original de Docker |
| Conexión | Pendiente, Conectado, y tres errores diferenciados |
| Gráfica de red | Se oculta si el agente devuelve `network: null` |

### Umbrales

Definidos en `THRESHOLDS` y `TEMP_THRESHOLDS` de `js/views/dashboard.js`. Son una **decisión de diseño**,
no un requisito:

| Magnitud | Alto (ámbar) a partir de | Crítico (rojo) a partir de |
|---|---|---|
| CPU | 75 % | 90 % |
| RAM | 80 % | 90 % |
| Disco | 80 % | 90 % |
| Temperatura | 75 °C | 90 °C |

### Responsive

Rejilla fluida con puntos de corte: ≥ 700 px, indicadores en dos columnas; ≥ 1100 px, las dos gráficas
lado a lado; ≥ 1200 px, tres o cuatro indicadores en una fila y seis datos de sistema en una fila.
Hasta 1279 px la tabla reduce el relleno y permite partir textos para no desbordar. **Hasta 760 px (móvil)**
la cabecera deja de ser fija, el botón de cerrar sesión se queda en solo icono y la tabla de contenedores
pasa a **fichas**: cada fila es una tarjeta con sus etiquetas (`data-label`). En 420 px o menos se oculta el
nombre del servidor y se reducen los indicadores.

### Accesibilidad

- Estructura con `header`, `main`, secciones con `aria-labelledby` y `<h1>` oculto visualmente.
- Foco visible en todos los elementos interactivos (`:focus-visible`, contorno de 2 px en el acento).
- Estado nunca solo por color: siempre hay texto («Alto», «Crítico», «Detenido»...).
- Las gráficas son `role="img"` con `aria-label` descriptivo; la última cifra de cada serie está en la
  leyenda como texto.
- `role="alert"` en los avisos de error y `role="status"` en la hora de actualización.
- `prefers-reduced-motion: reduce`: se desactivan transiciones y animaciones (CSS) y el desplazamiento
  animado de la gráfica (JS).

## 9.2 Módulos JavaScript (`web/js/`)

| Módulo | Líneas | Qué hace |
|---|---|---|
| `app.js` | 50 | Arranque: consulta la sesión y muestra login o panel (y la cabecera solo en el panel); el 401 de cualquier llamada lleva al login |
| `api.js` | 73 | Cliente `fetch` (JSON, `credentials: same-origin`, cabecera CSRF, manejo del 401) |
| `session.js` | 37 | Estado de sesión en memoria y `load`/`login`/`logout` |
| `dom.js` | 35 | `el()` crea elementos HTML con `textContent`; `svg()` crea elementos SVG; `icon()` inserta un icono del sprite |
| `format.js` | 76 | Formato de bytes (KiB, MiB...), velocidad, porcentaje, tiempo encendido, fechas, y **agrupación de puertos IPv4/IPv6** |
| `history.js` | 38 | Histórico en memoria y cálculo de la velocidad de red |
| `charts.js` | 198 | `createGauge` (indicador circular) y `createLineChart` (gráfica de líneas) |
| `views/login.js` | 63 | Pantalla de contraseña con la marca y el icono de candado |
| `views/dashboard.js` | 356 | Pantalla del panel y ciclo de actualización |

### `history.js`

`createHistory()` devuelve `{ samples, add }`. `add(metrics)` interpreta `collected_at` y descarta una
muestra repetida o más antigua. Guarda `{ t, cpu, ram, rx, tx }` con `t` en milisegundos. Mantiene como
máximo **120 muestras** y descarta las de más de 10 minutos (`WINDOW_MS`). **Velocidad de red:** el agente
envía contadores acumulados; la velocidad es `Δbytes / Δsegundos` entre la muestra actual y la anterior
(`rx = (rx_bytes − rx_anterior) / (t − t_anterior)`, igual para `tx`). Si un contador **baja** (reinicio del
servidor) o no hay muestra anterior, el valor es `null` y la gráfica deja un hueco: no se inventan datos.

### `charts.js`

- **Indicador circular (`createGauge`).** Un `<circle>` con `stroke-dasharray`: el arco máximo es el 75 %
  de la circunferencia (270°) y el trazo visible mide `arco × porcentaje`. Se gira 135° para que la
  abertura quede abajo. El color del arco sale del CSS según `data-tone` (normal, alto, crítico). El valor
  se anima con una transición de CSS.
- **Gráfica de líneas (`createLineChart`).** SVG con ejes, rejilla, marcas de tiempo «redondas» (10 s, 15 s,
  30 s, 1 min... separadas al menos 70 px) y un punto en el último valor. El eje de tiempo **empieza en la
  primera muestra, crece de 1 a 10 minutos y, cuando la ventana se llena, se desplaza** (las muestras
  nuevas entran por la derecha). Cortes: si entre dos muestras hay más de 15 s (p. ej. pestaña oculta) o un
  valor `null`, la línea se interrumpe. El eje Y es fijo 0–100 % para CPU/RAM y automático «redondo» para
  la red. El **tooltip** sigue al puntero (evento `pointermove`) y muestra, de la muestra más cercana, la
  hora y el valor de cada serie con una línea guía vertical. Se redibuja al cambiar el ancho
  (`ResizeObserver`).

### `views/dashboard.js`

`render(root)` construye la pantalla y devuelve la función de parada. Componentes: `createResources`
(indicadores; si cambia la lista de discos se rehacen las celdas, si no solo se actualizan),
`createCharts` (gráficas y leyendas con el valor actual), `createSystem` (datos del sistema y
temperatura) y `createContainers` (tabla). Las filas de contenedores se generan con `el()` y
`textContent`; nada se inserta como HTML. Los puertos se agrupan con `formatPorts`: el mismo puerto en
`0.0.0.0` y `::` se muestra una vez (`5432 → 5432/tcp`); si se publica solo en una IP, se indica
(`127.0.0.1:8080 → 80/tcp`); los no publicados no se listan («Sin publicar»).

El ciclo de actualización (cada 5 s, `setTimeout` encadenado, pausa con la pestaña oculta, parada al
cerrar sesión) está en [04-backend.md](04-backend.md), apartado 4.5.

## 9.3 Estado de lo implementado y probado

| Aspecto | Estado |
|---|---|
| Número y arco de CPU, RAM y discos iguales a los de la API | **Probado** en navegador real (`e2e_ui.py`) |
| Un indicador por disco; una sola temperatura | **Probado** |
| Filas de la tabla = contenedores de la API; detenidos marcados; sin botones de modificación | **Probado** |
| Actualización automática, al menos 3 muestras reales en las gráficas, líneas dibujadas | **Probado** |
| Tooltip con el ratón | **Probado** (aparece al pasar el cursor) |
| Pausa con pestaña oculta y reanudación | **Probado** (simulando `visibilitychange`: Chromium sin interfaz no oculta pestañas) |
| Sin scroll horizontal a 1024 y 390 px; sin errores de consola ni de CSP | **Probado** |
| Cerrar sesión | **Probado** |
| Desplazamiento de la gráfica con la ventana de 10 min llena | **Implementado**, **no probado** (requiere 10 min reales) |
| Tooltip con pantalla táctil | **Implementado** (eventos de puntero), **no probado** |
| Tooltip con teclado | **No implementado** (los valores actuales están en la leyenda) |
| Tema claro | **No implementado** (solo oscuro) |
| Umbrales | **Implementados**; valores elegidos sin requisito |
| Contraste AA y daltonismo de la paleta | Validado al diseñar; **no verificado** automáticamente |
