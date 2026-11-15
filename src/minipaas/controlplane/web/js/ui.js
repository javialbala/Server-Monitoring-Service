// Piezas de interfaz compartidas: avisos (toasts), campos de formulario y
// traducción de errores de la API a mensajes por campo.

import { el, clear } from "./dom.js";
import { ApiError, isUnauthorized, errorMessage } from "./api.js";

// Avisos temporales en una región role="status" que ya existe en index.html.
export function toast(message) {
  const region = document.getElementById("toasts");
  const item = el("p", { className: "toast", text: message });
  region.append(item);
  setTimeout(() => item.remove(), 6000);
}

// Campo con etiqueta, ayuda opcional y mensaje de error asociado por aria-describedby.
export function field({ id, label, type = "text", textarea = false, required = false,
  autocomplete, maxlength, rows = 4, help, value = "", placeholder }) {
  const wrap = el("div", { className: "field" });
  const labelEl = el("label", { attrs: { for: id }, text: label });
  const input = el(textarea ? "textarea" : "input", {
    className: "input",
    attrs: { id, name: id, type: textarea ? false : type, required, autocomplete,
      maxlength, rows: textarea ? rows : false, placeholder },
  });
  input.value = value;
  const errorEl = el("p", { className: "field-error", attrs: { id: id + "-error", "aria-live": "polite" } });
  const describedBy = [];
  wrap.append(labelEl, input);
  if (help) {
    const helpEl = el("p", { className: "help", attrs: { id: id + "-help" }, text: help });
    wrap.append(helpEl);
    describedBy.push(helpEl.id);
  }
  wrap.append(errorEl);
  describedBy.push(errorEl.id);
  input.setAttribute("aria-describedby", describedBy.join(" "));

  return {
    wrap, input, labelEl,
    setError(message) {
      errorEl.textContent = message;
      input.setAttribute("aria-invalid", "true");
    },
    clearError() {
      errorEl.textContent = "";
      input.removeAttribute("aria-invalid");
    },
  };
}

// Zona de error general del formulario (role="alert", existe antes de usarse).
export function formError() {
  const node = el("p", { className: "form-error", attrs: { role: "alert" } });
  return { node, set: (m) => { node.textContent = m; }, clear: () => { node.textContent = ""; } };
}

// Pone/quita el estado de carga de un botón de envío.
export function setBusy(button, busy, busyText, idleText) {
  button.disabled = busy;
  button.textContent = busy ? busyText : idleText;
  if (busy) button.setAttribute("aria-busy", "true"); else button.removeAttribute("aria-busy");
}

// Reparte los errores 422 entre campos conocidos; devuelve los que no encajan.
// fields: {nombreCampo: objetoField}
export function applyValidationErrors(error, fields) {
  const general = [];
  if (!(error instanceof ApiError)) return general;
  for (const { field: name, message } of error.fields) {
    if (fields[name]) fields[name].setError(message); else general.push(message);
  }
  return general;
}

export function loadingBox(text) {
  return el("p", { className: "muted loading", text, attrs: { role: "status" } });
}

export function errorBox(message, onRetry) {
  const box = el("div", { className: "notice notice-error" });
  box.append(el("p", { text: message, attrs: { role: "alert" } }));
  if (onRetry) {
    const retry = el("button", { className: "btn-secondary", text: "Reintentar", attrs: { type: "button" } });
    retry.addEventListener("click", onRetry);
    box.append(retry);
  }
  return box;
}

// Insignia con color según el "tono" (neutral, ok, warn, err, crit, progress).
export function toneBadge(text, tone) {
  const safe = /^[a-z]+$/.test(String(tone)) ? tone : "neutral";
  return el("span", { className: "badge tone-" + safe, text });
}

// Mensaje de error de una operación sobre la aplicación (503: agente caído).
export function operationError(error) {
  if (error instanceof ApiError && error.status === 503) return "No se puede contactar con el agente.";
  return errorMessage(error);
}

// Confirmación con <dialog> modal: el navegador gestiona foco y tecla Escape.
// action() es asíncrona; si lanza, se muestra el error dentro del diálogo.
export function confirmDialog({ title, text, confirmLabel, busyLabel, opener, action }) {
  const dialog = el("dialog", { className: "dialog", attrs: { "aria-labelledby": "dialog-title" } });
  const error = formError();
  const confirm = el("button", { className: "btn-danger", text: confirmLabel, attrs: { type: "button" } });
  const cancel = el("button", { className: "btn-secondary", text: "Cancelar", attrs: { type: "button" } });
  dialog.append(
    el("h2", { text: title, attrs: { id: "dialog-title" } }),
    el("p", { text }),
    error.node,
    el("div", { className: "actions" }, confirm, cancel));
  document.body.append(dialog);
  dialog.addEventListener("close", () => { dialog.remove(); if (opener && opener.isConnected) opener.focus(); });
  cancel.addEventListener("click", () => dialog.close());
  confirm.addEventListener("click", async () => {
    error.clear();
    setBusy(confirm, true, busyLabel, confirmLabel);
    try {
      await action();
      dialog.close();
    } catch (e) {
      if (isUnauthorized(e)) { dialog.close(); return; }
      error.set(operationError(e));
      setBusy(confirm, false, busyLabel, confirmLabel);
    }
  });
  dialog.showModal();
  cancel.focus();
}

export { clear };
