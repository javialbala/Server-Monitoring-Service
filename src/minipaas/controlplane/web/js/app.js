"use strict";

// Muestra un indicador como "Funcionando" (verde) o "No disponible" (rojo).
function setIndicator(name, ok) {
  const dot = document.getElementById("dot-" + name);
  const state = document.getElementById("state-" + name);
  dot.className = "dot " + (ok ? "ok" : "error");
  state.textContent = ok ? "Funcionando" : "No disponible";
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    setIndicator("controlplane", true);
    setIndicator("agent", data.agent.reachable === true);
    setIndicator("docker", data.docker.reachable === true);
  } catch (error) {
    // Si el control plane no responde, no podemos saber nada del resto.
    setIndicator("controlplane", false);
    setIndicator("agent", false);
    setIndicator("docker", false);
  }
}

document.getElementById("refresh").addEventListener("click", refreshStatus);
refreshStatus();
