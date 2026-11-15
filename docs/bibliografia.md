# Bibliografía y fuentes

> Las entradas marcadas con *(verificar)* se han consultado de forma indirecta y deben contrastarse
> con la fuente primaria antes de citarlas en la memoria.

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
- FastAPI. *Documentation*. https://fastapi.tiangolo.com/
- Pydantic. *Documentation*. https://docs.pydantic.dev/
- SQLite. *Documentation*. https://www.sqlite.org/docs.html
- Chart.js. *Documentation*. https://www.chartjs.org/docs/
- OWASP. *Cheat Sheet Series* (Docker Security, Session Management, CSRF, XSS).
  https://cheatsheetseries.owasp.org/
- Python Packaging Authority. *Python Packaging User Guide* (disposición `src/`).
  https://packaging.python.org/

## Seguridad de la autenticación (Fase 2)

- Biryukov, A., Dinu, D., Khovratovich, D. y Josefsson, S. (2021). *Argon2 Memory-Hard Function for
  Password Hashing and Proof-of-Work Applications*. RFC 9106. https://www.rfc-editor.org/rfc/rfc9106
- OWASP. *Password Storage Cheat Sheet*.
  https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- OWASP. *Session Management Cheat Sheet*.
  https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP. *Cross-Site Request Forgery Prevention Cheat Sheet*.
  https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- SQLite. *Write-Ahead Logging*. https://www.sqlite.org/wal.html
- SQLite. *SQLite Foreign Key Support*. https://www.sqlite.org/foreignkeys.html
- argon2-cffi. *Documentation*. https://argon2-cffi.readthedocs.io/

## Motor de despliegue (Fase 3)

- Docker Inc. *Networking: bridge network driver* (redes `internal`, opciones del *bridge*).
  https://docs.docker.com/engine/network/drivers/bridge/
- Docker Inc. *Packet filtering and firewalls* (publicación de puertos e iptables).
  https://docs.docker.com/engine/network/packet-filtering-firewalls/
- Docker Inc. *Image digests* (referencias inmutables). https://docs.docker.com/reference/cli/docker/image/pull/
- Docker SDK for Python 7.2. *Containers, Networks, Images*. https://docker-py.readthedocs.io/
- nginx/docker-nginx-unprivileged. https://github.com/nginx/docker-nginx-unprivileged
- traefik/whoami. https://github.com/traefik/whoami

## Plataformas de referencia

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

## Código y recursos de terceros

| Recurso | Uso | Licencia | Fase |
|---|---|---|---|
| FastAPI 0.163.1 | Framework web (control plane y agente) | MIT | 1 |
| Starlette 1.10.0 | Base de FastAPI (dependencia indirecta) | BSD-3-Clause | 1 |
| Uvicorn 0.54.0 | Servidor ASGI | BSD-3-Clause | 1 |
| HTTPX 0.28.1 | Cliente HTTP del control plane hacia el agente | BSD-3-Clause | 1 |
| Docker SDK for Python 7.2.0 | Acceso a Docker desde el agente | Apache-2.0 | 1 |
| pytest 9.2.0 / pytest-cov 7.1.0 | Tests y cobertura (solo desarrollo) | MIT | 1 |
| Ruff 0.17.5 | Estilo y análisis estático (solo desarrollo) | MIT | 1 |
| argon2-cffi 25.1.0 | Hash de contraseñas Argon2id (control plane) | MIT | 2 |
| argon2-cffi-bindings 26.2.0, cffi 2.1.1, pycparser 3.12 | Dependencias indirectas de argon2-cffi | MIT, MIT-0, BSD-3-Clause | 2 |
| Imagen `python:3.12-slim` | Base de las imágenes Docker | Licencia PSF + paquetes Debian | 1 |
| Imagen `nginxinc/nginx-unprivileged:1.29.8-alpine` (`sha256:0c79d56a…7fbe6`) | Entrada «Servidor web estático» del catálogo y sonda de salud. Se ejecuta, no se redistribuye | Dockerfiles: Apache-2.0 (etiqueta `org.opencontainers.image.licenses`); NGINX: BSD-2-Clause; Alpine y paquetes: licencias de cada proyecto | 3 |
| Imagen `traefik/whoami:v1.11.0` (`sha256:20068979…937ab`) | Entrada «Servicio HTTP de prueba» del catálogo | Apache-2.0 | 3 |

No se ha copiado ni adaptado código de terceros: solo se usan como dependencias. Versiones exactas
en `uv.lock`. Licencias comprobadas en los metadatos de los paquetes instalados
(`importlib.metadata`, 2026-11-15).

Cuando se incorpore una dependencia o se adapte código, se añadirá aquí con su licencia.

## Uso de herramientas de IA

El análisis, el diseño, el código y la documentación de las Fases 0 a 2 se han elaborado con la ayuda de un asistente
de IA (Claude, Anthropic) bajo la dirección del equipo. Todo el contenido debe ser revisado y
comprendido por el equipo, y las afirmaciones factuales se contrastan con la documentación oficial
citada.
