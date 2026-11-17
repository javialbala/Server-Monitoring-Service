# Bibliografía y fuentes

> Estado: **actualizada en la fase de rediseño de interfaz y limpieza (2026-11-16)**. Las entradas
> marcadas con *(verificar)* se han consultado de forma indirecta y deben contrastarse con la fuente
> primaria antes de citarlas en la memoria. Las entradas añadidas el 2026-11-16 se citan por su
> dirección oficial y **no se han vuelto a abrir en esta fase**: conviene comprobar que siguen vigentes.

## Fundamentos

- Mell, P. y Grance, T. (2011). *The NIST Definition of Cloud Computing*. NIST Special Publication
  800-145. National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-145
- Wiggins, A. *The Twelve-Factor App*. https://12factor.net/

## Tecnologías

- Docker Inc. *Docker Engine documentation*. https://docs.docker.com/engine/
- Docker Inc. *Docker Compose documentation*. https://docs.docker.com/compose/
- Docker Inc. *Docker Engine security* (incluye la superficie de ataque del demonio).
  https://docs.docker.com/engine/security/
- Docker Inc. *Docker SDK for Python*. https://docker-py.readthedocs.io/
- Docker Inc. *Docker Engine API: List containers* (`GET /containers/json`, parámetro `all`).
  https://docs.docker.com/reference/api/engine/ *(verificar versión 1.44)*
- FastAPI. *Documentation*. https://fastapi.tiangolo.com/
- Pydantic. *Documentation*. https://docs.pydantic.dev/
- OWASP. *Cheat Sheet Series* (Docker Security, Session Management, CSRF, XSS).
  https://cheatsheetseries.owasp.org/
- Python Packaging Authority. *Python Packaging User Guide* (disposición `src/`).
  https://packaging.python.org/
- uv. *Documentation*. https://docs.astral.sh/uv/

## Métricas del anfitrión (Linux)

- *proc(5): process information pseudo-filesystem* (`/proc/stat`, `/proc/meminfo`, `/proc/uptime`,
  `/proc/cpuinfo`, `/proc/net/dev`). https://man7.org/linux/man-pages/man5/proc.5.html
- *statvfs(3)* (tamaño y espacio libre de un sistema de archivos).
  https://man7.org/linux/man-pages/man3/statvfs.3.html
- Linux kernel documentation. *Sysfs interface for hardware monitoring (hwmon)*.
  https://www.kernel.org/doc/html/latest/hwmon/sysfs-interface.html
- Linux kernel documentation. *Kernel driver coretemp* y *Kernel driver k10temp*.
  https://www.kernel.org/doc/html/latest/hwmon/coretemp.html ·
  https://www.kernel.org/doc/html/latest/hwmon/k10temp.html
- Linux kernel documentation. *Thermal sysfs API* (`thermal_zone*`, tipo `x86_pkg_temp`).
  https://www.kernel.org/doc/html/latest/driver-api/thermal/sysfs-api.html
- Prometheus. *node_exporter* (inspiración del montaje `/hostfs`).
  https://github.com/prometheus/node_exporter

## Interfaz web

- MDN Web Docs. *Content Security Policy (CSP)*. https://developer.mozilla.org/docs/Web/HTTP/CSP
- MDN Web Docs. *SVG: `stroke-dasharray`, `<use>`, `<clipPath>`*.
  https://developer.mozilla.org/docs/Web/SVG
- MDN Web Docs. *Page Visibility API* y `prefers-reduced-motion`.
  https://developer.mozilla.org/docs/Web/API/Page_Visibility_API
- W3C. *Web Content Accessibility Guidelines (WCAG) 2.2*, criterio 1.4.3 Contraste (mínimo).
  https://www.w3.org/TR/WCAG22/

## Seguridad de la autenticación

- Biryukov, A., Dinu, D., Khovratovich, D. y Josefsson, S. (2021). *Argon2 Memory-Hard Function for
  Password Hashing and Proof-of-Work Applications*. RFC 9106. https://www.rfc-editor.org/rfc/rfc9106
- OWASP. *Password Storage Cheat Sheet*.
  https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- OWASP. *Session Management Cheat Sheet*.
  https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP. *Cross-Site Request Forgery Prevention Cheat Sheet*.
  https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- argon2-cffi. *Documentation*. https://argon2-cffi.readthedocs.io/

## Herramientas de monitorización comparables

- Netdata. https://learn.netdata.cloud/
- Glances. https://nicolargo.github.io/glances/
- cAdvisor. https://github.com/google/cadvisor
- Prometheus. https://prometheus.io/docs/
- Portainer. https://docs.portainer.io/

## Código y recursos de terceros

### Dependencias (instaladas con `uv`; versiones exactas en `uv.lock`)

