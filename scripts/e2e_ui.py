"""Prueba del panel en un navegador real (Chromium sin interfaz, con Playwright).

Comprueba lo que no se puede ver con curl: que el login funciona, que se pintan las métricas y
la tabla de contenedores, que los datos se actualizan solos y que la actualización se pausa
cuando la pestaña está oculta.

Playwright NO es dependencia del proyecto; se usa solo para esta prueba:
    MINIPAAS_URL=http://127.0.0.1:8000 MINIPAAS_PASSWORD=... \\
        uvx --with playwright python scripts/e2e_ui.py
Necesita Chromium instalado (por defecto /usr/bin/chromium; cambiar con CHROMIUM_PATH).
"""

import os
import sys
import time

from playwright.sync_api import sync_playwright

URL = os.environ.get("MINIPAAS_URL", "http://127.0.0.1:8000")
PASSWORD = os.environ["MINIPAAS_PASSWORD"]
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")
failed = False


def check(description: str, ok: bool) -> None:
    global failed
    print(f"{'OK   ' if ok else 'FALLO'}  {description}")
    failed = failed or not ok


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context()
    page = context.new_page()
    api_calls = []  # instantes de cada petición a /api/metrics
    page.on("request", lambda r: r.url.endswith("/api/metrics") and api_calls.append(time.time()))

    page.goto(URL)
    page.fill("#password", "incorrecta")
    page.click("button[type=submit]")
    page.wait_for_timeout(1000)
    alerts = " | ".join(page.get_by_role("alert").all_text_contents())
    check(f"con contraseña incorrecta se muestra el error ({alerts!r})", "incorrecta" in alerts)

    page.fill("#password", PASSWORD)
    page.click("button[type=submit]")
    status = page.get_by_role("status")
    status.wait_for(timeout=10000)
    for _ in range(20):  # espera a la primera actualización (máx. 10 s)
        if not status.text_content().endswith("—"):
            break
        page.wait_for_timeout(500)
    for title in ("CPU", "Memoria RAM", "Disco", "Sistema"):
        check(f"se ve la tarjeta {title!r}", page.get_by_role("heading", name=title).is_visible())
    check("la tabla de contenedores tiene filas", page.locator("tbody tr").count() > 0)

    first = page.get_by_role("status").text_content()
    time.sleep(6)
    second = page.get_by_role("status").text_content()
    check(f"la hora de actualización cambia sola ({first!r} -> {second!r})", first != second)

    # Otra pestaña al frente: la del panel queda oculta y debe dejar de consultar.
    other = context.new_page()
    other.bring_to_front()
    time.sleep(1)
    calls_before = len(api_calls)
    time.sleep(11)
    check("con la pestaña oculta no se hacen consultas", len(api_calls) == calls_before)
    page.bring_to_front()
    time.sleep(2)
    check("al volver a la pestaña se reanuda la actualización", len(api_calls) > calls_before)

    page.get_by_role("button", name="Cerrar sesión").click()
    page.locator("#password").wait_for(timeout=5000)  # is_visible() no espera: se usa wait_for
    check("al cerrar sesión vuelve el formulario de login", page.locator("#password").is_visible())
    session = page.request.get(f"{URL}/api/session").json()
    check("el servidor ya no reconoce la sesión", session["authenticated"] is False)
    browser.close()

print("UI correcta." if not failed else "UI con fallos.")
sys.exit(1 if failed else 0)
