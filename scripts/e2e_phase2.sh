#!/usr/bin/env bash
# Prueba extremo a extremo de la Fase 2 (login, CSRF, aplicaciones y persistencia).
# Usa un proyecto Compose SEPARADO (minipaas-e2e, puerto 8010) para no tocar la base de datos
# de desarrollo (volumen minipaas-dev_minipaas-data). Al terminar, borra SOLO ese proyecto.
# Requisitos: bash scripts/prepare_dev_env.sh ya ejecutado (tokens y deploy/.env).
# Uso: bash scripts/e2e_phase2.sh      (sale con código distinto de 0 si algún paso falla)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export MINIPAAS_PORT=8010
COMPOSE=(docker compose -p minipaas-e2e --env-file deploy/.env -f deploy/compose.dev.yaml)
BASE="http://127.0.0.1:$MINIPAAS_PORT"
WORK="$(mktemp -d)"
JAR="$WORK/cookies.txt"
FAILED=0

cleanup() {
    # -v y --rmi local SOLO del proyecto e2e: borra sus volúmenes e imágenes, no los de desarrollo.
    "${COMPOSE[@]}" down -v --rmi local --remove-orphans >/dev/null 2>&1
    rm -rf "$WORK"
}
trap cleanup EXIT

step() {  # step "descripción" comando...
    local description="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "OK     $description"
    else
        echo "FALLO  $description"
        FAILED=1
    fi
}

http_code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
expect_code() {  # expect_code CÓDIGO curl-args...
    local expected="$1"
    shift
    [[ "$(http_code "$@")" == "$expected" ]]
}
json_field() { python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"; }

# La contraseña se genera aquí y nunca se imprime ni se guarda en disco.
PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
create_admin() {
    printf '%s\n' "$PASSWORD" |
        "${COMPOSE[@]}" exec -T controlplane \
            python -m minipaas.controlplane.manage create-admin --username admin --password-stdin
}
login() {
    # La contraseña viaja por el entorno (no por argumentos: se vería con `ps`).
    E2E_PASSWORD="$PASSWORD" python3 -c \
        'import json,os; print(json.dumps({"username": "admin", "password": os.environ["E2E_PASSWORD"]}))' |
        curl -s -f -c "$JAR" -H 'Content-Type: application/json' -d @- "$BASE/api/auth/login"
}

not() { ! "$@"; }
restart_without_deleting_data() { "${COMPOSE[@]}" down && "${COMPOSE[@]}" up -d --wait; }

step "levantar el proyecto minipaas-e2e" "${COMPOSE[@]}" up -d --build --wait
step "crear el administrador" create_admin
step "un segundo create-admin falla (no sobrescribe)" not create_admin

CSRF="$(login | json_field csrf_token)"
step "login correcto (token CSRF recibido)" test -n "$CSRF"
step "GET /api/applications sin cookie -> 401" expect_code 401 "$BASE/api/applications"
step "POST sin token CSRF -> 403" expect_code 403 -b "$JAR" -X POST \
    -H 'Content-Type: application/json' -d '{"name":"E2E"}' "$BASE/api/applications"
step "POST con token CSRF -> 201" expect_code 201 -b "$JAR" -X POST \
    -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -d '{"name":"E2E","slug":"e2e-app"}' "$BASE/api/applications"

step "down (sin -v) y up de nuevo" restart_without_deleting_data
step "la aplicación sigue existiendo tras reiniciar" expect_code 200 -b "$JAR" \
    "$BASE/api/applications/e2e-app"
step "la sesión sigue válida tras reiniciar" expect_code 200 -b "$JAR" "$BASE/api/auth/me"

step "logout -> 204" expect_code 204 -b "$JAR" -X POST -H "X-CSRF-Token: $CSRF" \
    "$BASE/api/auth/logout"
step "la cookie antigua da 401" expect_code 401 -b "$JAR" "$BASE/api/auth/me"

if [[ "$FAILED" == 0 ]]; then echo "E2E correcto."; else echo "E2E con fallos."; fi
exit "$FAILED"
