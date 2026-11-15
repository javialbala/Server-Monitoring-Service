// Detalle de una aplicación: centro de gestión. Esta vista solo orquesta;
// cada sección vive en su propio módulo:
//   app-header.js (estado y acciones), app-services.js + service-form.js,
//   app-runtime.js (estado real), app-deployments.js (historial),
//   app-deploy.js (flujo de despliegue y sondeo de progreso).

import { el, clear } from "../dom.js";
import { api, ApiError, isUnauthorized, errorMessage } from "../api.js";
import { DESCRIPTION_MAX, NAME_MAX } from "../format.js";
import { field, formError, setBusy, applyValidationErrors, loadingBox, errorBox, toast, confirmDialog, operationError } from "../ui.js";
import { IN_PROGRESS } from "../tones.js";
import { renderHeader } from "./app-header.js";
import { mount as mountServices } from "./app-services.js";
import { mount as mountRuntime } from "./app-runtime.js";
import { mount as mountDeployments } from "./app-deployments.js";
import { createDeployFlow } from "./app-deploy.js";

const ACTIONS = {
  stop: { done: "Aplicación detenida." },
  start: { done: "Aplicación en marcha." },
  recover: { done: "Aplicación recuperada." },
};

export function render(root, ctx) {
  const slug = ctx.params.slug;
  const path = "/api/applications/" + encodeURIComponent(slug);
  const body = el("div");
  root.append(body);

  // Estado de la vista (solo en memoria).
  let app = null;
  let serviceCount = null;
  let deploying = false;
  let busyAction = null;
  let actionError = "";

  let dashboard, headBox, progressBox, servicesBox, runtimeBox, deploymentsBox;
  let services, runtime, deployments, flow;

  async function load() {
    clear(body);
    body.append(loadingBox("Cargando aplicación…"));
    try {
      app = await api.get(path);
      if (!ctx.isCurrent()) return;
      buildDashboard();
      reloadAll(false);
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

  function drawHeader() {
    renderHeader(headBox, { app, serviceCount, deploying, busyAction, error: actionError }, {
      onDeploy: () => { actionError = ""; flow.start(); },
      onAction: runAction,
      onEdit: () => showEdit(),
      onDelete: (button) => confirmDelete(button),
    });
  }

  function buildDashboard() {
    clear(body);
    dashboard = el("div");
    headBox = el("div");
    progressBox = el("div");
    servicesBox = el("section", { className: "card", attrs: { "aria-label": "Servicios" } });
    runtimeBox = el("section", { className: "card", attrs: { "aria-label": "Estado real" } });
    deploymentsBox = el("section", { className: "card", attrs: { "aria-label": "Historial de despliegues" } });
    dashboard.append(
      el("p", {}, el("a", { text: "← Aplicaciones", attrs: { href: "#/apps" } })),
      el("div", { className: "sections" }, headBox, progressBox, servicesBox, runtimeBox, deploymentsBox));
    body.append(dashboard);

    services = mountServices(servicesBox, { ctx, path, onChange: (items) => { serviceCount = items.length; drawHeader(); } });
    runtime = mountRuntime(runtimeBox, { ctx, path });
    deployments = mountDeployments(deploymentsBox, { ctx, path });
    flow = createDeployFlow({
      ctx, path, panel: progressBox,
      onBusyChange: (value) => { deploying = value; drawHeader(); },
      onFinished: () => reloadAll(true),
    });
    drawHeader();
  }

  // Recarga aplicación, servicios, estado real e historial. Si hay una
  // operación en curso y no la seguimos, se localiza en el historial.
  async function reloadAll(refreshApp) {
    const appPromise = refreshApp
      ? api.get(path).then((a) => { if (ctx.isCurrent()) { app = a; drawHeader(); } }).catch((e) => {
        if (ctx.isCurrent() && e instanceof ApiError && e.status === 404) load();
      })
      : Promise.resolve();
    const [, , , items] = await Promise.all([appPromise, services.reload(), runtime.reload(), deployments.reload()]);
    if (!ctx.isCurrent() || !app) return;
    if (app.operation_in_progress && !flow.busy && items) {
      const running = items.find((d) => IN_PROGRESS.has(d.status));
      if (running) flow.follow(running.revision);
    }
  }

  // Detener / Arrancar / Recuperar: peticiones síncronas que pueden tardar.
  async function runAction(kind) {
    busyAction = kind; actionError = ""; drawHeader();
    try {
      app = await api.post(`${path}/${kind}`);
      if (!ctx.isCurrent()) return;
      toast(ACTIONS[kind].done);
    } catch (e) {
      if (!ctx.isCurrent() || isUnauthorized(e)) return;
      actionError = operationError(e);
    }
    busyAction = null;
    drawHeader();
    await reloadAll(true);
  }

  function confirmDelete(opener) {
    confirmDialog({
      title: `¿Eliminar «${app.name}»?`,
      text: "Se detendrán y eliminarán sus servicios en ejecución. Esta acción no se puede deshacer.",
      confirmLabel: "Eliminar", busyLabel: "Eliminando…", opener,
      action: async () => {
        try {
          await api.del(path);
        } catch (e) {
          if (!(e instanceof ApiError && e.status === 404)) throw e;
        }
        if (flow) flow.stop();
        toast(`Aplicación «${app.name}» eliminada.`);
        location.hash = "#/apps";
      },
    });
  }

  // Edición de nombre y descripción: sustituye temporalmente el panel.
  function showEdit() {
    dashboard.hidden = true;
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
    const slugInfo = el("p", { className: "help" }, "Identificador: ", el("code", { text: app.slug }), " (no se puede cambiar).");
    const error = formError();
    const save = el("button", { text: "Guardar cambios", attrs: { type: "submit" } });
    const cancel = el("button", { className: "btn-secondary", text: "Cancelar", attrs: { type: "button" } });
    const close = () => { card.remove(); dashboard.hidden = false; drawHeader(); body.querySelector("h1").focus(); };
    cancel.addEventListener("click", close);
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
        app = await api.patch(path, { name: nameValue, description: description.input.value });
        if (!ctx.isCurrent()) return;
        toast("Cambios guardados.");
        close();
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

  load();
}
