// Helpers para construir DOM de forma segura: todo texto entra por textContent,
// nunca como HTML, así que los datos del servidor no pueden inyectar marcado.

export function el(tag, { className, text, attrs } = {}, ...children) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  if (attrs) {
    for (const [name, value] of Object.entries(attrs)) {
      if (value === false || value === null || value === undefined) continue;
      node.setAttribute(name, value === true ? "" : String(value));
    }
  }
  for (const child of children) if (child) node.append(child);
  return node;
}

export function clear(node) {
  node.replaceChildren();
}
