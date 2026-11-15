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

### Revisión del equipo (2026-11-15)

| # | Validación | Comando / procedimiento | Resultado real |
|---|---|---|---|
| 0.7 | Integridad de `formato_preguntas.md` al versionarlo | `sha256sum formato_preguntas.md`; `git show HEAD:formato_preguntas.md \| sha256sum`; `git diff --quiet HEAD -- formato_preguntas.md` | SHA-256 idéntico en disco y en Git (`af7d48262e8296a301435dc448af91f58bd84bbef21520ea3a6ef6b12d26f694`); sin diferencias. Commit `7275902`. |
| 0.8 | *Push* a GitHub | `git push -u origin main`, `git push -u origin fase-00-analisis` (HTTPS) | **Fallido**: `fatal: could not read Username for 'https://github.com': terminal prompts disabled`. Sin credenciales HTTPS ni CLI `gh`. Una comprobación de autenticación SSH no se ejecutó (denegada por los permisos del entorno). |
| 0.9 | Coherencia de la documentación tras incorporar los matices | Script de enlaces relativos; `grep` de `RuntimeSpec`, de ADR en estado *Propuesta* y de patrones de secretos | 15 archivos, 17 enlaces relativos, 0 rotos. `RuntimeSpec` solo aparece como nombre antiguo. Ninguna ADR en estado *Propuesta*. Sin secretos. |

No se ha realizado ninguna conexión ni operación sobre el servidor real.
