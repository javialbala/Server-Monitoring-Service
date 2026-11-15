// Sección «Servicios»: configuración que se aplicará en el próximo despliegue.
// Aquí viven la lista, el borrado y el cambio entre lista y formulario.

import { el, clear } from "../dom.js";
import { api, isUnauthorized, errorMessage } from "../api.js";
import { loadingBox, errorBox, toast, toneBadge, confirmDialog } from "../ui.js";
import { renderServiceForm } from "./service-form.js";

function accessText(s) {
  if (!s.publish) return "Solo interno";
  return s.host_port != null ? `Publicado en el puerto ${s.host_port}` : "Publicado (puerto asignado automáticamente)";
}

// opts: { ctx, path, onChange(items|null) } ; reload() resuelve con la lista.
export function mount(container, { ctx, path, onChange }) {
  const svcPath = path + "/services";
  let catalogPromise = null;
  let items = [];
  let hasLoaded = false;

  // El catálogo se pide una sola vez (y se reintenta si falló).
  function getCatalog() {
    if (!catalogPromise) {
      catalogPromise = api.get("/api/catalog").then((d) => d.items);
      catalogPromise.catch(() => { catalogPromise = null; });
    }
    return catalogPromise;
  }

  async function openForm(service, button) {
    const original = button ? button.textContent : "";
    if (button) { button.disabled = true; button.textContent = "Cargando…"; }
    let catalog;
    try {
      catalog = await getCatalog();
    } catch (e) {
      if (button && button.isConnected) { button.disabled = false; button.textContent = original; }
      if (!ctx.isCurrent() || isUnauthorized(e)) return;
      toast("No se pudo cargar el catálogo: " + errorMessage(e));
      return;
    }
    if (!ctx.isCurrent()) return;
    clear(container);
    renderServiceForm(container, {
      ctx, path: svcPath, catalog, service,
      onDone: async () => { toast(service ? "Servicio actualizado." : "Servicio añadido."); await reload(); focusHeading(); },
      onCancel: async () => { await reload(); focusHeading(); },
    });
  }

  function focusHeading() {
    const h = container.querySelector("h2");
    if (h) { h.setAttribute("tabindex", "-1"); h.focus(); }
  }

  function confirmDelete(s, opener) {
    confirmDialog({
      title: `¿Eliminar el servicio «${s.name}»?`,
      text: "Se quitará de la configuración. Los cambios se aplican en el próximo despliegue.",
      confirmLabel: "Eliminar", busyLabel: "Eliminando…", opener,
      action: async () => {
        await api.del(`${svcPath}/${encodeURIComponent(s.name)}`);
        if (!ctx.isCurrent()) return;
        toast(`Servicio «${s.name}» eliminado.`);
        await reload();
      },
    });
  }

  function serviceItem(s) {
    const edit = el("button", { className: "btn-secondary btn-small", text: "Editar",
      attrs: { type: "button", "aria-label": `Editar ${s.name}` } });
    const del = el("button", { className: "btn-danger btn-small", text: "Eliminar",
      attrs: { type: "button", "aria-label": `Eliminar ${s.name}`, disabled: s.protected } });
    edit.addEventListener("click", () => openForm(s, edit));
    del.addEventListener("click", () => confirmDelete(s, del));

    const envNames = Object.keys(s.env || {});
    const envNode = envNames.length
      ? el("ul", { className: "env-list" }, ...envNames.map((n) => el("li", {}, el("code", { text: `${n}=${s.env[n]}` }))))
      : el("span", { className: "muted", text: "Ninguna" });

    const item = el("li", { className: "item" },
      el("div", { className: "item-head" }, el("h3", { text: s.name }),
        s.protected ? toneBadge("Protegido", "neutral") : null),
      el("dl", { className: "details" },
        el("dt", { text: "Tipo" }), el("dd", { text: s.catalog_name }),
        el("dt", { text: "Acceso" }), el("dd", { text: accessText(s) }),
        el("dt", { text: "Recursos" }), el("dd", { text: `${s.memory_mb} MiB de memoria · ${s.cpus} CPU` }),
        el("dt", { text: "Variables" }), el("dd", {}, envNode)));
    const actions = el("div", { className: "actions" }, edit, del);
    if (s.protected) {
      const id = "protected-" + s.name;
      del.setAttribute("aria-describedby", id);
      actions.append(el("p", { className: "hint", text: "Este servicio está protegido y no se puede eliminar.", attrs: { id } }));
    }
    item.append(actions);
    return item;
  }

  async function reload() {
    if (!hasLoaded) { clear(container); container.append(loadingBox("Cargando servicios…")); }
    try {
      const data = await api.get(svcPath);
      if (!ctx.isCurrent()) return null;
      hasLoaded = true;
      items = data.items;
      clear(container);
      const add = el("button", { className: "btn-secondary btn-small", text: "Añadir servicio", attrs: { type: "button" } });
      add.addEventListener("click", () => openForm(null, add));
      container.append(
        el("div", { className: "section-head" }, el("h2", { text: "Servicios" }), add),
        el("p", { className: "hint", text: "Los cambios se aplican en el próximo despliegue." }));
      if (!items.length) {
        container.append(el("p", { className: "muted", text: "Esta aplicación todavía no tiene servicios. Añade al menos uno para poder desplegarla." }));
      } else {
        const list = el("ul", { className: "item-list" });
        for (const s of items) list.append(serviceItem(s));
        container.append(list);
      }
      if (onChange) onChange(items);
      return items;
    } catch (e) {
      if (!ctx.isCurrent() || isUnauthorized(e)) return null;
      clear(container);
      container.append(el("h2", { text: "Servicios" }), errorBox(errorMessage(e), reload));
      return null;
    }
  }

  return { reload };
}
