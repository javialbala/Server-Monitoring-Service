// Lista de aplicaciones.

import { el, clear } from "../dom.js";
import { api, isUnauthorized, errorMessage } from "../api.js";
import { formatDate } from "../format.js";
import { loadingBox, errorBox } from "../ui.js";

// La clase de la insignia sale de `status`; se limita a [a-z-] por seguridad.
export function badge(app) {
  const kind = String(app.status).replace(/[^a-z-]/g, "");
  return el("span", { className: "badge badge-" + kind, text: app.status_label });
}

function newButton() {
  return el("a", { className: "button", text: "Nueva aplicación", attrs: { href: "#/apps/new" } });
}

function appCard(app) {
  const title = el("h2", { className: "app-name" },
    el("a", { text: app.name, attrs: { href: "#/apps/" + encodeURIComponent(app.slug) } }));
  const description = app.description
    ? el("p", { className: "app-description", text: app.description })
    : el("p", { className: "app-description muted", text: "Sin descripción" });
  return el("li", { className: "card app-item" },
    el("div", { className: "app-item-head" }, title, badge(app)),
    description,
    el("p", { className: "meta", text: "Creada el " + formatDate(app.created_at) }));
}

export function render(root, ctx) {
  const head = el("div", { className: "page-head" },
    el("h1", { text: "Aplicaciones", attrs: { tabindex: "-1" } }), newButton());
  const body = el("div");
  root.append(head, body);

  async function load() {
    clear(body);
    body.append(loadingBox("Cargando aplicaciones…"));
    try {
      const data = await api.get("/api/applications");
      if (!ctx.isCurrent()) return;
      clear(body);
      if (!data.items.length) {
        body.append(el("div", { className: "card empty" },
          el("h2", { text: "Todavía no hay aplicaciones" }),
          el("p", { className: "muted", text: "Registra tu primera aplicación. Podrás desplegarla cuando esté disponible el despliegue (próximas fases)." }),
          newButton()));
        return;
      }
      const list = el("ul", { className: "app-list" });
      for (const app of data.items) list.append(appCard(app));
      body.append(list);
    } catch (e) {
      if (!ctx.isCurrent() || isUnauthorized(e)) return;
      clear(body);
      body.append(errorBox(errorMessage(e), load));
    }
  }
  load();
}
