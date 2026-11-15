// Cliente de la API. Centraliza JSON, cabecera CSRF y el manejo del 401.
// El token CSRF vive solo en memoria (nunca en localStorage/sessionStorage).

let csrfToken = null;
let unauthorizedHandler = null;

export class ApiError extends Error {
  constructor(status, detail, { fields = [], retryAfter = null } = {}) {
    super(typeof detail === "string" ? detail : "Error");
    this.status = status;
    this.detail = detail;
    this.fields = fields; // [{field, message}] de los 422 de validación
    this.retryAfter = retryAfter; // segundos (cabecera Retry-After) o null
  }
}

export class NetworkError extends Error {}

export function setCsrfToken(token) {
  csrfToken = token || null;
}

// app.js registra qué hacer ante un 401 (limpiar sesión e ir al login).
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

export function isUnauthorized(error) {
  return error instanceof ApiError && error.status === 401;
}

export function errorMessage(error) {
  if (error instanceof NetworkError) return "No se puede conectar con MiniPaaS";
  if (error instanceof ApiError && typeof error.detail === "string") return error.detail;
  return "Ha ocurrido un error inesperado. Inténtalo de nuevo.";
}

// FastAPI devuelve en 422 una lista [{loc: ["body","campo"], msg}].
function parseValidation(detail) {
  if (!Array.isArray(detail)) return [];
  return detail.map((item) => {
    const loc = Array.isArray(item.loc) ? item.loc : [];
    return { field: String(loc[loc.length - 1] ?? ""), message: String(item.msg ?? "Valor no válido") };
  });
}

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

  const detail = data && data.detail !== undefined ? data.detail : "Error del servidor";
  const retry = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
  const error = new ApiError(response.status, detail, {
    fields: response.status === 422 ? parseValidation(detail) : [],
    retryAfter: Number.isFinite(retry) ? retry : null,
  });

  if (response.status === 401 && !skipAuthHandling && unauthorizedHandler) {
    unauthorizedHandler();
  }
  if (response.status === 403) {
    // Token CSRF caducado: pedimos uno nuevo al servidor para el siguiente intento.
    await refreshCsrf();
    error.detail = "No se pudo completar la operación. Inténtalo de nuevo.";
    error.message = error.detail;
  }
  throw error;
}

async function refreshCsrf() {
  try {
    const data = await request("GET", "/api/auth/session", { skipAuthHandling: true });
    setCsrfToken(data.csrf_token);
    if (!data.authenticated && unauthorizedHandler) unauthorizedHandler();
  } catch (cause) {
    // Si tampoco responde la sesión, el error original ya informa al usuario.
  }
}

export const api = {
  get: (path, opts) => request("GET", path, opts),
  post: (path, body, opts) => request("POST", path, { ...opts, body }),
  patch: (path, body, opts) => request("PATCH", path, { ...opts, body }),
  del: (path, opts) => request("DELETE", path, opts),
};
