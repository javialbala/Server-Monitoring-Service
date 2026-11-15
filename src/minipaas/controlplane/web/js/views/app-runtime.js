// Sección «Estado real»: lo que de verdad está ejecutándose según el agente.
// No hay polling: se carga al abrir, con «Actualizar» y tras cada operación.

import { el, clear } from "../dom.js";
import { api, isUnauthorized, errorMessage } from "../api.js";
import { loadingBox, errorBox, toneBadge } from "../ui.js";
import { RUNTIME_TONE } from "../tones.js";

// Solo se enlazan URLs http/https, aunque la API sea de confianza.
function safeUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch (e) {
    return null;
  }
}

function serviceRow(s) {
  const head = el("div", { className: "item-head" },
    el("h3", { text: s.name }),
    toneBadge(s.state_label, RUNTIME_TONE[s.state] || "neutral"));
  const item = el("li", { className: "item" }, head,
    el("p", { className: "meta", text: "Revisión " + s.revision }));
  if (s.state === "exited" && s.exit_code != null && s.exit_code !== 0) {
    item.append(el("p", { className: "meta", text: "Código de salida: " + s.exit_code }));
  }
  const url = s.access_url ? safeUrl(s.access_url) : null;
  if (url) {
    item.append(el("p", {}, el("a", {
      text: "Abrir", attrs: { href: url, target: "_blank", rel: "noopener noreferrer",
        "aria-label": `Abrir ${s.name} en una pestaña nueva` } })));
  }
  return item;
}

export function mount(container, { ctx, path }) {
  let hasLoaded = false;

  async function reload() {
    if (!hasLoaded) { clear(container); container.append(loadingBox("Consultando el estado real…")); }
    try {
      const data = await api.get(path + "/runtime");
      if (!ctx.isCurrent()) return;
      hasLoaded = true;
      clear(container);
      const refresh = el("button", { className: "btn-secondary btn-small", text: "Actualizar", attrs: { type: "button" } });
      refresh.addEventListener("click", async () => {
        refresh.disabled = true; refresh.textContent = "Actualizando…";
        await reload();
      });
      container.append(el("div", { className: "section-head" }, el("h2", { text: "Estado real" }), refresh));
      if (!data.agent_reachable) {
        container.append(el("div", { className: "notice notice-error" },
          el("p", { text: "No se puede contactar con el agente: el estado real no está disponible." })));
      }
      if (data.unknown_containers > 0) {
        container.append(el("div", { className: "notice notice-info" },
          el("p", { text: `Hay ${data.unknown_containers} contenedor(es) de esta aplicación que MiniPaaS no reconoce. Puedes usar «Recuperar» si la aplicación necesita revisión.` })));
      }
      if (!data.services.length) {
        container.append(el("p", { className: "muted", text: "No hay servicios en ejecución." }));
      } else {
        const list = el("ul", { className: "item-list" });
        for (const s of data.services) list.append(serviceRow(s));
        container.append(list);
      }
    } catch (e) {
      if (!ctx.isCurrent() || isUnauthorized(e)) return;
      clear(container);
      container.append(el("h2", { text: "Estado real" }), errorBox(errorMessage(e), reload));
    }
  }

  return { reload };
}
