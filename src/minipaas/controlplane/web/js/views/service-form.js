// Formulario de servicio (alta y edición). Solo ofrece lo que declara la
// entrada del catálogo: sin imagen libre, sin comandos, sin montajes.

import { el, clear } from "../dom.js";
import { api, ApiError, isUnauthorized, errorMessage } from "../api.js";
import { field, formError, setBusy, applyValidationErrors } from "../ui.js";

const NAME_RE = /^[a-z][a-z0-9-]{0,28}[a-z0-9]$/;
const HOST_PORT_MIN = 20000;
const HOST_PORT_MAX = 20999;

// Selector con etiqueta y errores, con la misma estructura que ui.field().
function selectField({ id, label, options, value }) {
  const wrap = el("div", { className: "field" });
  const select = el("select", { className: "input", attrs: { id, name: id, "aria-describedby": id + "-error" } });
  for (const o of options) select.append(el("option", { text: o.text, attrs: { value: o.value } }));
  select.value = value ?? "";
  const errorEl = el("p", { className: "field-error", attrs: { id: id + "-error", "aria-live": "polite" } });
  wrap.append(el("label", { attrs: { for: id }, text: label }), select, errorEl);
  return {
    wrap, input: select,
    setError(m) { errorEl.textContent = m; select.setAttribute("aria-invalid", "true"); },
    clearError() { errorEl.textContent = ""; select.removeAttribute("aria-invalid"); },
  };
}

function rangeText(r, unit) {
  return `Entre ${r.min} y ${r.max} ${unit} (por defecto ${r.default}).`;
}

function limitationsNode(item) {
  const lim = item.limitations;
  if (!lim || (Array.isArray(lim) && !lim.length)) return null;
  if (Array.isArray(lim)) return el("ul", { className: "limits" }, ...lim.map((l) => el("li", { text: String(l) })));
  return el("p", { className: "help", text: "Limitaciones: " + lim });
}

