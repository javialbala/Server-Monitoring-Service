#!/usr/bin/env bash
# Exporta uv.lock a los archivos de dependencias que usan las imágenes Docker (ADR-013).
# Ejecútalo después de cambiar dependencias (uv add / uv lock). El CI comprueba que los
# archivos versionados coinciden con uv.lock.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p deploy/requirements

# --frozen: usa uv.lock tal cual, sin volver a resolver.
# --no-dev: sin pytest, ruff... (no van en las imágenes).
# --no-emit-project: sin el propio paquete minipaas (se copia como código fuente).
uv export --frozen --no-dev --no-emit-project --quiet \
    -o deploy/requirements/controlplane.txt
uv export --frozen --no-dev --no-emit-project --quiet --extra agent \
    -o deploy/requirements/agent.txt

echo "Exportados deploy/requirements/controlplane.txt y deploy/requirements/agent.txt"
