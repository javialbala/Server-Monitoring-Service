// Panel: métricas del servidor y contenedores en ejecución, con actualización periódica.
//
// Se usa setTimeout encadenado (no setInterval): la siguiente consulta se programa cuando
// termina la anterior, así nunca se solapan. Se pausa mientras la pestaña está oculta.

import { el, clear } from "../dom.js";
import { api, isUnauthorized } from "../api.js";
import { formatBytes, formatDate, formatPercent, formatPort, formatTime, formatUptime } from "../format.js";

const REFRESH_MS = 5000;
const NA = "No disponible";

// Tarjeta con título y lista de pares etiqueta/valor.
function card(title, rows) {
  const list = el("dl", { className: "details" });
  for (const [name, value] of rows) {
    list.append(el("dt", { text: name }), el("dd", { text: value ?? NA }));
  }
  return el("section", { className: "card" }, el("h2", { text: title }), list);
}

function renderMetrics(box, m) {
  const temperatures = m.temperatures.length
    ? m.temperatures.map((t) => `${t.sensor}: ${t.celsius} °C`).join(", ")
    : NA;
  clear(box);
  box.append(
    card("CPU", [
      ["Uso", formatPercent(m.cpu.percent)],
      ["Núcleos", String(m.cpu.cores)],
      ["Modelo", m.cpu.model],
    ]),
    card("Memoria RAM", [
      ["Total", formatBytes(m.memory.total_bytes)],
      ["Usada", `${formatBytes(m.memory.used_bytes)} (${formatPercent(m.memory.percent)})`],
      ["Disponible", formatBytes(m.memory.available_bytes)],
    ]),
    card("Disco", [
      ["Total", formatBytes(m.disk.total_bytes)],
      ["Usado", `${formatBytes(m.disk.used_bytes)} (${formatPercent(m.disk.percent)})`],
      ["Libre", formatBytes(m.disk.free_bytes)],
    ]),
    card("Sistema", [
      ["Hostname", m.hostname],
      ["Sistema operativo", m.os.name],
      ["Kernel", m.os.kernel],
      ["Arquitectura", m.os.architecture],
      ["Tiempo encendido", formatUptime(m.uptime_seconds)],
      ["Temperaturas", temperatures],
    ]),
  );
}

function renderContainers(box, data) {
  clear(box);
  if (data.containers.length === 0) {
    box.append(el("p", { className: "muted", text: "No hay contenedores en ejecución." }));
    return;
  }
  const head = el("tr", {}, ...["Nombre", "Imagen", "Estado", "Puertos", "Creado", "Proyecto Compose"]
    .map((title) => el("th", { text: title, attrs: { scope: "col" } })));
  const body = el("tbody");
  for (const c of data.containers) {
    const ports = c.ports.length ? c.ports.map(formatPort).join(", ") : "—";
    body.append(el("tr", {},
      el("td", { text: c.name }),
      el("td", { text: c.image }),
      el("td", { text: c.status }),
      el("td", { text: ports }),
      el("td", { text: formatDate(c.created_at) }),
      el("td", { text: c.compose_project ?? "—" }),
    ));
  }
  const table = el("table", {}, el("thead", {}, head), body);
  box.append(el("div", { className: "table-wrap" }, table));
}

// Dibuja el panel en `root` y devuelve la función para pararlo (cerrar sesión / 401).
export function render(root) {
  const updated = el("span", { className: "muted", text: "Última actualización: —", attrs: { role: "status" } });
  const warning = el("p", { className: "notice notice-error", attrs: { role: "alert" }, text: "No se pudo actualizar; se muestran los últimos datos." });
  warning.hidden = true;
  const metricsBox = el("div", { className: "grid" }, el("p", { className: "muted", text: "Cargando…" }));
  const containersBox = el("div");
  root.append(
    el("div", { className: "page-head" }, el("h1", { text: "Panel" }), updated),
    warning,
    metricsBox,
    el("h2", { className: "section-title", text: "Contenedores en ejecución" }),
    containersBox,
  );

  let stopped = false;
  let running = false; // hay una consulta en curso
  let timer = null;

  async function refresh() {
    if (stopped || running) return;
    running = true;
    try {
      // Si una de las dos falla, no se actualiza ninguna: los datos siempre son coherentes.
      const [metrics, containers] = await Promise.all([api.get("/api/metrics"), api.get("/api/containers")]);
      if (stopped) return;
      renderMetrics(metricsBox, metrics);
      renderContainers(containersBox, containers);
      updated.textContent = `Última actualización: ${formatTime(new Date())}`;
      warning.hidden = true;
    } catch (e) {
      // Con 401 el manejador global ya ha parado el panel. Otros fallos: aviso, sin borrar datos.
      if (!stopped && !isUnauthorized(e)) warning.hidden = false;
    } finally {
      running = false;
      schedule();
    }
  }

  function schedule() {
    clearTimeout(timer);
    if (!stopped && !document.hidden) timer = setTimeout(refresh, REFRESH_MS);
  }

  function onVisibilityChange() {
    if (document.hidden) clearTimeout(timer); // pestaña oculta: pausa
    else refresh(); // al volver, se actualiza enseguida y se reanuda el ciclo
  }

  document.addEventListener("visibilitychange", onVisibilityChange);
  refresh();

  return function stop() {
    stopped = true;
    clearTimeout(timer);
    document.removeEventListener("visibilitychange", onVisibilityChange);
  };
}
