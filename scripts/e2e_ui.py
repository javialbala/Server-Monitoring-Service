"""Prueba del panel en Chromium sin interfaz (Playwright, que no es dependencia del proyecto):

    SMS_URL=http://127.0.0.1:8000 APP_PASSWORD=... uvx --with playwright python scripts/e2e_ui.py

Chromium por defecto en /usr/bin/chromium (CHROMIUM_PATH). Capturas en SMS_SCREENSHOTS.
"""

import math
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.environ.get("SMS_URL", "http://127.0.0.1:8000")
PASSWORD = os.environ["APP_PASSWORD"]
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")
SHOTS = os.environ.get("SMS_SCREENSHOTS")
ARC_FRACTION = 0.75  # el arco ocupa 270° de la circunferencia
failed = False


def check(description: str, ok: bool) -> None:
    global failed
    print(f"{'OK   ' if ok else 'FALLO'}  {description}")
    failed = failed or not ok


def shot(page, name: str) -> None:
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)


def gauge(page, kind: str, index: int = 0) -> tuple[float, float]:
    """(número mostrado, fracción del arco dibujada) del indicador `kind`."""
    cell = page.locator(f".metric-{kind}").nth(index)
    number = float(cell.locator(".gauge-number").text_content())
    arc = cell.locator(".gauge-value")
    drawn = float(arc.get_attribute("stroke-dasharray").split()[0])
    radius = float(arc.get_attribute("r"))
    return number, drawn / (2 * math.pi * radius * ARC_FRACTION)


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
    responses = {"metrics": [], "containers": []}

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
    page.locator(".metric-cpu .gauge-number").wait_for(timeout=10000)
    page.wait_for_timeout(1000)  # deja terminar la transición del arco

    m = responses["metrics"][-1]
    for kind, expected in (("cpu", m["cpu"]["percent"]), ("ram", m["memory"]["percent"])):
        number, fraction = gauge(page, kind)
        check(f"indicador {kind}: muestra {number} % (API {expected} %)", number == expected)
        check(
            f"indicador {kind}: el arco cubre {fraction:.3f} del recorrido "
            f"(esperado {expected / 100:.3f})",
            abs(fraction - expected / 100) < 0.005,
        )
    check(
        f"hay un indicador por disco ({len(m['disks'])})",
        page.locator(".metric-disk").count() == len(m["disks"]),
    )
    for i, disk in enumerate(m["disks"]):
        number, fraction = gauge(page, "disk", i)
        check(
            f"disco {disk['name']}: {number} % y arco {fraction:.3f} (API {disk['percent']} %)",
            number == disk["percent"] and abs(fraction - disk["percent"] / 100) < 0.005,
        )

    temperature = page.locator(".sys-temp dd").text_content()
    api_temp = m["temperature"]
    expected_text = str(round(api_temp["celsius"])) if api_temp else "No disponible"
    check(
        f"una sola temperatura general ({temperature!r}; API {api_temp})",
        page.locator(".sys-temp").count() == 1 and expected_text in temperature,
    )

    containers = responses["containers"][-1]["containers"]
    check(
        f"tabla de contenedores con {len(containers)} filas (como la API)",
        page.locator(".containers tbody tr").count() == len(containers),
    )
    stopped = sum(1 for c in containers if c["state"] != "running")
    marked = page.locator(".containers tbody tr", has_text="Detenido").count()
    check(f"los detenidos se marcan como tales ({marked} de {stopped})", marked == stopped)
    check(
        "no hay botones para iniciar, parar o borrar contenedores",
        page.locator(".containers button").count() == 0,
    )

    first = page.get_by_role("status").text_content()
    page.wait_for_timeout(11000)
    second = page.get_by_role("status").text_content()
    check(f"la hora de actualización cambia sola ({first!r} -> {second!r})", first != second)
    count = len(responses["metrics"])
    check(f"se han recibido {count} muestras reales (al menos 3)", count >= 3)
    check(
        "las gráficas de evolución tienen líneas dibujadas",
        page.locator(".chart-panel svg path").count() > 0,
    )
    box = page.locator(".chart-panel svg").first.bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.95, box["y"] + box["height"] * 0.5)
    page.wait_for_timeout(300)
    tooltip = page.locator(".chart-tooltip").first
    check("al pasar el cursor aparece el tooltip", tooltip.is_visible())
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
