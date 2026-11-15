#!/usr/bin/env bash
# Levanta el entorno de desarrollo y comprueba sus propiedades de seguridad.
# Uso: bash scripts/verify_dev_env.sh [--down]   (--down baja el entorno al terminar)
# Sale con código distinto de 0 si alguna comprobación falla.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose --env-file deploy/.env -f deploy/compose.dev.yaml)
FAILED=0

check() {  # check "descripción" comando...
    local description="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "OK     $description"
    else
        echo "FALLO  $description"
        FAILED=1
    fi
}

cleanup() {
    if [[ "${1:-}" == "--down" ]]; then
        "${COMPOSE[@]}" down
    fi
}

if ! "${COMPOSE[@]}" up -d --build --wait; then
    echo "FALLO  no se pudo levantar el entorno"
    cleanup "${1:-}"
    exit 1
fi

health_ok() { curl -fsS http://127.0.0.1:8000/api/health | grep -q '"status":"ok"'; }
no_socket_in_controlplane() { "${COMPOSE[@]}" exec -T controlplane test ! -e /var/run/docker.sock; }
agent_has_no_ports() {
    local container
    container="$("${COMPOSE[@]}" ps -q agent)"
    [[ "$(docker inspect --format '{{json .HostConfig.PortBindings}}' "$container")" == "{}" ]]
}
agent_not_on_host() { ! curl -s --max-time 3 -o /dev/null http://127.0.0.1:8001/health; }
not_root() { [[ "$("${COMPOSE[@]}" exec -T "$1" id -u)" != "0" ]]; }
agent_rejects_no_token() {
    local code
    code="$("${COMPOSE[@]}" exec -T controlplane python -c "
import urllib.request, urllib.error
try:
    urllib.request.urlopen('http://agent:8001/health', timeout=3)
    print(200)
except urllib.error.HTTPError as e:
    print(e.code)
")"
    [[ "$code" == "401" ]]
}

# El secret debe tener permisos 600 (archivo) y 700 (directorio) en el host, y cada
# contenedor debe poder leerlo con su propio UID (ver ADR-014).
secrets_restricted_on_host() {
    [[ "$(stat -c '%a' deploy/secrets)" == "700" ]] &&
        [[ "$(stat -c '%a %u' deploy/secrets/controlplane_token)" == "600 10001" ]] &&
        [[ "$(stat -c '%a %u' deploy/secrets/agent_token)" == "600 10002" ]]
}
reads_own_secret() {  # reads_own_secret servicio archivo
    "${COMPOSE[@]}" exec -T "$1" sh -c "[ \"\$(stat -c '%a %u' /run/secrets/$2)\" = \"600 \$(id -u)\" ] && test -r /run/secrets/$2"
}

check "/api/health responde status ok" health_ok
check "controlplane NO tiene el socket de Docker" no_socket_in_controlplane
check "el agente no publica puertos" agent_has_no_ports
check "el agente no es accesible desde el host (8001)" agent_not_on_host
check "controlplane no se ejecuta como root" not_root controlplane
check "agent no se ejecuta como root" not_root agent
check "el agente rechaza peticiones sin token (401)" agent_rejects_no_token
check "secret con permisos 600 y directorio 700 en el host" secrets_restricted_on_host
check "controlplane lee su secret (600, propietario su UID)" reads_own_secret controlplane controlplane_token
check "agent lee su secret (600, propietario su UID)" reads_own_secret agent agent_token

cleanup "${1:-}"
exit "$FAILED"
