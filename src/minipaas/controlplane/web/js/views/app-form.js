// Formulario de nueva aplicación.

import { el } from "../dom.js";
import { api, ApiError, isUnauthorized, errorMessage } from "../api.js";
import { DESCRIPTION_MAX, NAME_MAX, isValidSlug, slugify } from "../format.js";
import { field, formError, setBusy, applyValidationErrors, toast } from "../ui.js";

export function render(root) {
  const card = el("section", { className: "card card-form", attrs: { "aria-labelledby": "new-title" } });
  card.append(el("h1", { text: "Nueva aplicación", attrs: { id: "new-title", tabindex: "-1" } }));

  const form = el("form", { attrs: { novalidate: true } });
  const name = field({ id: "name", label: "Nombre", required: true, maxlength: NAME_MAX, autocomplete: "off" });
  const slug = field({ id: "slug", label: "Identificador (opcional)", maxlength: 40, autocomplete: "off",
    help: "Identificador: se usa en direcciones y nombres internos. No se puede cambiar después.",
    placeholder: "se genera a partir del nombre" });
  const suggestion = el("p", { className: "help", attrs: { "aria-live": "off" } });
  slug.wrap.insertBefore(suggestion, slug.wrap.querySelector(".field-error"));
  const description = field({ id: "description", label: "Descripción (opcional)", textarea: true, maxlength: DESCRIPTION_MAX });
  const counter = el("p", { className: "help counter", text: `0/${DESCRIPTION_MAX}`, attrs: { "aria-hidden": "true" } });
  description.wrap.insertBefore(counter, description.wrap.querySelector(".field-error"));
  const error = formError();

  const submit = el("button", { text: "Crear aplicación", attrs: { type: "submit" } });
  const cancel = el("a", { className: "button btn-secondary", text: "Cancelar", attrs: { href: "#/apps" } });
  form.append(name.wrap, slug.wrap, description.wrap, error.node, el("div", { className: "actions" }, submit, cancel));
  card.append(form);
  root.append(card);

  // Sugerencia de identificador en vivo mientras se escribe el nombre.
  function updateSuggestion() {
    const s = slugify(name.input.value);
    slug.input.placeholder = s || "se genera a partir del nombre";
    suggestion.textContent = s ? "Sugerencia: " + s : "";
  }
  name.input.addEventListener("input", updateSuggestion);
  description.input.addEventListener("input", () => {
    counter.textContent = `${description.input.value.length}/${DESCRIPTION_MAX}`;
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    for (const f of [name, slug, description]) f.clearError();
    error.clear();

    const nameValue = name.input.value.trim();
    const slugValue = slug.input.value.trim();
    const descValue = description.input.value;
    let first = null;
    const fail = (f, msg) => { f.setError(msg); first = first || f; };
    if (!nameValue) fail(name, "El nombre es obligatorio.");
    else if (nameValue.length > NAME_MAX) fail(name, `El nombre admite como máximo ${NAME_MAX} caracteres.`);
    if (slugValue && !isValidSlug(slugValue)) {
      fail(slug, "Usa minúsculas, números y guiones (3 a 40 caracteres, empieza por letra y sin guiones dobles).");
    }
    if (descValue.length > DESCRIPTION_MAX) fail(description, `La descripción admite como máximo ${DESCRIPTION_MAX} caracteres.`);
    if (first) { first.input.focus(); return; }

    setBusy(submit, true, "Creando…", "Crear aplicación");
    try {
      const app = await api.post("/api/applications", {
        name: nameValue, slug: slugValue || null, description: descValue,
      });
      toast("Aplicación creada.");
      location.hash = "#/apps/" + encodeURIComponent(app.slug);
    } catch (e) {
      if (isUnauthorized(e)) return;
      if (e instanceof ApiError && e.status === 409) {
        slug.setError(errorMessage(e));
        slug.input.focus();
      } else if (e instanceof ApiError && e.status === 422) {
        const general = applyValidationErrors(e, { name, slug, description });
        if (general.length) error.set(general.join(" "));
        else for (const f of [name, slug, description]) if (f.input.hasAttribute("aria-invalid")) { f.input.focus(); break; }
      } else {
        error.set(errorMessage(e));
      }
    } finally {
      if (submit.isConnected) setBusy(submit, false, "Creando…", "Crear aplicación");
    }
  });

}
