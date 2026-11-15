// Estado de sesión SOLO en memoria. La fuente de verdad es siempre el servidor:
// nada de esto se persiste y se recarga con GET /api/auth/session.

import { api, setCsrfToken } from "./api.js";

export const state = {
  loaded: false, // ¿ya preguntamos al servidor desde el último reinicio de estado?
  authenticated: false,
  setupRequired: false,
  user: null,
};

let notice = null; // mensaje a mostrar una vez en el login
let returnTo = null; // ruta que se pidió antes de ir al login

function apply(data) {
  state.loaded = true;
  state.authenticated = data.authenticated === true;
  state.setupRequired = data.setup_required === true;
  state.user = data.user || null;
  setCsrfToken(data.csrf_token);
}

export async function load() {
  apply(await api.get("/api/auth/session", { skipAuthHandling: true }));
}

export async function login(username, password) {
  // Un 401 aquí significa credenciales incorrectas, no sesión caducada.
  const data = await api.post("/api/auth/login", { username, password }, { skipAuthHandling: true });
  apply({ authenticated: true, setup_required: false, user: data.user, csrf_token: data.csrf_token });
}

export async function logout() {
  try {
    await api.post("/api/auth/logout", undefined, { skipAuthHandling: true });
  } finally {
    clear();
  }
}

export function clear() {
  state.loaded = false;
  state.authenticated = false;
  state.user = null;
  setCsrfToken(null);
}

export function setNotice(message) { notice = message; }
export function takeNotice() { const n = notice; notice = null; return n; }
export function setReturnTo(hash) { returnTo = hash; }
export function takeReturnTo() { const r = returnTo; returnTo = null; return r; }
