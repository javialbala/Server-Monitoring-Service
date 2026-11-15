// Detalle de una aplicación: ver, editar (nombre y descripción) y eliminar.

import { el, clear } from "../dom.js";
import { api, ApiError, isUnauthorized, errorMessage } from "../api.js";
import { DESCRIPTION_MAX, NAME_MAX, formatDate } from "../format.js";
import { field, formError, setBusy, applyValidationErrors, loadingBox, errorBox, toast } from "../ui.js";
import { badge } from "./apps.js";

export function render(root, ctx) {
  const slug = ctx.params.slug;
  const path = "/api/applications/" + encodeURIComponent(slug);
  const body = el("div");
  root.append(body);

  async function load() {
    clear(body);
    body.append(loadingBox("Cargando aplicación…"));
    try {
      const app = await api.get(path);
      if (!ctx.isCurrent()) return;
      showView(app);
    } catch (e) {
      if (!ctx.isCurrent() || isUnauthorized(e)) return;
      clear(body);
      if (e instanceof ApiError && e.status === 404) {
        body.append(el("div", { className: "card empty" },
          el("h1", { text: "Esta aplicación no existe o ha sido eliminada", attrs: { tabindex: "-1" } }),
          el("a", { className: "button", text: "Volver a la lista", attrs: { href: "#/apps" } })));
      } else {
        body.append(errorBox(errorMessage(e), load));
      }
    }
  }

  function showView(app) {
    clear(body);
    const edit = el("button", { className: "btn-secondary", text: "Editar", attrs: { type: "button" } });
    const del = el("button", { className: "btn-danger", text: "Eliminar", attrs: { type: "button" } });
    edit.addEventListener("click", () => showEdit(app));
    del.addEventListener("click", () => confirmDelete(app, del));

    body.append(
      el("p", {}, el("a", { text: "← Aplicaciones", attrs: { href: "#/apps" } })),
      el("section", { className: "card", attrs: { "aria-labelledby": "app-title" } },
        el("div", { className: "app-item-head" },
          el("h1", { text: app.name, attrs: { id: "app-title", tabindex: "-1" } }), badge(app)),
        el("dl", { className: "details" },
          el("dt", { text: "Identificador" }), el("dd", {}, el("code", { text: app.slug })),
          el("dt", { text: "Descripción" }),
          el("dd", { className: app.description ? "" : "muted", text: app.description || "Sin descripción" }),
          el("dt", { text: "Creada" }), el("dd", { text: formatDate(app.created_at) }),
          el("dt", { text: "Última modificación" }), el("dd", { text: formatDate(app.updated_at) })),
        el("p", { className: "meta", text: "Esta aplicación todavía no está desplegada." }),
        el("div", { className: "actions" }, edit, del)));
  }

  function showEdit(app) {
    clear(body);
    const card = el("section", { className: "card card-form", attrs: { "aria-labelledby": "edit-title" } });
    card.append(el("h1", { text: "Editar aplicación", attrs: { id: "edit-title", tabindex: "-1" } }));
    const form = el("form", { attrs: { novalidate: true } });
    const name = field({ id: "name", label: "Nombre", required: true, maxlength: NAME_MAX, value: app.name, autocomplete: "off" });
    const description = field({ id: "description", label: "Descripción (opcional)", textarea: true,
      maxlength: DESCRIPTION_MAX, value: app.description || "" });
    const counter = el("p", { className: "help counter", text: `${description.input.value.length}/${DESCRIPTION_MAX}`, attrs: { "aria-hidden": "true" } });
    description.wrap.insertBefore(counter, description.wrap.querySelector(".field-error"));
    description.input.addEventListener("input", () => {
      counter.textContent = `${description.input.value.length}/${DESCRIPTION_MAX}`;
    });
    const slugInfo = el("p", { className: "help" }, "Identificador: ", el("code", { text: app.slug }),
      " (no se puede cambiar).");
    const error = formError();
    const save = el("button", { text: "Guardar cambios", attrs: { type: "submit" } });
    const cancel = el("button", { className: "btn-secondary", text: "Cancelar", attrs: { type: "button" } });
    cancel.addEventListener("click", () => showView(app));
    form.append(name.wrap, slugInfo, description.wrap, error.node, el("div", { className: "actions" }, save, cancel));
    card.append(form);
    body.append(card);
    name.input.focus();

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      name.clearError(); description.clearError(); error.clear();
      const nameValue = name.input.value.trim();
      if (!nameValue) { name.setError("El nombre es obligatorio."); name.input.focus(); return; }
      if (nameValue.length > NAME_MAX) { name.setError(`El nombre admite como máximo ${NAME_MAX} caracteres.`); name.input.focus(); return; }
      if (description.input.value.length > DESCRIPTION_MAX) {
        description.setError(`La descripción admite como máximo ${DESCRIPTION_MAX} caracteres.`);
        description.input.focus();
        return;
      }
      setBusy(save, true, "Guardando…", "Guardar cambios");
      try {
        const updated = await api.patch(path, { name: nameValue, description: description.input.value });
        if (!ctx.isCurrent()) return;
        toast("Cambios guardados.");
        showView(updated);
        body.querySelector("h1").focus();
      } catch (e) {
        if (!ctx.isCurrent() || isUnauthorized(e)) return;
        if (e instanceof ApiError && e.status === 404) { load(); return; }
        if (e instanceof ApiError && e.status === 422) {
          const general = applyValidationErrors(e, { name, description });
          if (general.length) error.set(general.join(" "));
        } else {
          error.set(errorMessage(e));
        }
      } finally {
        if (save.isConnected) setBusy(save, false, "Guardando…", "Guardar cambios");
      }
    });
  }

  // Confirmación con <dialog> modal: el navegador gestiona foco y tecla Escape.
  function confirmDelete(app, opener) {
    const dialog = el("dialog", { className: "dialog", attrs: { "aria-labelledby": "del-title" } });
    const error = formError();
    const confirm = el("button", { className: "btn-danger", text: "Eliminar", attrs: { type: "button" } });
    const cancel = el("button", { className: "btn-secondary", text: "Cancelar", attrs: { type: "button" } });
    dialog.append(
      el("h2", { text: `¿Eliminar «${app.name}»?`, attrs: { id: "del-title" } }),
      el("p", { text: "Esta acción no se puede deshacer." }),
      error.node,
      el("div", { className: "actions" }, confirm, cancel));
    document.body.append(dialog);
    dialog.addEventListener("close", () => { dialog.remove(); if (opener.isConnected) opener.focus(); });
    cancel.addEventListener("click", () => dialog.close());
    confirm.addEventListener("click", async () => {
      error.clear();
      setBusy(confirm, true, "Eliminando…", "Eliminar");
      try {
        await api.del(path);
        dialog.close();
        toast(`Aplicación «${app.name}» eliminada.`);
        location.hash = "#/apps";
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) { dialog.close(); location.hash = "#/apps"; return; }
        if (isUnauthorized(e)) { dialog.close(); return; }
        error.set(errorMessage(e));
        setBusy(confirm, false, "Eliminando…", "Eliminar");
      }
    });
    dialog.showModal();
    cancel.focus();
  }

  load();
}
