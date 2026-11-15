// Flujo «Desplegar» y panel de progreso.
//
// 1) POST /revisions {request_id}  -> crea (o recupera) la revisión
// 2) POST /revisions/N/deploy      -> lanza el despliegue
// 3) GET  /deployments/N cada 2 s  -> SOLO mientras siga en curso
//
// El request_id se conserva entre intentos fallidos por red para que un
// reintento no cree una revisión duplicada. El sondeo se detiene al llegar a un
// estado final, al cambiar de vista (hashchange / ctx.isCurrent) o al fallar 401.

import { el, clear } from "../dom.js";
import { api, ApiError, NetworkError, isUnauthorized, errorMessage } from "../api.js";
import { toast, toneBadge } from "../ui.js";
import { DEPLOY_TONE, IN_PROGRESS } from "../tones.js";
import { eventsList } from "./app-deployments.js";

const POLL_MS = 2000;

// UUID v4; crypto.randomUUID solo existe en contextos seguros (https/localhost).
function newRequestId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

// opts: { ctx, path, panel (nodo), onBusyChange(bool), onFinished(deployment|null) }
export function createDeployFlow({ ctx, path, panel, onBusyChange, onFinished }) {
  let requestId = null; // vive mientras dure el intento
  let busy = false;
  let timer = null;
  let session = 0; // invalida sondeos antiguos

  const setBusy = (value) => { busy = value; onBusyChange(value); };

  function stopPolling() {
    session++;
    if (timer) { clearTimeout(timer); timer = null; }
    window.removeEventListener("hashchange", stopPolling);
  }

  // Panel: título, estado actual, aviso y últimos eventos.
  function showPanel({ title, deployment, note, errorText }) {
    clear(panel);
    const card = el("section", { className: "card", attrs: { "aria-labelledby": "deploy-progress-title" } });
    const head = el("div", { className: "section-head" }, el("h2", { text: title, attrs: { id: "deploy-progress-title" } }));
    if (deployment) head.append(toneBadge(deployment.status_label, DEPLOY_TONE[deployment.status] || "neutral"));
    card.append(head);
    const live = el("div", { attrs: { "aria-live": "polite" } });
    if (note) live.append(el("p", { className: "muted", text: note }));
    if (deployment && deployment.events && deployment.events.length) live.append(eventsList(deployment.events, 5));
    card.append(live);
    if (errorText) card.append(el("p", { className: "inline-error", text: errorText, attrs: { role: "alert" } }));
    panel.append(card);
  }

  function hidePanel() { clear(panel); }

  function finish(d) {
    stopPolling();
    setBusy(false);
    requestId = null;
    hidePanel();
    const n = d.revision;
    if (d.status === "healthy") toast(`Revisión ${n} desplegada y funcionando.`);
    else if (d.status === "rolled_back") toast(`La revisión ${n} falló; se ha recuperado la revisión anterior.`);
    else toast(`La revisión ${n} no se pudo desplegar${d.error ? ": " + d.error : "."}`);
    onFinished(d);
  }

  // Sondeo de la revisión `revision` (también se usa si ya había una en curso).
  function follow(revision) {
    stopPolling();
    const mine = session;
    setBusy(true);
    window.addEventListener("hashchange", stopPolling);
    showPanel({ title: `Desplegando la revisión ${revision}…`, note: "Esperando el estado del despliegue…" });
    const alive = () => mine === session && ctx.isCurrent();

    async function tick() {
      timer = null;
      if (!alive()) return;
      try {
        const d = await api.get(`${path}/deployments/${revision}`);
        if (!alive()) return;
        if (IN_PROGRESS.has(d.status)) {
          showPanel({ title: `Desplegando la revisión ${revision}…`, deployment: d });
          timer = setTimeout(tick, POLL_MS);
        } else {
          finish(d);
        }
      } catch (e) {
        if (!alive() || isUnauthorized(e)) return;
        if (e instanceof ApiError && e.status === 404) {
          stopPolling(); setBusy(false); hidePanel(); onFinished(null);
          return;
        }
        // Fallo puntual de red o servidor: se informa y se sigue intentando.
        showPanel({ title: `Desplegando la revisión ${revision}…`,
          note: "No se puede consultar el estado ahora mismo; se reintentará automáticamente." });
        timer = setTimeout(tick, POLL_MS);
      }
    }
    tick();
  }

  // Botón «Desplegar».
  async function start() {
    if (busy) return;
    setBusy(true);
    requestId = requestId || newRequestId();
    showPanel({ title: "Preparando el despliegue…", note: "Creando la revisión con los servicios actuales…" });
    let revision;
    try {
      const rev = await api.post(path + "/revisions", { request_id: requestId });
      revision = rev.revision;
      await api.post(`${path}/revisions/${revision}/deploy`);
    } catch (e) {
      if (!ctx.isCurrent() || isUnauthorized(e)) return;
      const network = e instanceof NetworkError;
      // Con fallo de red se conserva el request_id: el reintento no duplica revisión.
      if (!network) requestId = null;
      setBusy(false);
      showPanel({ title: "No se pudo desplegar",
        errorText: network ? "No se puede conectar con MiniPaaS. Pulsa «Desplegar» para reintentar."
          : (e instanceof ApiError && e.status === 503 ? "No se puede contactar con el agente." : errorMessage(e)) });
      if (e instanceof ApiError && e.status === 409) onFinished(null); // refresca el estado real de la app
      return;
    }
    if (!ctx.isCurrent()) return;
    follow(revision);
  }

  return { start, follow, stop: stopPolling, get busy() { return busy; } };
}
