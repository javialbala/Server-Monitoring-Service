// Estado de sesión SOLO en memoria. La fuente de verdad es siempre el servidor.

import { api, setCsrfToken } from "./api.js";

export const state = { authenticated: false };

let notice = null; // mensaje a mostrar una vez en el login

function apply(data) {
  state.authenticated = data.authenticated === true;
  setCsrfToken(data.csrf_token);
}

export async function load() {
  apply(await api.get("/api/session", { skipAuthHandling: true }));
}

export async function login(password) {
  await api.post("/api/login", { password }, { skipAuthHandling: true });
  await load(); // la respuesta del login no trae cuerpo: se pide la sesión (y su token CSRF)
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
