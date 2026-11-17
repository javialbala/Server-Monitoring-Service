// Estado de sesión solo en memoria; la fuente de verdad es el servidor.

import { api, setCsrfToken } from "./api.js";

export const state = { authenticated: false };

let notice = null;

function apply(data) {
  state.authenticated = data.authenticated === true;
  setCsrfToken(data.csrf_token);
}

export async function load() {
  apply(await api.get("/api/session", { skipAuthHandling: true }));
}

export async function login(password) {
  await api.post("/api/login", { password }, { skipAuthHandling: true });
  await load(); // el login no devuelve cuerpo: se pide la sesión para obtener el token CSRF
}

export async function logout() {
  try {
    await api.post("/api/logout", undefined, { skipAuthHandling: true });
  } finally {
    clear();
  }
}

export function clear() {
  state.authenticated = false;
  setCsrfToken(null);
}

export function setNotice(message) { notice = message; }
export function takeNotice() { const n = notice; notice = null; return n; }
