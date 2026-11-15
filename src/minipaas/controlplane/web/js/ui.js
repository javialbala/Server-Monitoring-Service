// Piezas de interfaz compartidas: avisos (toasts), campos de formulario y
// traducción de errores de la API a mensajes por campo.

import { el, clear } from "./dom.js";
import { ApiError } from "./api.js";

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

export { clear };
