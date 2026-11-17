#!/usr/bin/env bash
# Exporta uv.lock a deploy/requirements/*.txt (con hashes) para las imágenes Docker.
# Ejecútalo tras cambiar dependencias; el CI comprueba que coinciden con uv.lock.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p deploy/requirements

uv export --frozen --no-dev --no-emit-project --quiet --extra panel \
    -o deploy/requirements/panel.txt
uv export --frozen --no-dev --no-emit-project --quiet --extra agent \
    -o deploy/requirements/agent.txt

echo "Exportados deploy/requirements/panel.txt y deploy/requirements/agent.txt"
