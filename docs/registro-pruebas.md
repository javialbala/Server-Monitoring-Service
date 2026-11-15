# Registro de pruebas

Registro cronológico de pruebas y validaciones **realmente ejecutadas**. Cada entrada indica la fase,
el comando o procedimiento, el resultado observado y las observaciones.

## Fase 0 — Análisis y arquitectura (2026-11-15)

En esta fase no hay código, por lo que no hay pruebas automáticas. Se han realizado las siguientes
validaciones:

| # | Validación | Comando / procedimiento | Resultado real |
|---|---|---|---|
| 0.1 | Estado inicial del repositorio | `git status`, `git log`, `git ls-remote origin` | Rama `main` sin commits; remoto `origin` (GitHub) sin referencias; un único archivo sin seguimiento: `formato_preguntas.md`. |
| 0.2 | Herramientas del entorno local | `python3 --version`, `docker --version`, `docker compose version` | Python 3.14.8, Docker 29.9.2, Docker Compose 5.6.1. |
| 0.3 | Acceso a Docker sin root en local | `docker info`, `id -nG` | El usuario pertenece al grupo `docker`; el demonio responde (perfil seccomp y cgroupns activos). Docker en modo *rootful*. |
| 0.4 | Enlaces internos de la documentación | Script Python (fuera del repositorio) que recorre `README.md`, `CHANGELOG.md` y `docs/**/*.md` y comprueba que cada enlace Markdown relativo apunta a un archivo o directorio existente | 1.ª ejecución: 2 enlaces rotos (el directorio `informes/` aún no existía y un ejemplo literal en este documento se detectaba como enlace). Corregidos. 2.ª ejecución: 0 enlaces rotos (ver informe de la Fase 0 para la salida exacta). |
| 0.5 | Ausencia de secretos en los archivos versionados | `grep -rniE` de patrones de credenciales (`password/token/secret/api_key = valor`, cabeceras de clave privada, tokens `ghp_`) sobre `README.md`, `CHANGELOG.md`, `.gitignore` y `docs/` | Sin coincidencias (código de salida 1 de `grep`). |
| 0.6 | Diagramas Mermaid | Revisión manual de la sintaxis de los 4 diagramas (`03-arquitectura.md` ×3, `06-roadmap.md` ×1) | Revisados manualmente. **Pendiente**: comprobar que GitHub los renderiza correctamente tras el *push*. |

No se ha realizado ninguna conexión ni operación sobre el servidor real.
