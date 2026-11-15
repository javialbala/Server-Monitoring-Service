#!/usr/bin/env bash
# Prueba extremo a extremo de la Fase 3 (motor de despliegue) con contenedores reales.
#
# Usa un proyecto Compose SEPARADO para no tocar el entorno de desarrollo:
#   proyecto minipaas-e2e · instancia e2e · panel en 127.0.0.1:8010 · catálogo de prueba activo.
# Al terminar elimina sus contenedores, volúmenes, imágenes y redes, y los recursos de
# aplicación con la etiqueta minipaas.instance=e2e (que solo puede haber creado esta prueba).
#
# Uso: bash scripts/e2e_phase3.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export MINIPAAS_PORT=8010 MINIPAAS_INSTANCE=e2e MINIPAAS_ENABLE_TEST_CATALOG=true
COMPOSE=(docker compose -p minipaas-e2e --env-file deploy/.env -f deploy/compose.dev.yaml)

cleanup() {
    # Primero los recursos de aplicación de la instancia e2e (si la prueba se cortó a medias)…
    docker ps -aq --filter label=minipaas.instance=e2e | xargs -r docker rm -f >/dev/null 2>&1
    docker ps -aq --filter label=minipaas.e2e-check=true | xargs -r docker rm -f >/dev/null 2>&1
    docker network ls -q --filter label=minipaas.instance=e2e | xargs -r docker network rm >/dev/null 2>&1
    # …y después el propio proyecto de prueba (volumen e imágenes incluidos).
    "${COMPOSE[@]}" down -v --rmi local --remove-orphans >/dev/null 2>&1
}
trap cleanup EXIT

if ! "${COMPOSE[@]}" up -d --build --wait >/dev/null 2>&1; then
    echo "FALLO  no se pudo levantar el proyecto minipaas-e2e"
    exit 1
fi

# Contraseña aleatoria solo para esta prueba: nunca se imprime.
E2E_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
export E2E_PASSWORD
if ! printf '%s\n' "$E2E_PASSWORD" | "${COMPOSE[@]}" exec -T controlplane \
    python -m minipaas.controlplane.manage create-admin --username admin --password-stdin >/dev/null; then
    echo "FALLO  no se pudo crear el administrador"
    exit 1
fi

uv run python scripts/e2e_phase3.py
