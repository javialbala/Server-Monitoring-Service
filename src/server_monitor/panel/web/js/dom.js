// Construcción de DOM sin innerHTML: el texto entra siempre por textContent.

const SVG_NS = "http://www.w3.org/2000/svg";

export function el(tag, { className, text, attrs } = {}, ...children) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  setAttrs(node, attrs);
  for (const child of children) if (child) node.append(child);
  return node;
}

export function svg(tag, attrs, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  setAttrs(node, attrs);
  for (const child of children) if (child) node.append(child);
  return node;
}

export function icon(name, className = "icon") {
  return svg("svg", { class: className, "aria-hidden": "true" }, svg("use", { href: `/icons.svg#${name}` }));
}

function setAttrs(node, attrs) {
  if (!attrs) return;
  for (const [name, value] of Object.entries(attrs)) {
    if (value === false || value === null || value === undefined) continue;
    node.setAttribute(name, value === true ? "" : String(value));
  }
}

export function clear(node) {
  node.replaceChildren();
}
