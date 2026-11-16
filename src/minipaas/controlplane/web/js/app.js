// Arranque: pregunta al servidor si hay sesión y muestra el login o el panel.

import { clear, el } from "./dom.js";
import { setUnauthorizedHandler, errorMessage } from "./api.js";
import * as session from "./session.js";
import * as login from "./views/login.js";
import * as dashboard from "./views/dashboard.js";

const root = document.getElementById("view");
const userArea = document.getElementById("user-area");
let stopDashboard = null; // función que detiene la actualización periódica

function showLogin() {
  if (stopDashboard) { stopDashboard(); stopDashboard = null; }
  userArea.hidden = true;
  clear(root);
  login.render(root, showDashboard);
}

function showDashboard() {
  userArea.hidden = false;
  clear(root);
  stopDashboard = dashboard.render(root);
}

// 401 desde cualquier llamada: la sesión ha caducado.
setUnauthorizedHandler(() => {
  session.clear();
  session.setNotice("Tu sesión ha caducado. Vuelve a iniciar sesión.");
  showLogin();
});

document.getElementById("logout").addEventListener("click", async () => {
  try {
    await session.logout();
  } catch (e) {
    // Aunque falle la petición, el estado local ya se ha limpiado.
  }
  showLogin();
});

(async () => {
  try {
    await session.load();
  } catch (e) {
    root.append(el("p", { className: "notice notice-error", text: errorMessage(e), attrs: { role: "alert" } }));
    return;
  }
  if (session.state.authenticated) showDashboard(); else showLogin();
})();
