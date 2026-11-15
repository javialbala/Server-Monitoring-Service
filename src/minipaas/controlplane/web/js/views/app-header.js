// Cabecera de la aplicación: nombre, estado, datos y acciones según el estado.

import { el, clear } from "../dom.js";
import { formatDate } from "../format.js";
import { toneBadge } from "../ui.js";
import { APP_TONE } from "../tones.js";

const RECOVER_TEXT = "La aplicación necesita revisión. Recuperar limpia los restos de operaciones fallidas y vuelve a poner en marcha la última versión que funcionaba.";

// st: { app, serviceCount (null si aún no se sabe), deploying, busyAction, error }
// h:  { onDeploy, onAction(kind), onEdit, onDelete(button) }
export function renderHeader(container, st, h) {
  clear(container);
  const { app, busyAction } = st;
  const locked = Boolean(busyAction) || st.deploying;
  const hasRevision = Number.isInteger(app.active_revision);

  const button = (cls, text, handler, disabled) => {
    const b = el("button", { className: cls, text, attrs: { type: "button", disabled } });
    b.addEventListener("click", () => handler(b));
    return b;
  };
  const busyText = { stop: "Deteniendo…", start: "Arrancando…", recover: "Recuperando…" };
  const lifecycle = (kind, label, cls) =>
    button(cls, busyAction === kind ? busyText[kind] : label, () => h.onAction(kind), locked || app.operation_in_progress);

  const actions = el("div", { className: "actions" });
  const noServices = st.serviceCount === 0;
  const deployDisabled = locked || app.operation_in_progress || !st.serviceCount;
  actions.append(button("", st.deploying ? "Desplegando…" : "Desplegar", h.onDeploy, deployDisabled));
  if (app.status === "running") actions.append(lifecycle("stop", "Detener", "btn-secondary"));
  if (app.status === "stopped") actions.append(lifecycle("start", "Arrancar", "btn-secondary"));
  if (app.status === "attention") actions.append(lifecycle("recover", "Recuperar", "btn-secondary"));
  actions.append(button("btn-secondary", "Editar", h.onEdit, false),
    button("btn-danger", "Eliminar", h.onDelete, false));

  const card = el("section", { className: "card", attrs: { "aria-labelledby": "app-title" } },
    el("div", { className: "app-item-head" },
      el("h1", { text: app.name, attrs: { id: "app-title", tabindex: "-1" } }),
      el("span", { className: "badge-group" },
        toneBadge(app.status_label, APP_TONE[app.status] || "neutral"),
        app.operation_in_progress ? toneBadge("Operación en curso", "progress") : null)),
    el("p", { className: "meta", text: hasRevision ? `Revisión activa: r${app.active_revision}` : "Sin desplegar" }),
    el("dl", { className: "details" },
      el("dt", { text: "Identificador" }), el("dd", {}, el("code", { text: app.slug })),
      el("dt", { text: "Descripción" }),
      el("dd", { className: app.description ? "" : "muted", text: app.description || "Sin descripción" }),
      el("dt", { text: "Creada" }), el("dd", { text: formatDate(app.created_at) }),
      el("dt", { text: "Última modificación" }), el("dd", { text: formatDate(app.updated_at) })));

  if (app.status === "attention") card.append(el("p", { className: "notice notice-error", text: RECOVER_TEXT }));
  card.append(actions);
  if (noServices) card.append(el("p", { className: "hint", text: "Añade al menos un servicio para poder desplegar." }));
  if (app.operation_in_progress && !st.deploying) {
    card.append(el("p", { className: "hint", text: "Hay una operación en curso; las acciones se habilitarán cuando termine." }));
  }
  card.append(el("p", { className: "inline-error", text: st.error || "", attrs: { role: "alert" } }));
  container.append(card);
}
