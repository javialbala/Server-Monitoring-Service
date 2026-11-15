// Arranque, router por hash y cabecera.
//
// Flujo: boot() -> route(). route() pregunta SIEMPRE al servidor por la sesión
// (GET /api/auth/session) si no la tiene confirmada, y solo entonces pinta una
// vista privada. Cualquier 401 posterior de la API llama a onUnauthorized().

import { clear } from "./dom.js";
import { setUnauthorizedHandler, errorMessage } from "./api.js";
import * as session from "./session.js";
import { errorBox, toast } from "./ui.js";
import * as login from "./views/login.js";
import * as apps from "./views/apps.js";
import * as appForm from "./views/app-form.js";
import * as appDetail from "./views/app-detail.js";
import * as status from "./views/status.js";

const root = document.getElementById("view");
const nav = document.getElementById("main-nav");
const userArea = document.getElementById("user-area");
const userName = document.getElementById("user-name");
let renderId = 0; // invalida respuestas asíncronas de vistas ya abandonadas

// Tabla de rutas: patrón -> vista, sección del menú y título.
const ROUTES = [
  { re: /^#\/login$/, view: login, title: "Iniciar sesión", public: true },
  { re: /^#\/apps$/, view: apps, title: "Aplicaciones", nav: "apps" },
  { re: /^#\/apps\/new$/, view: appForm, title: "Nueva aplicación", nav: "apps" },
  { re: /^#\/apps\/([^/]+)$/, view: appDetail, title: "Aplicación", nav: "apps", param: "slug" },
  { re: /^#\/status$/, view: status, title: "Estado del sistema", nav: "status" },
];

function match(hash) {
  for (const route of ROUTES) {
    const m = route.re.exec(hash);
    if (m) {
      let params = {};
      if (route.param) {
        try { params = { [route.param]: decodeURIComponent(m[1]) }; } catch (e) { return null; }
      }
      return { route, params };
    }
  }
  return null;
}

function renderHeader(section) {
  const logged = session.state.authenticated;
  nav.hidden = !logged;
  userArea.hidden = !logged;
  userName.textContent = logged && session.state.user ? session.state.user.username : "";
  for (const link of nav.querySelectorAll("a")) {
    if (logged && link.dataset.nav === section) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

async function route() {
  const id = ++renderId;
  const current = () => id === renderId;
  const hash = location.hash || "#/apps";
  const found = match(hash);
  if (!found) { location.replace("#/apps"); return; }
  const { route: r, params } = found;

  // La pantalla de login siempre refresca la sesión (puede cambiar setup_required).
  if (!session.state.loaded || r.public) {
    try {
      await session.load();
    } catch (e) {
      if (!current()) return;
      renderHeader(null);
      clear(root);
      root.append(errorBox(errorMessage(e), route));
      return;
    }
    if (!current()) return;
  }

  if (!session.state.authenticated) {
    if (!r.public) {
      session.setReturnTo(hash);
      location.replace("#/login");
      return;
    }
  } else if (r.public) {
    location.replace(session.takeReturnTo() || "#/apps");
    return;
  }

  renderHeader(r.nav);
  document.title = r.title + " · MiniPaaS";
  clear(root);
  r.view.render(root, { params, isCurrent: current });
  // Foco en el título de la vista para lectores de pantalla y teclado.
  const heading = root.querySelector("h1");
  if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); }
}

// 401 desde cualquier llamada: limpiar estado en memoria e ir al login.
function onUnauthorized() {
  const wasAuthenticated = session.state.authenticated;
  session.clear();
  if (wasAuthenticated) {
    session.setNotice("Tu sesión ha caducado. Vuelve a iniciar sesión.");
    const hash = location.hash;
    if (hash && hash !== "#/login") session.setReturnTo(hash);
  }
  renderHeader(null);
  if (location.hash === "#/login") route(); else location.hash = "#/login";
}

document.getElementById("logout").addEventListener("click", async () => {
  try {
    await session.logout();
  } catch (e) {
    // Aunque falle la petición, el estado local ya se ha limpiado.
  }
  toast("Has cerrado la sesión.");
  if (location.hash === "#/login") route(); else location.hash = "#/login";
});

setUnauthorizedHandler(onUnauthorized);
window.addEventListener("hashchange", route);
route();
