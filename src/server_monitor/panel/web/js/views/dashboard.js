// Panel con actualización periódica. setTimeout encadenado en lugar de setInterval: la
// siguiente consulta se programa al terminar la anterior y nunca se solapan; se pausa con la
// pestaña oculta.

import { el, icon, clear } from "../dom.js";
import { api, isUnauthorized, ApiError, NetworkError } from "../api.js";
import { createGauge, createLineChart } from "../charts.js";
import { createHistory } from "../history.js";
import {
  NA, formatBytes, formatDate, formatPercent, formatPorts, formatRate, formatRateAxis, formatTime, formatUptime,
} from "../format.js";

const REFRESH_MS = 5000;

// [alto, crítico]
const THRESHOLDS = { cpu: [75, 90], ram: [80, 90], disk: [80, 90] };
const TEMP_THRESHOLDS = [75, 90]; // °C

function toneFor(value, [warning, critical]) {
  if (value >= critical) return "critical";
  if (value >= warning) return "warning";
  return "normal";
}

// kind (cpu | ram | disk) da el color del arco; rows: [[clave, etiqueta]].
function metricCell(kind, iconName, title, rows) {
  const gauge = createGauge();
  const sub = el("span", { className: "metric-sub" });
  const toneTag = el("span", { className: "tone-tag" });
  const values = {};
  const list = el("dl", { className: "kv" });
  for (const [key, label] of rows) {
    values[key] = el("dd", { text: "—" });
    list.append(el("div", { className: "kv-row" }, el("dt", { text: label }), values[key]));
  }
  const root = el("article", { className: `metric metric-${kind}` },
    el("header", { className: "metric-head" }, icon(iconName), el("h2", { text: title }), sub),
    el("div", { className: "metric-body" }, el("div", { className: "gauge-wrap" }, gauge.root, toneTag), list));

  function setPercent(percent, thresholds) {
    const tone = toneFor(percent, thresholds);
    gauge.update(percent, tone);
    root.dataset.tone = tone;
    toneTag.textContent = tone === "critical" ? "Crítico" : tone === "warning" ? "Alto" : "";
  }
  return { root, sub, values, setPercent };
}

function createResources() {
  const cpu = metricCell("cpu", "cpu", "CPU", [["cores", "Núcleos"], ["model", "Modelo"]]);
  const ram = metricCell("ram", "memory-stick", "Memoria RAM", [["used", "Usada"], ["available", "Disponible"], ["total", "Total"]]);
  const root = el("section", { className: "panel resources", attrs: { "aria-label": "Uso de recursos" } }, cpu.root, ram.root);
  let disks = [];
  let diskKey = "";

  function update(m) {
    cpu.setPercent(m.cpu.percent, THRESHOLDS.cpu);
    cpu.values.cores.textContent = String(m.cpu.cores);
    cpu.values.model.textContent = m.cpu.model || NA;
    cpu.values.model.title = m.cpu.model || "";

    ram.setPercent(m.memory.percent, THRESHOLDS.ram);
    ram.values.used.textContent = formatBytes(m.memory.used_bytes);
    ram.values.available.textContent = formatBytes(m.memory.available_bytes);
    ram.values.total.textContent = formatBytes(m.memory.total_bytes);

    // Las celdas de disco solo se rehacen si cambia la lista de discos.
    const key = m.disks.map((d) => d.path).join("|");
    if (key !== diskKey) {
      for (const cell of disks) cell.root.remove();
      disks = m.disks.map(() => metricCell("disk", "hard-drive", "Almacenamiento", [["used", "Usado"], ["free", "Libre"], ["total", "Total"]]));
      root.append(...disks.map((cell) => cell.root));
      root.dataset.count = String(2 + disks.length);
      diskKey = key;
    }
    m.disks.forEach((d, i) => {
      const cell = disks[i];
      cell.sub.textContent = `${d.name} · ${d.path}`;
      cell.setPercent(d.percent, THRESHOLDS.disk);
      cell.values.used.textContent = formatBytes(d.used_bytes);
      cell.values.free.textContent = formatBytes(d.free_bytes);
      cell.values.total.textContent = formatBytes(d.total_bytes);
    });
  }
  return { root, update };
}

