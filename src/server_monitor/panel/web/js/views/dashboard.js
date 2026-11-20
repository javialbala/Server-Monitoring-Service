// Panel con actualización periódica. setTimeout encadenado en lugar de setInterval: la
// siguiente consulta se programa al terminar la anterior y nunca se solapan; se pausa con la
// pestaña oculta.

import { el, icon } from "../dom.js";
import { api, isUnauthorized, ApiError, NetworkError } from "../api.js";
import { formatBytes, formatTime } from "../format.js";

const REFRESH_MS = 5000;
const TABLE_LIMIT = 5;

function percentText(value) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)}%` : "—";
}

function numberText(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";
}

function kpiCard(iconName, title, subtitle) {
  const value = el("p", { className: "kpi-value", text: "—" });
  const fill = el("span", { className: "progress-fill" });
  const bar = el("div", {
    className: "progress",
    attrs: { role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": "0" },
  }, fill);
  const note = el("p", { className: "kpi-note", text: "—" });
  const root = el("article", { className: "kpi-card" },
    el("header", { className: "kpi-head" },
      el("span", { className: "kpi-icon" }, icon(iconName)),
      el("div", { className: "kpi-copy" },
        el("h3", { text: title }),
        el("p", { text: subtitle }))),
    value, bar, note);

  function update(display, percent, message) {
    value.textContent = display;
    const width = typeof percent === "number" && Number.isFinite(percent)
      ? Math.min(100, Math.max(0, percent))
      : 0;
    fill.style.width = `${width.toFixed(1)}%`;
    bar.setAttribute("aria-valuenow", width.toFixed(1));
    note.textContent = message;
  }
  return { root, update };
}

function createOverview() {
  const containers = kpiCard("box", "Running Containers", "Active containers");
  const cpu = kpiCard("cpu", "CPU Usage", "Current load");
  const memory = kpiCard("memory-stick", "Memory Usage", "RAM in use");
  const disk = kpiCard("hard-drive", "Disk Usage", "Root filesystem");
  const root = el("section", { className: "overview", attrs: { id: "overview", "aria-labelledby": "overview-title" } },
    el("h2", { className: "section-title", text: "System Overview", attrs: { id: "overview-title" } }),
    el("div", { className: "kpi-grid" }, containers.root, cpu.root, memory.root, disk.root));

  function update(metrics, containerData) {
    const list = containerData.containers ?? [];
    const running = list.filter((c) => c.state === "running").length;
    const total = list.length;
    containers.update(
      String(running),
      total ? (running / total) * 100 : 0,
      `${running} of ${total} running`,
    );

    const cpuPercent = metrics.cpu?.percent;
    cpu.update(numberText(cpuPercent), cpuPercent, `${percentText(cpuPercent)} of resources being used`);

    const memoryPercent = metrics.memory?.percent;
    memory.update(
      numberText(memoryPercent),
      memoryPercent,
      `${percentText(memoryPercent)} of resources being used`,
    );

    const rootDisk = metrics.disks?.[0];
    const diskPercent = rootDisk?.percent;
    disk.update(numberText(diskPercent), diskPercent, `${percentText(diskPercent)} of resources being used`);
  }

  return { root, update };
}

function detailCard(tone, iconName, title, subtitle, badge) {
  const copy = el("div", { className: "detail-copy" }, el("h3", { text: title }), subtitle);
  const root = el("article", { className: `detail-card detail-${tone}` },
    el("div", { className: "detail-main" },
      el("span", { className: "detail-icon" }, icon(iconName)),
      copy),
    badge);
  return { root };
}

function miniBadge(text, tone) {
  return el("span", { className: `mini-badge mini-${tone}`, text });
}

function createDockerDetails() {
  const version = el("span", { className: "badge", text: "—" });
  const platform = el("span", { className: "detail-sub", text: "linux • —" });
  const engine = detailCard("blue", "ship", "Docker Engine", platform, version);

  const totals = el("div", { className: "mini-badges" },
    miniBadge("total 0", "green"),
    miniBadge("stopped 0", "neutral"));
  const running = el("span", { className: "badge", text: "0 running" });
  const containers = detailCard("green", "box", "Containers", totals, running);

  const imageCount = el("span", { className: "badge", text: "—" });
  const images = detailCard(
    "purple",
    "image",
    "Images",
    el("p", { className: "detail-sub", text: "Total images discovered" }),
    imageCount,
  );

  const root = el("section", { className: "docker-details", attrs: { "aria-labelledby": "docker-title" } },
    el("h2", { className: "section-title", text: "Docker Details", attrs: { id: "docker-title" } }),
    el("div", { className: "detail-grid" }, engine.root, containers.root, images.root));

  function update(metrics, containerData, imagesData, dockerData) {
    const arch = metrics.os?.architecture || "—";
    platform.textContent = `linux • ${arch}`;
    version.textContent = dockerData?.reachable && dockerData.server_version
      ? dockerData.server_version
      : dockerData?.reachable === false
        ? "Offline"
        : "—";

    const list = containerData.containers ?? [];
    const runningCount = list.filter((c) => c.state === "running").length;
    const stoppedCount = list.length - runningCount;
    totals.replaceChildren(
      miniBadge(`total ${list.length}`, "green"),
      miniBadge(`stopped ${stoppedCount}`, "neutral"),
    );
    running.textContent = `${runningCount} running`;

    const count = Array.isArray(imagesData?.images) ? imagesData.images.length : null;
    imageCount.textContent = count === null ? "—" : String(count);
  }

  return { root, update };
}

function containerState(container) {
  if (container.state === "running") {
    if (container.health === "unhealthy") return ["Unhealthy", "red"];
    if (container.health === "starting") return ["Starting", "amber"];
    return ["Running", "green"];
  }
  const states = {
    paused: ["Paused", "amber"],
    restarting: ["Restarting", "amber"],
    exited: ["Stopped", "neutral"],
    created: ["Created", "neutral"],
    dead: ["Dead", "red"],
    removing: ["Removing", "neutral"],
  };
  return states[container.state] ?? [container.state || "Unknown", "neutral"];
}

function containerRow(container) {
  const [label, tone] = containerState(container);
  return el("tr", {},
    el("td", {}, el("span", { className: "cell-strong", text: container.name })),
    el("td", {}, el("span", { className: "cell-muted mono cell-truncate", text: container.image, attrs: { title: container.image } })),
    el("td", {}, el("span", { className: `pill pill-${tone}`, text: label })),
    el("td", {}, el("span", { className: "cell-muted cell-truncate", text: container.status || "—" })));
}

function imageRow(image) {
  return el("tr", {},
    el("td", {}, el("span", { className: "cell-strong mono cell-truncate", text: image.repository, attrs: { title: image.repository } })),
    el("td", {}, el("span", {
      className: `pill ${image.in_use ? "pill-green" : "pill-amber"}`,
      text: image.in_use ? "In Use" : "Unused",
    })),
    el("td", {}, el("span", { className: "cell-muted mono", text: image.tag })),
    el("td", {}, el("span", { className: "cell-strong", text: formatBytes(image.size_bytes) })));
}

function createResourcePanel({ id, title, subtitle, columns, renderRow }) {
  const tbody = el("tbody");
  const table = el("table", { className: "data-table" },
    el("thead", {}, el("tr", {}, ...columns.map((column) => el("th", { text: column, attrs: { scope: "col" } })))),
    tbody);
  const wrap = el("div", { className: "table-wrap" }, table);
  const body = el("div", { className: "resource-body" }, wrap);
  const viewAll = el("button", { className: "text-link", text: "View All →", attrs: { type: "button" } });
  const root = el("article", { className: "resource-panel", attrs: { id } },
    el("header", { className: "resource-head" },
      el("div", {}, el("h3", { text: title }), el("p", { text: subtitle })),
      viewAll),
    body);

  let rows = [];
  let expanded = false;

  function draw() {
    const visible = expanded ? rows : rows.slice(0, TABLE_LIMIT);
    if (rows.length === 0) {
      tbody.replaceChildren();
      body.replaceChildren(el("p", { className: "empty", text: "No data available." }));
    } else {
      tbody.replaceChildren(...visible.map(renderRow));
      body.replaceChildren(wrap);
    }
    viewAll.hidden = rows.length <= TABLE_LIMIT;
    viewAll.textContent = expanded ? "Show Less ←" : "View All →";
  }

  viewAll.addEventListener("click", () => {
    expanded = !expanded;
    draw();
  });

  function update(nextRows) {
    rows = nextRows;
    draw();
  }

  return { root, update };
}

function createResources() {
  const containers = createResourcePanel({
    id: "containers-panel",
    title: "Containers",
    subtitle: "Recent containers",
    columns: ["Name", "Image", "State", "Status"],
    renderRow: containerRow,
  });
  const images = createResourcePanel({
    id: "images-panel",
    title: "Images",
    subtitle: "Top 5 Largest Images",
    columns: ["Repository", "Status", "Tag", "Size"],
    renderRow: imageRow,
  });
  const root = el("section", { className: "resources-section", attrs: { "aria-labelledby": "resources-title" } },
    el("h2", { className: "section-title", text: "Resources", attrs: { id: "resources-title" } }),
    el("div", { className: "resource-grid" }, containers.root, images.root));

  function update(containerData, imagesData) {
    const list = [...(containerData.containers ?? [])].sort((a, b) => {
      const ta = Date.parse(a.created_at);
      const tb = Date.parse(b.created_at);
      if (Number.isNaN(ta) || Number.isNaN(tb)) return 0;
      return tb - ta;
    });
    containers.update(list);
    images.update(Array.isArray(imagesData?.images) ? imagesData.images : []);
  }

  return { root, update };
}

// Devuelve la función que detiene la actualización.
export function render(root) {
  const linkState = document.getElementById("link-state");
  const linkText = document.getElementById("link-text");
  const lastUpdate = document.getElementById("last-update");
  lastUpdate.textContent = "—";
  setLink("pending", "Conectando…");

  const warningText = el("span");
  const warning = el("div", { className: "banner", attrs: { role: "alert" } }, icon("triangle-alert"), warningText);
  warning.hidden = true;
  const loading = el("p", { className: "loading", text: "Loading dashboard…" });

  const overview = createOverview();
  const details = createDockerDetails();
  const resources = createResources();
  const content = el("div", { className: "dashboard" }, warning, overview.root, details.root, resources.root);
  content.hidden = true;
  root.append(el("h1", { className: "sr-only", text: "Estado del servidor" }), loading, content);

  const navLinks = Array.from(document.querySelectorAll("[data-nav]"));
  function setActiveNav(name) {
    for (const link of navLinks) {
      const active = link.dataset.nav === name;
      link.classList.toggle("is-active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
  }
  function onNavClick(event) {
    const link = event.currentTarget;
    const target = document.getElementById(link.getAttribute("href").slice(1));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveNav(link.dataset.nav);
  }
  navLinks.forEach((link) => link.addEventListener("click", onNavClick));
  setActiveNav("dashboard");

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
      // Métricas y contenedores son imprescindibles; imágenes y versión de Docker son opcionales.
      const [metrics, containerData, imagesData, dockerData] = await Promise.all([
        api.get("/api/metrics"),
        api.get("/api/containers"),
        api.get("/api/images").catch(() => null),
        api.get("/api/docker").catch(() => null),
      ]);
      if (stopped) return;
      overview.update(metrics, containerData);
      details.update(metrics, containerData, imagesData, dockerData);
      resources.update(containerData, imagesData);
      loading.hidden = true;
      content.hidden = false;
      lastSuccess = new Date();
      lastUpdate.textContent = formatTime(lastSuccess);
      lastUpdate.title = "Última actualización";
      setLink("ok", "Conectado");
      warning.hidden = true;
    } catch (e) {
      if (!stopped && !isUnauthorized(e)) showFailure(e);
    } finally {
      running = false;
      schedule();
    }
  }

  function showFailure(error) {
    let reason = "error al consultar el servidor";
    if (error instanceof NetworkError) {
      setLink("error", "Sin conexión");
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
    navLinks.forEach((link) => link.removeEventListener("click", onNavClick));
  };
}
