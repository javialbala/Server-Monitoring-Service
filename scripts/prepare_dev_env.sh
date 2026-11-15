#!/usr/bin/env bash
# Prepara el entorno de desarrollo local: token compartido y GID del socket de Docker.
# Es idempotente: no sobrescribe un token existente.
#
# Después, desde la raíz del repositorio:
#   docker compose --env-file deploy/.env -f deploy/compose.dev.yaml up -d --build --wait
# (Compose busca el .env en el directorio del proyecto, que es deploy/ por estar ahí el
#  archivo compose, pero se pasa --env-file explícito para no depender de ello.)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_DIR="$ROOT/deploy/secrets"
TOKEN_FILE="$SECRETS_DIR/agent_token"
ENV_FILE="$ROOT/deploy/.env"
SOCKET=/var/run/docker.sock

if [[ ! -S "$SOCKET" ]]; then
    echo "ERROR: no existe el socket de Docker en $SOCKET." >&2
    exit 1
fi

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

if [[ -f "$TOKEN_FILE" ]]; then
    echo "El token ya existe: $TOKEN_FILE (no se sobrescribe)."
else
    python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > "$TOKEN_FILE"
    # Permisos 644 (y no 600) a propósito: Compose monta el secret como bind mount del
    # archivo del host, conservando su propietario (tu usuario) y sus permisos. Los
    # procesos del contenedor (UID 10001/10002) son "otros" y necesitan lectura.
    # Es aceptable en desarrollo local porque el directorio padre es 700 (solo tú
    # puedes llegar al archivo en el host). En producción (Fase 13) se usará otro
    # mecanismo.
    chmod 644 "$TOKEN_FILE"
    echo "Token creado: $TOKEN_FILE"
fi

echo "DOCKER_GID=$(stat -c %g "$SOCKET")" > "$ENV_FILE"
echo "Escrito $ENV_FILE con el GID del socket de Docker."
