#!/usr/bin/env bash
# Prueba extremo a extremo de la plataforma de monitorización, con Docker real.
# Usa un proyecto Compose SEPARADO (minipaas-e2e, puerto 8010) para no tocar el entorno de
# desarrollo. Al terminar borra SOLO ese proyecto y el contenedor de prueba que crea.
# Requisitos: bash scripts/prepare_dev_env.sh ya ejecutado (tokens y deploy/.env).
# Uso: bash scripts/e2e_monitor.sh      (sale con código distinto de 0 si algún paso falla)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export MINIPAAS_PORT=8010
COMPOSE=(docker compose -p minipaas-e2e --env-file deploy/.env -f deploy/compose.dev.yaml)
BASE="http://127.0.0.1:$MINIPAAS_PORT"
WORK="$(mktemp -d)"
JAR="$WORK/cookies.txt"
# Contenedor "ajeno": lo crea este script con la CLI de Docker, no la plataforma.
EXTERNAL="monitor-e2e-$RANDOM"
FAILED=0

cleanup() {
    docker rm -f "$EXTERNAL" >/dev/null 2>&1
    # -v y --rmi local SOLO del proyecto e2e: no toca el volumen ni las imágenes de desarrollo.
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
not() { ! "$@"; }
http_code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
expect_code() {  # expect_code CÓDIGO curl-args...
    local expected="$1"
    shift
    [[ "$(http_code "$@")" == "$expected" ]]
}
# check_json ARCHIVO "expresión de Python sobre d": comprueba una condición sobre un JSON.
check_json() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if eval(sys.argv[2]) else 1)' "$1" "$2"; }

# La contraseña se genera aquí y nunca se imprime ni se guarda en disco.
PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')"
set_password() {  # set_password CONTRASEÑA
    printf '%s\n' "$1" |
        "${COMPOSE[@]}" exec -T controlplane python -m minipaas.controlplane.manage set-password --stdin
}
login() {  # login CONTRASEÑA  -> imprime el código HTTP
    # La contraseña viaja por el entorno y stdin (no por argumentos: se vería con `ps`).
    E2E_PASSWORD="$1" python3 -c \
        'import json,os; print(json.dumps({"password": os.environ["E2E_PASSWORD"]}))' |
        curl -s -o /dev/null -w '%{http_code}' -c "$JAR" -H 'Content-Type: application/json' \
            -d @- "$BASE/api/login"
}
login_ok() { [[ "$(login "$PASSWORD")" == "204" ]]; }
login_wrong_is_401() { [[ "$(login "incorrecta")" == "401" ]]; }
get() { curl -s -f -b "$JAR" "$BASE$1" -o "$2"; }  # get RUTA ARCHIVO

echo "== Despliegue"
step "levantar el proyecto minipaas-e2e" "${COMPOSE[@]}" up -d --build --wait
step "set-password rechaza una contraseña de 3 caracteres" not set_password "abc"
step "set-password acepta la contraseña de prueba" set_password "$PASSWORD"

echo "== Autenticación"
step "GET /api/metrics sin sesión -> 401" expect_code 401 "$BASE/api/metrics"
step "GET /api/containers sin sesión -> 401" expect_code 401 "$BASE/api/containers"
step "login con contraseña incorrecta -> 401" login_wrong_is_401
step "login correcto -> 204 con cookie" login_ok

echo "== Métricas del anfitrión"
get /api/metrics "$WORK/m1.json"
step "CPU: porcentaje entre 0 y 100 y núcleos > 0" check_json "$WORK/m1.json" \
    '0 <= d["cpu"]["percent"] <= 100 and d["cpu"]["cores"] > 0'
step "RAM: total igual a MemTotal del anfitrión" check_json "$WORK/m1.json" \
    "d['memory']['total_bytes'] == $(awk '/^MemTotal:/ {print $2 * 1024}' /proc/meminfo)"
step "RAM: usada + disponible = total y porcentaje coherente" check_json "$WORK/m1.json" \
    'd["memory"]["used_bytes"] + d["memory"]["available_bytes"] == d["memory"]["total_bytes"] and 0 <= d["memory"]["percent"] <= 100'
step "Disco: total igual al de / en el anfitrión (df)" check_json "$WORK/m1.json" \
    "d['disk']['total_bytes'] == $(df -B1 --output=size / | tail -1)"
step "Disco: porcentaje entre 0 y 100" check_json "$WORK/m1.json" '0 <= d["disk"]["percent"] <= 100'
step "Hostname del anfitrión (no el del contenedor)" check_json "$WORK/m1.json" \
    "d['hostname'] == '$(cat /etc/hostname 2>/dev/null || hostname)'"
step "Sistema operativo del anfitrión (os-release)" check_json "$WORK/m1.json" \
    "d['os']['name'] == '$(. /etc/os-release && echo "$PRETTY_NAME")'"
