// Arranque: muestra el login o el panel según la sesión del servidor.

import { clear, el } from "./dom.js";
import { setUnauthorizedHandler, errorMessage } from "./api.js";
import * as session from "./session.js";
import * as login from "./views/login.js";
import * as dashboard from "./views/dashboard.js";

const root = document.getElementById("view");
const header = document.getElementById("app-header");
let stopDashboard = null;

function showLogin() {
  if (stopDashboard) { stopDashboard(); stopDashboard = null; }
  header.hidden = true;
  clear(root);
  login.render(root, showDashboard);
}

function showDashboard() {
  header.hidden = false;
  clear(root);
  stopDashboard = dashboard.render(root);
}

setUnauthorizedHandler(() => {
  session.clear();
  session.setNotice("Tu sesión ha caducado. Vuelve a iniciar sesión.");
  showLogin();
});

document.getElementById("logout").addEventListener("click", async () => {
  try {
    await session.logout();
  } catch {
    // el estado local ya se ha limpiado aunque falle la petición
  }
  showLogin();
});

(async () => {
  try {
    await session.load();
  } catch (e) {
    root.append(el("div", { className: "login-screen" },
      el("p", { className: "banner", text: errorMessage(e), attrs: { role: "alert" } })));
    return;
  }
  if (session.state.authenticated) showDashboard(); else showLogin();
})();
