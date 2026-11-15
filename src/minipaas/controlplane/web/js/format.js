// Formato de fechas y reglas de identificador (slug), espejo de las del servidor.

const dateFormat = new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short" });

export function formatDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "fecha desconocida" : dateFormat.format(date);
}

export const SLUG_PATTERN = /^[a-z][a-z0-9-]{1,38}[a-z0-9]$/;
export const NAME_MAX = 100;
export const DESCRIPTION_MAX = 500;

// Misma regla que el servidor: minúsculas, sin acentos, todo lo no alfanumérico
// pasa a "-", guiones colapsados y recortados, máximo 40 caracteres.
export function slugify(name) {
  return name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40)
    .replace(/-+$/g, "");
}

export function isValidSlug(slug) {
  return SLUG_PATTERN.test(slug) && !slug.includes("--");
}