// ctx: { isCurrent } ; service: servicio existente (edición) o null (alta).
export function renderServiceForm(container, { ctx, path, catalog, service, onDone, onCancel }) {
  const editing = Boolean(service);
  const title = editing ? `Editar servicio «${service.name}»` : "Añadir servicio";
  const card = el("div");
  card.append(el("h2", { text: title, attrs: { id: "svc-form-title", tabindex: "-1" } }));
  container.append(card);

  const form = el("form", { attrs: { novalidate: true, "aria-labelledby": "svc-form-title" } });
  const error = formError();

  // Tipo de servicio
  let typeField = null;
  let current = null; // entrada del catálogo seleccionada
  const typeInfo = el("div");
  if (editing) {
    current = catalog.find((c) => c.id === service.catalog_id) || null;
    form.append(el("div", { className: "field" },
      el("label", { text: "Tipo de servicio" }),
      el("p", { className: "static-value", text: service.catalog_name }),
      el("p", { className: "help", text: "El tipo no se puede cambiar. Para usar otro, crea un servicio nuevo." })));
  } else {
    typeField = selectField({
      id: "svc-type", label: "Tipo de servicio",
      options: [{ value: "", text: "Elige un tipo de servicio…" },
        ...catalog.map((c) => ({ value: c.id, text: c.test_only && !c.name.includes("[Prueba]") ? `[Prueba] ${c.name}` : c.name }))],
    });
    form.append(typeField.wrap);
  }
  form.append(typeInfo);

  // Nombre
  const name = field({ id: "svc-name", label: "Nombre del servicio", required: !editing, maxlength: 30, autocomplete: "off",
    value: editing ? service.name : "",
    help: editing
      ? "El nombre no se puede cambiar."
      : "Otros servicios de la aplicación lo usarán como dirección interna, p. ej. http://<nombre>:<puerto>. Minúsculas, números y guiones; empieza por letra. No se puede cambiar después." });
  if (editing) name.input.disabled = true;
  form.append(name.wrap);

  const dyn = el("div"); // parte que depende del tipo elegido
  form.append(dyn);
  const submit = el("button", { text: editing ? "Guardar cambios" : "Añadir servicio", attrs: { type: "submit" } });
  const cancel = el("button", { className: "btn-secondary", text: "Cancelar", attrs: { type: "button" } });
  cancel.addEventListener("click", () => onCancel());
  const actions = el("div", { className: "actions" }, submit, cancel);
  form.append(error.node, actions);
  card.append(form);

  // Campos dependientes del tipo; se reconstruyen al cambiar la selección.
  let f = {};
  function buildDynamic(item) {
    clear(dyn); clear(typeInfo);
    f = {};
    if (!item) {
      if (editing) dyn.append(el("p", { className: "inline-error", text: "Este tipo de servicio ya no está en el catálogo." }));
      return;
    }
    const initial = editing ? service : null;
    typeInfo.append(el("p", { className: "help", text: item.description }),
      el("p", { className: "help", text: `Imagen: ${item.repository}:${item.version} · ${item.license}` }));
    const lim = limitationsNode(item);
    if (lim) typeInfo.append(lim);

    // Puerto interno
    if (item.internal_ports.length > 1) {
      f.internal_port = selectField({ id: "svc-port", label: "Puerto interno",
        options: item.internal_ports.map((p) => ({ value: String(p), text: String(p) })),
        value: String(initial ? initial.internal_port : item.default_internal_port) });
      dyn.append(f.internal_port.wrap);
    } else {
      dyn.append(el("div", { className: "field" }, el("label", { text: "Puerto interno" }),
        el("p", { className: "static-value", text: String(item.internal_ports[0]) })));
    }

    // Publicación
    if (item.publishable) {
      const box = el("input", { attrs: { type: "checkbox", id: "svc-publish", name: "svc-publish" } });
      box.checked = initial ? initial.publish : false;
      const publishWrap = el("div", { className: "field" },
        el("label", { className: "check" }, box, "Publicar para acceder desde el navegador"));
      f.publish = { input: box };
      f.host_port = field({ id: "svc-host-port", label: "Puerto de acceso (opcional)", type: "number",
        value: initial && initial.host_port != null ? String(initial.host_port) : "",
        help: `Entre ${HOST_PORT_MIN} y ${HOST_PORT_MAX}. Si lo dejas vacío, se asigna automáticamente.` });
      f.host_port.input.min = HOST_PORT_MIN; f.host_port.input.max = HOST_PORT_MAX; f.host_port.input.step = 1;
      const sync = () => { f.host_port.wrap.hidden = !box.checked; };
      box.addEventListener("change", sync);
      sync();
      dyn.append(publishWrap, f.host_port.wrap);
    }

    // Variables declaradas por la entrada
    f.env = {};
    if (item.env.length) {
      const set = el("fieldset", { className: "form-section" }, el("legend", { text: "Variables" }));
      for (const v of item.env) {
        const id = "svc-env-" + v.name.replace(/[^A-Za-z0-9_-]/g, "_");
        const fld = field({ id, label: v.label, maxlength: v.max_length, autocomplete: "off",
          help: v.help, value: initial && initial.env && initial.env[v.name] != null ? initial.env[v.name] : "" });
        f.env[v.name] = fld;
        set.append(fld.wrap);
      }
      dyn.append(set);
    }

    // Recursos
    f.memory_mb = field({ id: "svc-memory", label: "Memoria (MiB)", type: "number", required: true,
      value: String(initial ? initial.memory_mb : item.memory_mb.default), help: rangeText(item.memory_mb, "MiB") });
    f.memory_mb.input.min = item.memory_mb.min; f.memory_mb.input.max = item.memory_mb.max; f.memory_mb.input.step = 1;
    f.cpus = field({ id: "svc-cpus", label: "CPU (núcleos)", type: "number", required: true,
      value: String(initial ? initial.cpus : item.cpus.default), help: rangeText(item.cpus, "núcleos") });
    f.cpus.input.min = item.cpus.min; f.cpus.input.max = item.cpus.max; f.cpus.input.step = "any";
    dyn.append(f.memory_mb.wrap, f.cpus.wrap);
  }

  if (typeField) {
    typeField.input.addEventListener("change", () => {
      current = catalog.find((c) => c.id === typeField.input.value) || null;
      typeField.clearError();
      buildDynamic(current);
    });
  }
  buildDynamic(current);
  (editing ? (f.memory_mb || name) : typeField).input.focus();

  function allFields() {
    return [name, typeField, f.internal_port, f.host_port, f.memory_mb, f.cpus, ...Object.values(f.env || {})].filter(Boolean);
  }

  // Validación en el cliente (el servidor sigue siendo la autoridad).
  function validate() {
    let first = null;
    const fail = (fld, msg) => { fld.setError(msg); first = first || fld; };
    if (!editing) {
      if (!current) fail(typeField, "Elige un tipo de servicio.");
      const n = name.input.value.trim();
      if (!NAME_RE.test(n) || n.includes("--")) {
        fail(name, "Usa de 2 a 30 caracteres: minúsculas, números y guiones; empieza por letra, termina en letra o número y sin guiones dobles.");
      }
    }
    if (!current) return first;
    if (f.publish && f.publish.input.checked && f.host_port.input.value.trim() !== "") {
      const p = Number(f.host_port.input.value);
      if (!Number.isInteger(p) || p < HOST_PORT_MIN || p > HOST_PORT_MAX) {
        fail(f.host_port, `El puerto de acceso debe estar entre ${HOST_PORT_MIN} y ${HOST_PORT_MAX}.`);
      }
    }
    for (const v of current.env) {
      const value = f.env[v.name].input.value;
      if (value === "") continue;
      if (value.length > v.max_length) fail(f.env[v.name], `Admite como máximo ${v.max_length} caracteres.`);
      else {
        let ok = true;
        // El servidor exige que el valor COMPLETO cumpla el patrón (fullmatch): se ancla igual aquí.
        try { ok = new RegExp(`^(?:${v.pattern})$`).test(value); } catch (e) { ok = true; } // patrón no válido en JS: decide el servidor
        if (!ok) fail(f.env[v.name], "El valor no tiene un formato válido." + (v.help ? " " + v.help : ""));
      }
    }
    const mem = Number(f.memory_mb.input.value);
    if (f.memory_mb.input.value === "" || !Number.isInteger(mem) || mem < current.memory_mb.min || mem > current.memory_mb.max) {
      fail(f.memory_mb, rangeText(current.memory_mb, "MiB"));
    }
    const cpu = Number(f.cpus.input.value);
    if (f.cpus.input.value === "" || !Number.isFinite(cpu) || cpu < current.cpus.min || cpu > current.cpus.max) {
      fail(f.cpus, rangeText(current.cpus, "núcleos"));
    }
    return first;
  }

  function buildBody() {
    const body = {
      internal_port: f.internal_port ? Number(f.internal_port.input.value) : current.internal_ports[0],
      publish: f.publish ? f.publish.input.checked : false,
      env: {},
      memory_mb: Number(f.memory_mb.input.value),
      cpus: Number(f.cpus.input.value),
    };
    const hp = f.host_port && body.publish ? f.host_port.input.value.trim() : "";
    if (hp !== "") body.host_port = Number(hp);
    else if (editing) body.host_port = null;
    for (const v of current.env) {
      const value = f.env[v.name].input.value;
      if (value !== "") body.env[v.name] = value;
    }
    if (!editing) { body.name = name.input.value.trim(); body.catalog_id = current.id; }
    return body;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    for (const fld of allFields()) fld.clearError();
    error.clear();
    if (!current) {
      if (typeField) { typeField.setError("Elige un tipo de servicio."); typeField.input.focus(); }
      else error.set("Este tipo de servicio ya no está en el catálogo.");
      return;
    }
    const first = validate();
    if (first) { first.input.focus(); return; }
    const label = editing ? "Guardar cambios" : "Añadir servicio";
    setBusy(submit, true, "Guardando…", label);
    try {
      if (editing) await api.patch(`${path}/${encodeURIComponent(service.name)}`, buildBody());
      else await api.post(path, buildBody());
      if (!ctx.isCurrent()) return;
      await onDone();
    } catch (e) {
      if (!ctx.isCurrent() || isUnauthorized(e)) return;
      handleError(e);
    } finally {
      if (submit.isConnected) setBusy(submit, false, "Guardando…", label);
    }
  });

  // 422 por campo (lista o cadena) y 409 asociado a nombre o puerto.
  function handleError(e) {
    if (e instanceof ApiError && e.status === 409) {
      const target = /puerto/i.test(e.detail) && f.host_port ? f.host_port : (!editing ? name : null);
      if (target) { target.setError(errorMessage(e)); target.input.focus(); } else error.set(errorMessage(e));
      return;
    }
    if (e instanceof ApiError && e.status === 422) {
      if (typeof e.detail === "string") { error.set(e.detail); return; }
      const known = {
        name, catalog_id: typeField, internal_port: f.internal_port, host_port: f.host_port,
        memory_mb: f.memory_mb, cpus: f.cpus, ...(f.env || {}),
      };
      for (const k of Object.keys(known)) if (!known[k]) delete known[k];
      const general = applyValidationErrors(e, known);
      if (general.length) error.set(general.join(" "));
      else { const bad = allFields().find((x) => x.input.hasAttribute("aria-invalid")); if (bad) bad.input.focus(); }
      return;
    }
    error.set(errorMessage(e));
  }
}
