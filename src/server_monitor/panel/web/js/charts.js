// Indicador circular y gráfica de líneas en SVG, sin librerías.

import { el, svg } from "./dom.js";
import { formatClock, formatTime } from "./format.js";
import { WINDOW_MS } from "./history.js";

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// Arco de 270° con un <circle> de trazo discontinuo: stroke-dasharray="L C" dibuja L y deja
// hueco hasta la circunferencia C. El giro de 135° pone el inicio abajo a la izquierda y el
// CSS anima el cambio de L.
const R = 52;
const CIRCUMFERENCE = 2 * Math.PI * R;
const ARC = CIRCUMFERENCE * 0.75;

export function createGauge() {
  const ring = (className) => svg("circle", {
    class: className, cx: 60, cy: 60, r: R, transform: "rotate(135 60 60)",
    "stroke-dasharray": `${ARC} ${CIRCUMFERENCE}`,
  });
  const track = ring("gauge-track");
  const value = ring("gauge-value");
  value.setAttribute("stroke-dasharray", `0 ${CIRCUMFERENCE}`);
  const number = svg("tspan", { class: "gauge-number" });
  const unit = svg("tspan", { class: "gauge-unit", dx: 2 });
  unit.textContent = "%";
  const text = svg("text", { x: 60, y: 66, "text-anchor": "middle" }, number, unit);
  const root = svg("svg", { class: "gauge", viewBox: "0 0 120 120", "aria-hidden": "true" }, track, value, text);

  function update(percent, tone) {
    const p = Math.min(100, Math.max(0, percent)) / 100;
    value.setAttribute("stroke-dasharray", `${(ARC * p).toFixed(2)} ${CIRCUMFERENCE}`);
    number.textContent = percent.toFixed(1);
    root.dataset.tone = tone;
  }

  return { root, update };
}

// Gráfica de líneas. El eje X empieza en la primera muestra, se ensancha (mínimo 1 minuto)
// hasta 10 minutos y entonces se desplaza. series: [{ key, label }] (el color sale de .s-<key>);
// yMax fijo o null para calcularlo con los datos.
const MARGIN = { top: 14, right: 14, bottom: 26, left: 64 };
const GAP_MS = 15000; // más de 15 s sin muestras (p. ej. pestaña oculta) corta la línea
const MIN_SPAN_MS = 60000;
const TIME_STEPS = [10, 15, 30, 60, 120, 300].map((s) => s * 1000);
let clipCounter = 0;

