// Cliente de la API. Centraliza JSON, cabecera CSRF y el manejo del 401.
// El token CSRF vive solo en memoria (nunca en localStorage/sessionStorage).

let csrfToken = null;
let unauthorizedHandler = null;

export class ApiError extends Error {
  constructor(status, detail, retryAfter = null) {
    super(typeof detail === "string" ? detail : "Error");
    this.status = status;
    this.retryAfter = retryAfter; // segundos (cabecera Retry-After) o null
  }
}

export class NetworkError extends Error {}

export function setCsrfToken(token) {
  csrfToken = token || null;
}

// app.js registra qué hacer ante un 401 (parar el panel e ir al login).
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

export function isUnauthorized(error) {
  return error instanceof ApiError && error.status === 401;
}

export function errorMessage(error) {
  if (error instanceof NetworkError) return "No se puede conectar con MiniPaaS";
  if (error instanceof ApiError) return error.message;
  return "Ha ocurrido un error inesperado. Inténtalo de nuevo.";
}

// skipAuthHandling: el 401 del login significa "contraseña incorrecta", no "sesión caducada".
async function request(method, path, { body, skipAuthHandling = false } = {}) {
  const headers = { Accept: "application/json" };
  const options = { method, credentials: "same-origin", headers };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
    if (body !== undefined) options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(path, options);
  } catch (cause) {
    throw new NetworkError("network");
  }

  if (response.status === 204) return null;

  let data = null;
  try {
    data = await response.json();
  } catch (cause) {
    data = null; // cuerpo vacío o no JSON
  }
  if (response.ok) return data;

  const detail = data && typeof data.detail === "string" ? data.detail : "Error del servidor";
  const retry = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
  const error = new ApiError(response.status, detail, Number.isFinite(retry) ? retry : null);
  if (response.status === 401 && !skipAuthHandling && unauthorizedHandler) {
    unauthorizedHandler();
  }
  throw error;
}

export const api = {
  get: (path, opts) => request("GET", path, opts),
  post: (path, body, opts) => request("POST", path, { ...opts, body }),
};
