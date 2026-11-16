// Pantalla de inicio de sesión: un único campo de contraseña.

import { el } from "../dom.js";
import * as session from "../session.js";
import { ApiError, errorMessage } from "../api.js";

// onLogin: función que app.js ejecuta tras un login correcto.
export function render(root, onLogin) {
  const card = el("section", { className: "card card-narrow", attrs: { "aria-labelledby": "login-title" } });
  card.append(el("h1", { text: "Iniciar sesión", attrs: { id: "login-title" } }));

  const noticeText = session.takeNotice();
  if (noticeText) card.append(el("p", { className: "notice notice-info", text: noticeText, attrs: { role: "status" } }));

  const label = el("label", { text: "Contraseña", attrs: { for: "password" } });
  const input = el("input", {
    className: "input",
    attrs: { id: "password", name: "password", type: "password", required: true, autocomplete: "current-password" },
  });
  const error = el("p", { className: "form-error", attrs: { role: "alert" } });
  const submit = el("button", { text: "Entrar", attrs: { type: "submit" } });
  const form = el("form", { attrs: { novalidate: true } }, el("div", { className: "field" }, label, input), error, submit);
  card.append(form);
  root.append(card);
  input.focus();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    if (!input.value) {
      error.textContent = "Escribe tu contraseña.";
      input.focus();
      return;
    }
    submit.disabled = true;
    try {
      await session.login(input.value);
      onLogin();
    } catch (e) {
      let message = errorMessage(e);
      if (e instanceof ApiError && e.status === 429 && e.retryAfter) {
        const minutes = Math.max(1, Math.ceil(e.retryAfter / 60));
        message += ` Podrás intentarlo en ${minutes} ${minutes === 1 ? "minuto" : "minutos"}.`;
      }
      error.textContent = message;
      input.value = "";
      input.focus();
    } finally {
      submit.disabled = false;
    }
  });
}
