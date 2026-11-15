// Correspondencia entre estados que envía la API y el "tono" visual de la insignia.

export const APP_TONE = { draft: "neutral", running: "ok", stopped: "neutral", attention: "warn" };

export const RUNTIME_TONE = { running: "ok", exited: "neutral", dead: "err", restarting: "warn" };

export const DEPLOY_TONE = {
  preparing: "progress", deploying: "progress", rolling_back: "progress",
  healthy: "ok", stopped: "neutral", superseded: "neutral", discarded: "neutral",
  failed: "err", rolled_back: "err", rollback_failed: "crit", interrupted: "crit",
};

// Estados de un despliegue que todavía no han terminado.
export const IN_PROGRESS = new Set(["preparing", "deploying", "rolling_back"]);
