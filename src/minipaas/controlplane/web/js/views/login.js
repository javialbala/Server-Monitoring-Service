// Pantalla de inicio de sesión.

import { el } from "../dom.js";
import * as session from "../session.js";
import { ApiError, NetworkError, errorMessage } from "../api.js";
import { field, formError, setBusy } from "../ui.js";

const CREATE_ADMIN_COMMAND =
  "docker compose --env-file deploy/.env -f deploy/compose.dev.yaml exec controlplane python -m minipaas.controlplane.manage create-admin --username admin";

export function render(root) {
  const card = el("section", { className: "card card-narrow", attrs: { "aria-labelledby": "login-title" } });
  card.append(el("h1", { text: "Iniciar sesión", attrs: { id: "login-title", tabindex: "-1" } }));

  const noticeText = session.takeNotice();
  if (noticeText) card.append(el("p", { className: "notice notice-info", text: noticeText, attrs: { role: "status" } }));

  if (session.state.setupRequired) {
    card.append(el("div", { className: "notice notice-info" },
      el("p", { text: "Todavía no existe ningún administrador. Créalo desde la terminal del servidor:" }),
      el("pre", { className: "command" }, el("code", { text: CREATE_ADMIN_COMMAND }))));
  }

  const form = el("form", { attrs: { novalidate: true } });
  const username = field({ id: "username", label: "Usuario", required: true, autocomplete: "username" });
  const password = field({ id: "password", label: "Contraseña", type: "password", required: true,
    autocomplete: "current-password" });
  const error = formError();
  const submit = el("button", { text: "Entrar", attrs: { type: "submit" } });
  form.append(username.wrap, password.wrap, error.node, submit);
  card.append(form);
  root.append(card);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.clear(); username.clearError(); password.clearError();
    const user = username.input.value.trim();
    const pass = password.input.value;
    let invalid = null;
    if (!user) { username.setError("Escribe tu usuario."); invalid = username; }
    if (!pass) { password.setError("Escribe tu contraseña."); invalid = invalid || password; }
    if (invalid) { invalid.input.focus(); return; }

    setBusy(submit, true, "Entrando…", "Entrar");
    try {
      await session.login(user, pass);
      // Ruta pedida originalmente, o la lista de aplicaciones.
      location.hash = session.takeReturnTo() || "#/apps";
    } catch (e) {
      let message = errorMessage(e);
      if (e instanceof ApiError && e.status === 429 && e.retryAfter) {
        const minutes = Math.max(1, Math.ceil(e.retryAfter / 60));
        message += ` Podrás intentarlo en ${minutes} ${minutes === 1 ? "minuto" : "minutos"}.`;
      } else if (e instanceof ApiError && e.status === 422) {
        message = "Revisa los datos introducidos.";
      }
      error.set(message);
      password.input.value = ""; // el usuario se conserva; la contraseña no
      password.input.focus();
    } finally {
      if (submit.isConnected) setBusy(submit, false, "Entrando…", "Entrar");
    }
  });
}
