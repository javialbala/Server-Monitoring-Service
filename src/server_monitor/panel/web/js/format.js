// Formato de números, fechas, velocidades y puertos.

const dateFormat = new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short" });
const clockFormat = new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const shortClockFormat = new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", hour12: false });

export const NA = "No disponible";

export function formatDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateFormat.format(date);
}

export function formatTime(time) {
  return clockFormat.format(time);
}

export function formatClock(time) {
  return shortClockFormat.format(time);
}

const BYTE_UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];

export function formatBytes(bytes) {
  if (typeof bytes !== "number" || !Number.isFinite(bytes)) return "—";
  let value = bytes;
  let unit = 0;
  while (Math.abs(value) >= 1024 && unit < BYTE_UNITS.length - 1) { value /= 1024; unit += 1; }
  const decimals = unit === 0 ? 0 : value >= 100 ? 0 : 1;
  return `${value.toFixed(decimals)} ${BYTE_UNITS[unit]}`;
}

export function formatRate(bytesPerSecond) {
  return typeof bytesPerSecond === "number" ? `${formatBytes(bytesPerSecond)}/s` : "—";
}

// Sin decimales si el valor es redondo: "2 MiB/s"
export function formatRateAxis(bytesPerSecond) {
  if (!bytesPerSecond) return "0";
  return `${formatBytes(bytesPerSecond).replace(".0 ", " ")}/s`;
}

export function formatPercent(value) {
  return typeof value === "number" ? `${value.toFixed(1)} %` : "—";
}

export function formatUptime(seconds) {
  if (typeof seconds !== "number") return NA;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const parts = [];
  if (days) parts.push(`${days} d`);
  if (days || hours) parts.push(`${hours} h`);
  parts.push(`${minutes} min`);
  return parts.join(" ");
}

const ANY_ADDRESS = new Set(["", "0.0.0.0", "::"]);

// Agrupa la misma publicación en IPv4 e IPv6 ("5432 → 5432/tcp"); con IP concreta la indica; omite los no publicados.
export function formatPorts(ports) {
  const seen = new Set();
  const result = [];
  const published = ports
    .filter((p) => p.host_port)
    .sort((a, b) => a.container_port - b.container_port || a.host_port - b.host_port);
  for (const p of published) {
    const ip = p.host_ip ?? "";
    let host = String(p.host_port);
    if (!ANY_ADDRESS.has(ip)) host = ip.includes(":") ? `[${ip}]:${host}` : `${ip}:${host}`;
    const text = `${host} → ${p.container_port}/${p.protocol}`;
    if (!seen.has(text)) { seen.add(text); result.push(text); }
  }
  return result;
}
