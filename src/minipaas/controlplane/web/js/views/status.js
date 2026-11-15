// Estado del sistema: tres indicadores a partir de GET /api/health (público).

import { el } from "../dom.js";
import { api } from "../api.js";

const ITEMS = [["controlplane", "Control plane"], ["agent", "Agente"], ["docker", "Docker"]];

export function render(root, ctx) {
  const card = el("section", { className: "card card-narrow", attrs: { "aria-labelledby": "status-title" } });
  card.append(el("h1", { text: "Estado del sistema", attrs: { id: "status-title", tabindex: "-1" } }));

  const list = el("ul", { className: "indicators" });
  const refs = {};
  for (const [key, name] of ITEMS) {
    const dot = el("span", { className: "dot" });
    const state = el("span", { className: "state", text: "Comprobando…" });
    refs[key] = { dot, state };
    list.append(el("li", {}, dot, el("span", { className: "name", text: name }), state));
  }
  const button = el("button", { text: "Actualizar", attrs: { type: "button" } });
  card.append(list, button);
  root.append(card);

  function setIndicator(key, ok) {
    refs[key].dot.className = "dot " + (ok ? "ok" : "error");
    refs[key].state.textContent = ok ? "Funcionando" : "No disponible";
  }

  async function refresh() {
    button.disabled = true;
    try {
      const data = await api.get("/api/health");
      if (!ctx.isCurrent()) return;
      setIndicator("controlplane", true);
      setIndicator("agent", data.agent.reachable === true);
      setIndicator("docker", data.docker.reachable === true);
    } catch (e) {
      if (!ctx.isCurrent()) return;
      // Si el control plane no responde, no podemos saber nada del resto.
      for (const [key] of ITEMS) setIndicator(key, false);
    } finally {
      button.disabled = false;
    }
  }

  button.addEventListener("click", refresh);
  refresh();
}
