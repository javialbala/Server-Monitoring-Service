// Formato de números, fechas y puertos para mostrar en pantalla.

const dateFormat = new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short" });

export function formatDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateFormat.format(date);
}

export function formatTime(date) {
  return date.toLocaleTimeString("es-ES", { hour12: false }); // HH:MM:SS
}

export function formatBytes(bytes) {
  if (typeof bytes !== "number") return "—";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function formatPercent(value) {
  return typeof value === "number" ? `${value.toFixed(1)} %` : "—";
}

// 93784 -> "1 d 2 h 3 min"
export function formatUptime(seconds) {
  if (typeof seconds !== "number") return "No disponible";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const parts = [];
  if (days) parts.push(`${days} d`);
  if (days || hours) parts.push(`${hours} h`);
  parts.push(`${minutes} min`);
  return parts.join(" ");
}

// "127.0.0.1:8096→8096/tcp" si está publicado, "8096/tcp" si no.
export function formatPort(port) {
  const inside = `${port.container_port}/${port.protocol}`;
  return port.host_port ? `${port.host_ip}:${port.host_port}→${inside}` : inside;
}