function legendItem(key, label, iconName) {
  const value = el("span", { className: "legend-value", text: "—" });
  const item = el("li", { className: "legend-item" },
    el("span", { className: `swatch s-${key}` }),
    iconName ? icon(iconName, "icon icon-sm") : null,
    el("span", { className: "legend-label", text: label }), value);
  return { item, value };
}

function chartPanel(title, legendItems, chart) {
  return el("article", { className: "panel chart-panel" },
    el("header", { className: "panel-head" },
      el("h2", { text: title }),
      el("ul", { className: "legend" }, ...legendItems.map((l) => l.item))),
    chart.root);
}

function createCharts() {
  const usage = createLineChart({
    series: [{ key: "cpu", label: "CPU" }, { key: "ram", label: "RAM" }],
    yMax: 100,
    formatValue: formatPercent,
    formatAxis: (v) => `${v} %`,
    label: "Evolución del uso de CPU y RAM en los últimos 10 minutos",
  });
  const network = createLineChart({
    series: [{ key: "rx", label: "Bajada" }, { key: "tx", label: "Subida" }],
    formatValue: formatRate,
    formatAxis: formatRateAxis,
    label: "Velocidad de red de bajada y subida en los últimos 10 minutos",
  });
  const legend = {
    cpu: legendItem("cpu", "CPU"), ram: legendItem("ram", "RAM"),
    rx: legendItem("rx", "Bajada", "arrow-down"), tx: legendItem("tx", "Subida", "arrow-up"),
  };
  const networkPanel = chartPanel("Red", [legend.rx, legend.tx], network);
  const grid = el("div", { className: "charts" },
    chartPanel("Uso de CPU y RAM", [legend.cpu, legend.ram], usage), networkPanel);
  const root = el("section", { className: "section", attrs: { "aria-labelledby": "charts-title" } },
    el("div", { className: "section-head" },
      el("h2", { className: "section-title", text: "Evolución", attrs: { id: "charts-title" } }),
      el("p", { className: "section-note" }, icon("clock", "icon icon-sm"),
        el("span", { text: "Últimos 10 min · histórico solo en este navegador, empieza de cero al recargar" }))),
    grid);

  function update(samples, metrics) {
    const last = samples[samples.length - 1];
    legend.cpu.value.textContent = formatPercent(metrics.cpu.percent);
    legend.ram.value.textContent = formatPercent(metrics.memory.percent);
    legend.rx.value.textContent = last ? formatRate(last.rx) : "—";
    legend.tx.value.textContent = last ? formatRate(last.tx) : "—";
    usage.update(samples);
    // Sin lectura de red del agente no se muestra su gráfica.
    const hasNetwork = metrics.network !== null && metrics.network !== undefined;
    networkPanel.hidden = !hasNetwork;
    grid.classList.toggle("charts-single", !hasNetwork);
    if (hasNetwork) network.update(samples);
  }
  return { root, update };
}