step "Uptime cercano al del anfitrión (±60 s)" check_json "$WORK/m1.json" \
    "abs(d['uptime_seconds'] - $(cut -d. -f1 /proc/uptime)) < 60"

echo "== Actualización periódica"
sleep 2
get /api/metrics "$WORK/m2.json"
step "una segunda consulta devuelve una medición nueva (collected_at distinto)" python3 -c \
    'import json,sys; a,b=(json.load(open(f)) for f in sys.argv[1:]); sys.exit(a["collected_at"] == b["collected_at"])' \
    "$WORK/m1.json" "$WORK/m2.json"

echo "== Contenedores"
docker run -d --name "$EXTERNAL" -p 127.0.0.1::80 \
    --label com.docker.compose.project=e2e-demo --label com.docker.compose.service=web \
    traefik/whoami:v1.11 >/dev/null
HOST_PORT="$(docker port "$EXTERNAL" 80/tcp | head -1 | awk -F: '{print $NF}')"
get /api/containers "$WORK/c1.json"
step "detecta el contenedor creado fuera de la plataforma" check_json "$WORK/c1.json" \
    "any(c['name'] == '$EXTERNAL' for c in d['containers'])"
step "imagen, estado, puerto y proyecto Compose correctos" check_json "$WORK/c1.json" \
    "[(c['image'], c['state'], c['ports'][0]['host_port'], c['ports'][0]['container_port'], c['compose_project'], c['compose_service']) for c in d['containers'] if c['name'] == '$EXTERNAL'] == [('traefik/whoami:v1.11', 'running', $HOST_PORT, 80, 'e2e-demo', 'web')]"
step "lista el mismo número de contenedores que docker ps" check_json "$WORK/c1.json" \
    "len(d['containers']) == $(docker ps -q | wc -l)"
step "solo muestra contenedores en ejecución" check_json "$WORK/c1.json" \
    'all(c["state"] == "running" for c in d["containers"])'
docker stop -t 1 "$EXTERNAL" >/dev/null
get /api/containers "$WORK/c2.json"
step "un contenedor parado deja de aparecer" check_json "$WORK/c2.json" \
    "all(c['name'] != '$EXTERNAL' for c in d['containers'])"

echo "== Solo lectura"
# Se consultan las rutas varias veces y se comprueba con `docker events` que en ese intervalo
# Docker no registró NINGÚN evento de contenedores, imágenes, volúmenes ni redes. Se excluyen
# solo los healthchecks que Docker ejecuta por su cuenta (exec_create/start/die, health_status):
# no son operaciones de la plataforma.
# `docker events --since` tiene resolución de segundos: se espera para que la ventana no
# incluya la parada del contenedor de prueba hecha justo antes por este script.
sleep 2
SINCE="$(date +%s)"
sleep 1
for _ in 1 2 3; do
    get /api/metrics /dev/null
    get /api/containers /dev/null
done
sleep 1
UNTIL="$(date +%s)"
docker events --since "$SINCE" --until "$UNTIL" \
    --filter type=container --filter type=image --filter type=volume --filter type=network \
    --format '{{.Type}} {{.Action}} {{.Actor.Attributes.name}}' |
    grep -Ev '^container (exec_(create|start|die)|health_status)' >"$WORK/events.txt"
step "las consultas no generan eventos de modificación en Docker" test ! -s "$WORK/events.txt"
sed 's/^/       evento inesperado: /' "$WORK/events.txt"
step "el panel NO tiene el socket de Docker" "${COMPOSE[@]}" exec -T controlplane test ! -e /var/run/docker.sock
step "el agente no puede escribir en /hostfs (solo lectura)" not "${COMPOSE[@]}" exec -T agent touch /hostfs/tmp/minipaas-e2e
step "/hostfs no incluye submontajes (/hostfs/proc vacío)" "${COMPOSE[@]}" exec -T agent sh -c 'test -z "$(ls -A /hostfs/proc)"'

echo "== Sesión"
CSRF="$(curl -s -b "$JAR" "$BASE/api/session" | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])')"
step "logout sin token CSRF -> 403" expect_code 403 -b "$JAR" -X POST "$BASE/api/logout"
step "logout con token CSRF -> 204" expect_code 204 -b "$JAR" -X POST -H "X-CSRF-Token: $CSRF" "$BASE/api/logout"
step "la cookie antigua da 401" expect_code 401 -b "$JAR" "$BASE/api/metrics"

echo "== Intentos repetidos"
for _ in 1 2 3 4 5; do login "incorrecta" >/dev/null; done
step "tras 5 fallos la IP queda bloqueada (429), incluso con la contraseña correcta" \
    test "$(login "$PASSWORD")" == "429"

if [[ "$FAILED" == 0 ]]; then echo "E2E correcto."; else echo "E2E con fallos."; fi
exit "$FAILED"
