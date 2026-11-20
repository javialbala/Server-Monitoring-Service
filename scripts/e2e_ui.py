"""Prueba del panel en Chromium sin interfaz (Playwright, que no es dependencia del proyecto):

    SMS_URL=http://127.0.0.1:8000 APP_PASSWORD=... uvx --with playwright python scripts/e2e_ui.py

Chromium por defecto en /usr/bin/chromium (CHROMIUM_PATH). Capturas en SMS_SCREENSHOTS.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.environ.get("SMS_URL", "http://127.0.0.1:8000")
PASSWORD = os.environ["APP_PASSWORD"]
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")
SHOTS = os.environ.get("SMS_SCREENSHOTS")
failed = False


def check(description: str, ok: bool) -> None:
    global failed
    print(f"{'OK   ' if ok else 'FALLO'}  {description}")
    failed = failed or not ok


def shot(page, name: str) -> None:
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)


def text(target, selector: str | None = None) -> str:
    node = target.locator(selector) if selector else target
    return (node.text_content() or "").strip()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # El 401 de la contraseña incorrecta es esperado.
    page.on(
        "console", lambda m: m.type == "error" and "401" not in m.text and errors.append(m.text)
    )
    responses = {"metrics": [], "containers": [], "images": [], "docker": []}

    def on_response(response):
        for name in responses:
            if response.url.endswith(f"/api/{name}") and response.ok:
                responses[name].append(response.json())

    page.on("response", on_response)

    page.goto(URL)
    shot(page, "login-1440")
    page.fill("#password", "incorrecta")
    page.click("button[type=submit]")
    page.wait_for_timeout(1000)
    alerts = " | ".join(page.get_by_role("alert").all_text_contents())
    check(f"con contraseña incorrecta se muestra el error ({alerts!r})", "incorrecta" in alerts)

    page.fill("#password", PASSWORD)
    page.click("button[type=submit]")
    page.locator(".kpi-card").first.wait_for(timeout=10000)
    page.wait_for_timeout(1000)

    m = responses["metrics"][-1]
    containers = responses["containers"][-1]["containers"]
    images = responses["images"][-1]["images"]
    docker = responses["docker"][-1]
    cards = page.locator(".kpi-card")

    running = sum(1 for c in containers if c["state"] == "running")
    running_percent = running / len(containers) * 100 if containers else 0
    expected_values = [
        (str(running), f"{running} of {len(containers)} running", running_percent),
        (
            f"{m['cpu']['percent']:.1f}",
            f"{m['cpu']['percent']:.1f}% of resources being used",
            m["cpu"]["percent"],
        ),
        (
            f"{m['memory']['percent']:.1f}",
            f"{m['memory']['percent']:.1f}% of resources being used",
            m["memory"]["percent"],
        ),
        (
            f"{m['disks'][0]['percent']:.1f}",
            f"{m['disks'][0]['percent']:.1f}% of resources being used",
            m["disks"][0]["percent"],
        ),
    ]
    for i, (value, note, percent) in enumerate(expected_values):
        card = cards.nth(i)
        check(f"KPI {i + 1}: valor {value!r}", text(card.locator(".kpi-value").first) == value)
        check(f"KPI {i + 1}: nota {note!r}", text(card.locator(".kpi-note").first) == note)
        width = card.locator(".progress-fill").evaluate("node => node.style.width")
        check(f"KPI {i + 1}: barra a {width}", float(width.rstrip("%")) == round(percent, 1))

    details = page.locator(".detail-card")
    check(
        f"Docker Engine muestra la versión {docker['server_version']!r}",
        text(details.nth(0).locator(".badge").first) == docker["server_version"],
    )
    check(
        f"Containers muestra {running} en ejecución",
        text(details.nth(1).locator(".badge").first) == f"{running} running",
    )
    check(
        f"Images muestra {len(images)} imágenes",
        text(details.nth(2).locator(".badge").first) == str(len(images)),
    )

    container_rows = page.locator("#containers-panel tbody tr")
    image_rows = page.locator("#images-panel tbody tr")
    check(
        f"tabla de contenedores con {min(5, len(containers))} filas visibles",
        container_rows.count() == min(5, len(containers)),
    )
    check(
        f"tabla de imágenes con {min(5, len(images))} filas visibles",
        image_rows.count() == min(5, len(images)),
    )
    check(
        "los contenedores en ejecución llevan el badge Running",
        page.locator("#containers-panel .pill-green").count() == min(5, running),
    )
    check(
        "no hay botones para iniciar, parar o borrar contenedores",
        page.locator("#containers-panel button").count() <= 1,
    )

    if len(containers) > 5:
        page.locator("#containers-panel .text-link").click()
        check(
            f"View All muestra los {len(containers)} contenedores",
            page.locator("#containers-panel tbody tr").count() == len(containers),
        )

    first = text(page, "#last-update")
    page.wait_for_timeout(11000)
    second = text(page, "#last-update")
    check(f"la hora de actualización cambia sola ({first!r} -> {second!r})", first != second)
    count = len(responses["metrics"])
    check(f"se han recibido {count} muestras reales (al menos 3)", count >= 3)
    shot(page, "panel-1440")

    # Chromium sin interfaz no oculta la pestaña: se simula el cambio de visibilidad.
    page.evaluate(
        """Object.defineProperty(document, 'hidden',
               {configurable: true, get: () => window.__hidden === true});
           window.__hidden = true; document.dispatchEvent(new Event('visibilitychange'));"""
    )
    before = len(responses["metrics"])
    page.wait_for_timeout(12000)
    check("con la pestaña oculta no se hacen consultas", len(responses["metrics"]) == before)
    page.evaluate("window.__hidden = false; document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(2000)
    check("al volver a la pestaña se reanuda la actualización", len(responses["metrics"]) > before)

    for width, height in ((1024, 768), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(600)
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check(f"{width} px: sin scroll horizontal (sobran {overflow} px)", overflow <= 0)
        shot(page, f"panel-{width}")
    page.set_viewport_size({"width": 1440, "height": 900})

    page.get_by_role("button", name="Cerrar sesión").click()
    page.locator("#password").wait_for(timeout=5000)
    check("al cerrar sesión vuelve el formulario de login", page.locator("#password").is_visible())
    session = page.request.get(f"{URL}/api/session").json()
    check("el servidor ya no reconoce la sesión", session["authenticated"] is False)
    check(f"sin errores de JavaScript ni de CSP en la consola {errors}", not errors)
    browser.close()

print("UI correcta." if not failed else "UI con fallos.")
sys.exit(1 if failed else 0)