function createSystem() {
  const fields = {};
  const item = (key, iconName, label) => {
    fields[key] = el("dd", { text: "—" });
    return el("div", { className: `sys-item sys-${key}` }, icon(iconName), el("dt", { text: label }), fields[key]);
  };
  const list = el("dl", { className: "sys-list" },
    item("hostname", "server", "Hostname"),
    item("os", "monitor", "Sistema operativo"),
    item("kernel", "layers", "Kernel"),
    item("arch", "cpu", "Arquitectura"),
    item("uptime", "clock", "Tiempo encendido"),
    item("temp", "thermometer", "Temperatura"));
  const root = el("section", { className: "panel system", attrs: { "aria-labelledby": "system-title" } },
    el("header", { className: "panel-head" }, el("h2", { text: "Sistema", attrs: { id: "system-title" } })), list);

  function update(m) {
    fields.hostname.textContent = m.hostname || NA;
    fields.os.textContent = m.os.name || NA;
    fields.kernel.textContent = m.os.kernel || NA;
    fields.arch.textContent = m.os.architecture || NA;
    fields.uptime.textContent = formatUptime(m.uptime_seconds);
    const celsius = m.temperature?.celsius;
    const temp = fields.temp.parentElement;
    if (typeof celsius === "number") {
      fields.temp.textContent = `${celsius.toFixed(0)} °C`;
      temp.dataset.tone = toneFor(celsius, TEMP_THRESHOLDS);
    } else {
      fields.temp.textContent = NA;
      temp.dataset.tone = "unknown";
    }
  }
  return { root, update };
}

// [texto, tono] de cada estado de Docker.
function containerState(c) {
  if (c.state === "running") {
    if (c.health === "unhealthy") return ["Con fallos", "critical"];
    if (c.health === "starting") return ["Arrancando", "warning"];
    return ["En ejecución", "ok"];
  }
  const states = {
    paused: ["En pausa", "warning"],
    restarting: ["Reiniciando", "warning"],
    exited: ["Detenido", "stopped"],
    created: ["Creado", "stopped"],
    dead: ["Muerto", "critical"],
    removing: ["Eliminándose", "stopped"],
  };
  return states[c.state] ?? [c.state || "Desconocido", "stopped"];
}

function containerRow(c) {
  const [label, tone] = containerState(c);
  const cell = (heading, className, ...children) =>
    el("td", { className, attrs: { "data-label": heading } }, ...children);

  const name = el("div", { className: "c-name" }, el("span", { text: c.name }));
  if (c.compose_service && c.compose_service !== c.name) {
    name.append(el("span", { className: "c-service", text: c.compose_service }));
  }
  const ports = formatPorts(c.ports ?? []);
  const portList = ports.length
    ? el("ul", { className: "ports" }, ...ports.map((p) => el("li", { className: "port", text: p })))
    : el("span", { className: "muted", text: "Sin publicar" });

  return el("tr", { attrs: { "data-tone": tone } },
    cell("Nombre", "c-main", name),
    cell("Estado", "c-state",
      el("span", { className: "state" }, el("span", { className: "state-dot", attrs: { "aria-hidden": "true" } }),
        el("span", { className: "state-label", text: label })),
      el("span", { className: "state-detail", text: c.status })),
    cell("Imagen", "c-image", el("span", { className: "mono", text: c.image, attrs: { title: c.image } })),
    cell("Puertos", "c-ports", portList),
    cell("Proyecto Compose", "c-project",
      c.compose_project ? el("span", { className: "project", text: c.compose_project }) : el("span", { className: "muted", text: "—" })),
    cell("Creado", "c-created", el("span", { text: formatDate(c.created_at) })));
}

function createContainers() {
  const summary = el("p", { className: "panel-meta" });
  const body = el("div", { className: "containers-body" });
  const root = el("section", { className: "panel containers", attrs: { "aria-labelledby": "containers-title" } },
    el("header", { className: "panel-head" },
      el("h2", { text: "Contenedores", attrs: { id: "containers-title" } }), summary),
    body);

  function update(data) {
    const list = data.containers;
    const running = list.filter((c) => c.state === "running").length;
    const failing = list.filter((c) => c.health === "unhealthy").length;
    const parts = [`${running} en ejecución`, `${list.length - running} detenidos`];
    if (failing) parts.push(`${failing} con fallos`);
    summary.textContent = parts.join(" · ");

    clear(body);
    if (list.length === 0) {
      body.append(el("p", { className: "empty", text: "No hay contenedores en este servidor." }));
      return;
    }
    const head = el("tr", {}, ...["Nombre", "Estado", "Imagen", "Puertos", "Proyecto Compose", "Creado"]
      .map((title) => el("th", { text: title, attrs: { scope: "col" } })));
    const table = el("table", { className: "table" }, el("thead", {}, head), el("tbody", {}, ...list.map(containerRow)));
    body.append(el("div", { className: "table-wrap" }, table));
  }
  return { root, update };
}

