#!/usr/bin/env bash
# Prepara el entorno de desarrollo local: token compartido y GID del socket de Docker.
# Es idempotente: no regenera el token si ya existe con los permisos correctos.
#
# Uso:  bash scripts/prepare_dev_env.sh            (prepara si hace falta)
#       bash scripts/prepare_dev_env.sh --rotate   (genera un token nuevo)
#
# Después, desde la raíz del repositorio:
#   docker compose --env-file deploy/.env -f deploy/compose.dev.yaml up -d --build --wait
#
# --- Por qué un archivo de token por componente (ADR-014) -----------------------------
# Sin Swarm, Docker Compose monta cada secret como un bind mount del archivo del host,
# conservando su propietario y sus permisos; ignora las opciones uid/gid/mode
# ("not supported outside Swarm mode"). Para que el archivo tenga permisos 600 y aun así
# lo lea el proceso del contenedor, su propietario debe ser el UID de ese proceso.
# Como control plane (UID 10001) y agente (UID 10002) tienen UID distintos, cada uno
# recibe su propia copia del MISMO token, con permisos 600 y propietario su UID.
#
# Asignar un archivo a otro UID requiere root en el host. En lugar de pedir sudo, se usa
# un contenedor efímero, sin red, que solo escribe los dos archivos: no concede ningún
# privilegio nuevo, porque quien puede usar Docker ya tiene un acceso equivalente a root
# (ver ADR-002). Consecuencia buscada: el token tampoco es legible por el usuario del
# host; solo por el proceso que lo necesita.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_DIR="$ROOT/deploy/secrets"
ENV_FILE="$ROOT/deploy/.env"
SOCKET=/var/run/docker.sock
HELPER_IMAGE=python:3.12-slim   # la misma imagen base que los Dockerfiles

# Deben coincidir con los UID de deploy/Dockerfile.controlplane y deploy/Dockerfile.agent.
CONTROLPLANE_UID=10001
AGENT_UID=10002

if [[ ! -S "$SOCKET" ]]; then
    echo "ERROR: no existe el socket de Docker en $SOCKET." >&2
    exit 1
fi

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Devuelve 0 si el archivo existe con permisos 600 y el propietario esperado.
secret_is_valid() {
    local file="$1" uid="$2"
    [[ -f "$file" ]] && [[ "$(stat -c '%a %u' "$file")" == "600 $uid" ]]
}

tokens_are_valid() {
    secret_is_valid "$SECRETS_DIR/controlplane_token" "$CONTROLPLANE_UID" &&
        secret_is_valid "$SECRETS_DIR/agent_token" "$AGENT_UID"
}

if [[ "${1:-}" == "--rotate" ]] || ! tokens_are_valid; then
    # Se borran desde el host: el directorio es nuestro, así que podemos eliminar
    # archivos de otro propietario aunque no podamos leerlos.
    rm -f "$SECRETS_DIR/controlplane_token" "$SECRETS_DIR/agent_token"
    docker run --rm --network none --user 0 \
        -v "$SECRETS_DIR:/secrets" \
        "$HELPER_IMAGE" python -c "
import os, secrets
token = secrets.token_urlsafe(48)
for name, uid in (('controlplane_token', $CONTROLPLANE_UID), ('agent_token', $AGENT_UID)):
    path = '/secrets/' + name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        file.write(token + '\n')
    os.chown(path, uid, uid)
"
    echo "Token generado: un archivo por componente, permisos 600, directorio 700."
else
    echo "Los tokens ya existen con permisos 600 y el propietario correcto (no se regeneran)."
fi

stat -c '  %A %u  %n' "$SECRETS_DIR" "$SECRETS_DIR"/*

echo "DOCKER_GID=$(stat -c %g "$SOCKET")" > "$ENV_FILE"
echo "Escrito $ENV_FILE con el GID del socket de Docker."
