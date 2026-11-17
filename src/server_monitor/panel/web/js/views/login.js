// Pantalla de inicio de sesión.

import { el, icon } from "../dom.js";
import * as session from "../session.js";
import { ApiError, errorMessage } from "../api.js";

export function render(root, onLogin) {
  const card = el("section", { className: "login-card", attrs: { "aria-labelledby": "login-title" } });
  card.append(
    el("div", { className: "login-brand" },
      icon("logo", "login-mark"),
      el("p", { className: "login-product", text: "Server Monitoring Service" })),
    el("h1", { className: "login-title", text: "Iniciar sesión", attrs: { id: "login-title" } }),
    el("p", { className: "login-hint", text: "Introduce la contraseña del panel para ver el estado del servidor." }),
  );

  const noticeText = session.takeNotice();
  if (noticeText) {
    card.append(el("p", { className: "notice", attrs: { role: "status" } }, icon("circle-alert"), el("span", { text: noticeText })));
  }

  const label = el("label", { className: "field-label", text: "Contraseña", attrs: { for: "password" } });
  const input = el("input", {
    className: "input",
    attrs: { id: "password", name: "password", type: "password", required: true, autocomplete: "current-password" },
  });
  const field = el("div", { className: "input-wrap" }, icon("lock-keyhole", "icon input-icon"), input);
  const error = el("p", { className: "form-error", attrs: { role: "alert" } });
  const submit = el("button", { className: "btn btn-primary btn-block", text: "Entrar", attrs: { type: "submit" } });
  const form = el("form", { className: "login-form", attrs: { novalidate: true } },
    el("div", { className: "field" }, label, field), error, submit);
  card.append(form);
  root.append(el("div", { className: "login-screen" }, card));
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
    submit.textContent = "Comprobando…";
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
      submit.textContent = "Entrar";
    }
  });
}