// Devuelve la función que detiene la actualización.
export function render(root) {
  const hostName = document.getElementById("host-name");
  const linkState = document.getElementById("link-state");
  const linkText = document.getElementById("link-text");
  const lastUpdate = document.getElementById("last-update");
  hostName.textContent = "";
  lastUpdate.textContent = "Última actualización —";
  setLink("pending", "Conectando…");

  const warningText = el("span");
  const warning = el("div", { className: "banner", attrs: { role: "alert" } }, icon("triangle-alert"), warningText);
  warning.hidden = true;
  const loading = el("p", { className: "loading", text: "Cargando métricas del servidor…" });

  const history = createHistory();
  const resources = createResources();
  const charts = createCharts();
  const system = createSystem();
  const containers = createContainers();
  const content = el("div", { className: "dashboard" }, resources.root, charts.root, system.root, containers.root);
  content.hidden = true;
  root.append(el("div", { className: "page" },
    el("h1", { className: "sr-only", text: "Estado del servidor" }), warning, loading, content));

  let stopped = false;
  let running = false;
  let timer = null;
  let lastSuccess = null;

  function setLink(state, text) {
    linkState.dataset.state = state;
    linkText.textContent = text;
  }

  async function refresh() {
    if (stopped || running) return;
    running = true;
    try {
      // Si una falla no se actualiza ninguna, para que los datos sean coherentes.
      const [metrics, containerData] = await Promise.all([api.get("/api/metrics"), api.get("/api/containers")]);
      if (stopped) return;
      history.add(metrics);
      hostName.textContent = metrics.hostname || "";
      resources.update(metrics);
      system.update(metrics);
      containers.update(containerData);
      loading.hidden = true;
      content.hidden = false; // las gráficas necesitan ser visibles para medir su ancho
      charts.update(history.samples, metrics);
      lastSuccess = new Date();
      lastUpdate.textContent = `Última actualización ${formatTime(lastSuccess)}`;
      setLink("ok", "Conectado");
      warning.hidden = true;
    } catch (e) {
      // Con 401 el manejador global ya ha parado el panel.
      if (!stopped && !isUnauthorized(e)) showFailure(e);
    } finally {
      running = false;
      schedule();
    }
  }

  function showFailure(error) {
    let reason = "error al consultar el servidor";
    if (error instanceof NetworkError) {
      setLink("error", "Sin conexión con el panel");
      reason = "no hay conexión con el panel";
    } else if (error instanceof ApiError && error.status === 502) {
      setLink("error", "Agente sin respuesta");
      reason = "el agente no responde";
    } else {
      setLink("error", "Error al actualizar");
    }
    warningText.textContent = lastSuccess
      ? `No se pudo actualizar: ${reason}. Se muestran los datos de las ${formatTime(lastSuccess)}; se reintentará en unos segundos.`
      : `No se pudieron obtener los datos: ${reason}. Se reintentará en unos segundos.`;
    warning.hidden = false;
  }

  function schedule() {
    clearTimeout(timer);
    if (!stopped && !document.hidden) timer = setTimeout(refresh, REFRESH_MS);
  }

  function onVisibilityChange() {
    if (document.hidden) clearTimeout(timer);
    else refresh();
  }

  document.addEventListener("visibilitychange", onVisibilityChange);
  refresh();

  return function stop() {
    stopped = true;
    clearTimeout(timer);
    document.removeEventListener("visibilitychange", onVisibilityChange);
  };
}