export function createLineChart({ series, height = 210, yMax = null, formatValue, formatAxis, label }) {
  const clipId = `chart-clip-${++clipCounter}`;
  const chartSvg = svg("svg", { class: "chart-svg", role: "img", "aria-label": label });
  const tooltip = el("div", { className: "chart-tooltip", attrs: { "aria-hidden": "true" } });
  tooltip.hidden = true;
  const empty = el("p", { className: "chart-empty", text: "Esperando muestras…" });
  const root = el("div", { className: "chart" }, chartSvg, tooltip, empty);

  let samples = [];
  let lastEnd = null; // fin del eje del dibujo anterior, para animar el desplazamiento
  let hoverX = null;
  let geometry = null; // escalas del último dibujo, para el tooltip

  function draw(animate) {
    const width = root.clientWidth;
    if (!width) return;
    const plotW = width - MARGIN.left - MARGIN.right;
    const plotH = height - MARGIN.top - MARGIN.bottom;
    chartSvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    chartSvg.setAttribute("height", height);
    empty.hidden = samples.length > 0;

    const first = samples.length ? samples[0].t : Date.now();
    const lastT = samples.length ? samples[samples.length - 1].t : first;
    const span = Math.min(WINDOW_MS, Math.max(MIN_SPAN_MS, lastT - first));
    const start = lastT - first >= MIN_SPAN_MS ? lastT - span : first;
    const end = start + span;
    const scrolling = span === WINDOW_MS;
    const top = yMax ?? niceMax(maxValue(samples, series));
    const x = (t) => MARGIN.left + ((t - start) / span) * plotW;
    const y = (v) => MARGIN.top + plotH - (v / top) * plotH;
    geometry = { x, y, plotW, plotH };

    const nodes = [];
    for (let i = 0; i <= 4; i += 1) {
      const value = (top / 4) * i;
      const gy = Math.round(y(value)) + 0.5;
      nodes.push(svg("line", { class: i === 0 ? "axis-base" : "grid", x1: MARGIN.left, x2: width - MARGIN.right, y1: gy, y2: gy }));
      const tick = svg("text", { class: "axis-label", x: MARGIN.left - 10, y: gy + 4, "text-anchor": "end" });
      tick.textContent = formatAxis(value);
      nodes.push(tick);
    }
    // Marcas del eje X en instantes redondos, separadas al menos 70 px.
    const step = TIME_STEPS.find((ms) => (ms / span) * plotW >= 70) ?? WINDOW_MS;
    const tickText = step < 60000 ? formatTime : formatClock;
    for (let t = Math.ceil(start / step) * step; t <= end; t += step) {
      const gx = x(t);
      if (gx < MARGIN.left + 16 || gx > width - MARGIN.right - 16) continue;
      nodes.push(svg("line", { class: "tick", x1: gx, x2: gx, y1: MARGIN.top + plotH, y2: MARGIN.top + plotH + 4 }));
      const tick = svg("text", { class: "axis-label", x: gx, y: height - 6, "text-anchor": "middle" });
      tick.textContent = tickText(t);
      nodes.push(tick);
    }

    const plot = svg("g", { "clip-path": `url(#${clipId})` });
    for (const s of series) {
      plot.append(svg("path", { class: `line s-${s.key}`, d: linePath(samples, s.key, x, y) }));
      const last = samples[samples.length - 1];
      if (last && typeof last[s.key] === "number") {
        plot.append(svg("circle", { class: `end-dot s-${s.key}`, cx: x(last.t), cy: y(last[s.key]), r: 3.5 }));
      }
    }
    const clip = svg("clipPath", { id: clipId },
      svg("rect", { x: MARGIN.left, y: MARGIN.top - 6, width: plotW + 6, height: plotH + 7 }));

    const hover = svg("g", { class: "hover" });
    chartSvg.replaceChildren(svg("defs", {}, clip), ...nodes, plot, hover);

    // La línea se desliza lo que ha avanzado el tiempo; solo con la ventana llena.
    if (animate && scrolling && lastEnd !== null && end > lastEnd && !reducedMotion.matches) {
      const dx = ((end - lastEnd) / span) * plotW;
      plot.animate([{ transform: `translateX(${dx}px)` }, { transform: "translateX(0)" }],
        { duration: 600, easing: "cubic-bezier(.2,.7,.3,1)" });
    }
    lastEnd = end;
    drawHover(hover);
  }

  function drawHover(layer) {
    if (hoverX === null || !samples.length || !geometry) { tooltip.hidden = true; return; }
    const { x, y, plotH } = geometry;
    let nearest = samples[0];
    for (const s of samples) if (Math.abs(x(s.t) - hoverX) < Math.abs(x(nearest.t) - hoverX)) nearest = s;
    const px = x(nearest.t);
    layer.append(svg("line", { class: "crosshair", x1: px, x2: px, y1: MARGIN.top, y2: MARGIN.top + plotH }));

    const rows = [];
    for (const s of series) {
      const v = nearest[s.key];
      if (typeof v === "number") layer.append(svg("circle", { class: `hover-dot s-${s.key}`, cx: px, cy: y(v), r: 4 }));
      rows.push(el("div", { className: "tt-row" },
        el("span", { className: `swatch s-${s.key}` }),
        el("span", { className: "tt-label", text: s.label }),
        el("span", { className: "tt-value", text: typeof v === "number" ? formatValue(v) : "—" })));
    }
    tooltip.replaceChildren(el("div", { className: "tt-time", text: formatTime(nearest.t) }), ...rows);
    tooltip.hidden = false;
    const box = tooltip.offsetWidth;
    const left = px + 14 + box > root.clientWidth ? px - 14 - box : px + 14;
    tooltip.style.left = `${Math.max(0, left)}px`;
    tooltip.style.top = `${MARGIN.top}px`;
  }

  chartSvg.addEventListener("pointermove", (event) => {
    const rect = chartSvg.getBoundingClientRect();
    hoverX = event.clientX - rect.left;
    const layer = chartSvg.querySelector(".hover");
    if (layer) { layer.replaceChildren(); drawHover(layer); }
  });
  chartSvg.addEventListener("pointerleave", () => {
    hoverX = null;
    chartSvg.querySelector(".hover")?.replaceChildren();
    tooltip.hidden = true;
  });

  new ResizeObserver(() => draw(false)).observe(root);

  return {
    root,
    update(newSamples) { samples = newSamples; draw(true); },
  };
}

// Salta los huecos (valores null o muestras muy separadas).
function linePath(samples, key, x, y) {
  let d = "";
  let prev = null;
  for (const s of samples) {
    const v = s[key];
    if (typeof v !== "number") { prev = null; continue; }
    const cmd = prev && s.t - prev.t <= GAP_MS ? "L" : "M";
    d += `${cmd}${x(s.t).toFixed(1)} ${y(v).toFixed(1)} `;
    prev = s;
  }
  return d.trim() || "M0 0";
}

function maxValue(samples, series) {
  let max = 0;
  for (const s of samples) for (const { key } of series) if (typeof s[key] === "number") max = Math.max(max, s[key]);
  return max;
}

function niceMax(max) {
  const value = Math.max(max * 1.1, 1024); // mínimo 1 KiB/s para no dibujar ruido
  const unit = 1024 ** Math.floor(Math.log(value) / Math.log(1024));
  const steps = [0.25, 0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250];
  const step = steps.find((s) => s * 4 * unit >= value) ?? 256;
  return step * 4 * unit;
}
