// Sección «Historial de despliegues»: una entrada por revisión y, bajo
// demanda, la bitácora de eventos de cada una.

import { el, clear } from "../dom.js";
import { api, isUnauthorized, errorMessage } from "../api.js";
import { formatDate } from "../format.js";
import { loadingBox, errorBox, toneBadge } from "../ui.js";
import { DEPLOY_TONE } from "../tones.js";

const OUTCOME_LABEL = { info: "Info", success: "Correcto", failure: "Fallo" };

export function deployBadge(d) {
  return toneBadge(d.status_label, DEPLOY_TONE[d.status] || "neutral");
}

function formatTime(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString("es-ES");
}

// Bitácora en orden. `limit` (opcional) muestra solo los últimos N eventos.
export function eventsList(events, limit) {
  const list = el("ol", { className: "events" });
  const shown = limit ? events.slice(-limit) : events;
  for (const ev of shown) {
    const outcome = /^[a-z]+$/.test(String(ev.outcome)) ? ev.outcome : "info";
    list.append(el("li", { className: "outcome-" + outcome },
      el("span", { className: "time", text: formatTime(ev.occurred_at) }),
      el("span", { className: "step" }, el("code", { text: ev.step }),
        " · " + (OUTCOME_LABEL[outcome] || outcome)),
      el("span", { className: "msg", text: ev.message })));
  }
  return list;
}

function servicesText(services) {
  return services.map((s) => `${s.name} (${s.catalog_name})`).join(", ");
}

// Devuelve { reload() } ; reload() resuelve con la lista de despliegues (o null si falla).
export function mount(container, { ctx, path }) {
  const openRevisions = new Set(); // revisiones con «Ver detalles» abierto
  let hasLoaded = false;

  function entry(d) {
    const head = el("div", { className: "item-head" },
      el("h3", { text: "Revisión " + d.revision }),
      el("span", { className: "badge-group" },
        d.is_active ? toneBadge("Activa", "ok") : null, deployBadge(d)));
    const item = el("li", { className: "item" }, head,
      el("p", { className: "meta", text: formatDate(d.created_at) }));
    if (d.services.length) {
      item.append(el("p", { className: "meta", text: "Servicios: " + servicesText(d.services) }));
    }
    if (d.status === "rolled_back" && d.previous_revision != null) {
      item.append(el("p", { text: `Falló y se recuperó la revisión ${d.previous_revision}.` }));
    }
    if (d.error) item.append(el("p", { className: "inline-error", text: d.error }));

    const body = el("div", { attrs: { "aria-live": "polite" } });
    const details = el("details", {}, el("summary", { text: "Ver detalles" }), body);
    let loaded = false;
    async function loadDetail() {
      clear(body);
      body.append(loadingBox("Cargando detalles…"));
      try {
        const full = await api.get(`${path}/deployments/${d.revision}`);
        if (!ctx.isCurrent()) return;
        clear(body);
        loaded = true;
        body.append(full.events && full.events.length
          ? eventsList(full.events) : el("p", { className: "muted", text: "Sin eventos registrados." }));
      } catch (e) {
        if (!ctx.isCurrent() || isUnauthorized(e)) return;
        clear(body);
        body.append(errorBox(errorMessage(e), loadDetail));
      }
    }
    details.addEventListener("toggle", () => {
      if (details.open) { openRevisions.add(d.revision); if (!loaded) loadDetail(); }
      else openRevisions.delete(d.revision);
    });
    item.append(details);
    if (openRevisions.has(d.revision)) details.open = true;
    return item;
  }

  async function reload() {
    // Primera carga: indicador; en recargas se conserva lo pintado hasta tener datos.
    if (!hasLoaded) { clear(container); container.append(loadingBox("Cargando historial…")); }
    try {
      const data = await api.get(path + "/deployments");
      if (!ctx.isCurrent()) return null;
      hasLoaded = true;
      const items = [...data.items].sort((a, b) => b.revision - a.revision); // más reciente primero
      clear(container);
      container.append(el("div", { className: "section-head" }, el("h2", { text: "Historial de despliegues" })));
      if (!items.length) {
        container.append(el("p", { className: "muted", text: "Todavía no se ha desplegado ninguna revisión." }));
      } else {
        const list = el("ul", { className: "item-list" });
        for (const d of items) list.append(entry(d));
        container.append(list);
      }
      return items;
    } catch (e) {
      if (!ctx.isCurrent() || isUnauthorized(e)) return null;
      clear(container);
      container.append(el("h2", { text: "Historial de despliegues" }), errorBox(errorMessage(e), reload));
      return null;
    }
  }

  return { reload };
}