| Recurso | Uso | Licencia | Etapa |
|---|---|---|---|
| FastAPI 0.163.1 | Framework web (panel y agente) | MIT | 1 |
| Starlette 1.10.0 | Base de FastAPI (dependencia indirecta) | BSD-3-Clause | 1 |
| Uvicorn 0.54.0 | Servidor ASGI | BSD-3-Clause | 1 |
| HTTPX 0.28.1 | Cliente HTTP del panel hacia el agente | BSD-3-Clause | 1 |
| Docker SDK for Python 7.2.0 | Acceso a Docker desde el agente | Apache-2.0 | 1 |
| pytest 9.2.0 / pytest-cov 7.1.0 | Tests y cobertura (solo desarrollo) | MIT | 1 |
| Ruff 0.17.5 | Estilo y análisis estático (solo desarrollo) | MIT | 1 |
| argon2-cffi 25.1.0 | Hash de contraseñas Argon2id (panel) | MIT | 2 |
| argon2-cffi-bindings 26.2.0, cffi 2.1.1, pycparser 3.12 | Dependencias indirectas de argon2-cffi | MIT, MIT-0, BSD-3-Clause | 2 |
| Imagen `python:3.12-slim` | Base de las imágenes Docker | Licencia PSF + paquetes Debian | 1 |

Licencias comprobadas en los metadatos de los paquetes instalados (`importlib.metadata`,
2026-11-15). La fase de rediseño **no añadió ni eliminó ninguna dependencia**.

### Recursos estáticos incluidos en el repositorio (no son dependencias)

Se copian a `src/server_monitor/panel/web/` y se sirven desde el propio panel (ADR-048). No se ha
modificado su contenido.

| Recurso | Uso | Licencia | Origen | Texto de la licencia |
|---|---|---|---|---|
| **IBM Plex Sans** (400, 500, 600; `woff2` latino) | Tipografía del texto | SIL Open Font License 1.1, © IBM Corp. | Paquete `@fontsource/ibm-plex-sans@5.2.8`, descargado de https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-sans@5.2.8/ | `web/fonts/OFL.txt` |
| **IBM Plex Mono** (400, 500; `woff2` latino) | Cifras, nombres de imagen, ejes | SIL Open Font License 1.1, © IBM Corp. | Paquete `@fontsource/ibm-plex-mono@5.2.7`, descargado de https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.2.7/ | `web/fonts/OFL.txt` |
| **Lucide** (18 iconos reunidos en un *sprite* `icons.svg`) | Iconos de la interfaz | ISC | Paquete `lucide-static@1.68.0`, descargado de https://unpkg.com/lucide-static@1.68.0/icons/ | `web/icons-LICENSE.txt` |
| Marca «Server Monitoring Service» (arco de 270°, `logo` y `favicon.svg`) | Marca y favicon | Obra propia del proyecto | — | — |

- IBM. *IBM Plex*. https://github.com/IBM/plex · SIL. *Open Font License 1.1*.
  https://openfontlicense.org/
- Fontsource. https://fontsource.org/
- Lucide. https://lucide.dev/ · *lucide-static* en npm. https://www.npmjs.com/package/lucide-static

No se ha copiado ni adaptado código de terceros: solo se usan como dependencias o recursos con licencia
compatible. Cuando se incorpore una dependencia o un recurso, se añadirá aquí con su licencia.

## Etapa PaaS (histórico, ya no se usa)

Fuentes de las Fases 0 a 3 (contexto en [historico/](historico/README.md)):

- SQLite. *Documentation*, *Write-Ahead Logging* y *Foreign Key Support*. https://www.sqlite.org/docs.html
- Chart.js. *Documentation* (previsto y no usado: ver ADR-047). https://www.chartjs.org/docs/
- Red Hat. *OpenShift Container Platform documentation*. https://docs.redhat.com/ (sección OpenShift)
- OKD. *OKD documentation*. https://docs.okd.io/
- Cloud Foundry Foundation. *Cloud Foundry documentation*. https://docs.cloudfoundry.org/
- eWeek (2015). *HP Buying ActiveState's Stackato Cloud PaaS Product*.
  https://www.eweek.com/cloud/hp-buying-activestate-s-stackato-cloud-paas-product/
- Data Center Knowledge (2015). *HP Buys ActiveState's Cloud Foundry PaaS Stackato*.
  https://www.datacenterknowledge.com/cloud/hp-buys-activestate-s-cloud-foundry-paas-stackato
- TechCrunch (2013). *PaaS Provider ActiveState And The Paradox Of Aligning With HP And Cloud
  Foundry*. https://techcrunch.com/2013/01/27/paas-provider-activestate-and-the-paradox-of-aligning-with-hp-and-cloud-foundry
- Wikipedia. *HPE Helion* *(verificar con fuentes primarias)*. https://en.wikipedia.org/wiki/HP_Helion
- Dokku. https://dokku.com/docs/
- CapRover. https://caprover.com/docs/
- Coolify. https://coolify.io/docs/

## Uso de herramientas de IA

El análisis, el diseño, el código y la documentación de las Fases 0 a 2 se han elaborado con la ayuda de un asistente
de IA (Claude, Anthropic) bajo la dirección del equipo. Todo el contenido debe ser revisado y
comprendido por el equipo, y las afirmaciones factuales se contrastan con la documentación oficial
citada.
