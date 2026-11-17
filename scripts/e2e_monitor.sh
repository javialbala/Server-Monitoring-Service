#!/usr/bin/env bash
# Prueba extremo a extremo con Docker real, en un proyecto aislado (sms-e2e, puerto 8010).
# Borra siempre el proyecto y el contenedor de prueba al terminar. Sale con 1 si algo falla.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PORT=8010
BASE="http://127.0.0.1:$PORT"
WORK="$(mktemp -d)"
JAR="$WORK/cookies.txt"
OVERRIDE="$WORK/override.yaml"
COMPOSE=(docker compose -p sms-e2e -f docker-compose.yml -f "$OVERRIDE")
EXTERNAL="monitor-e2e-$RANDOM"
FAILED=0

cleanup() {
    docker rm -f "$EXTERNAL" >/dev/null 2>&1
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
check_json() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if eval(sys.argv[2]) else 1)' "$1" "$2"; }
get() { curl -s -f -b "$JAR" "$BASE$1" -o "$2"; }  # get RUTA ARCHIVO

# Las contraseñas son aleatorias y nunca se imprimen. Solo existen en el override temporal.
PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')"
OTHER_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')"
DOCKER_GID="$(stat -c %g /var/run/docker.sock)"
write_override() {  # write_override CONTRASEÑA (vacía = panel sin contraseña)
    cat >"$OVERRIDE" <<YAML
services:
  panel:
    environment:
      APP_PASSWORD: "$1"
    ports: !override
      - "127.0.0.1:$PORT:8000"
  agent:
    group_add: !override ["$DOCKER_GID"]
YAML
}
login() {  # login CONTRASEÑA -> imprime el código HTTP (la contraseña no pasa por argumentos)
    E2E_PASSWORD="$1" python3 -c \
        'import json,os; print(json.dumps({"password": os.environ["E2E_PASSWORD"]}))' |
        curl -s -o /dev/null -w '%{http_code}' -c "$JAR" -H 'Content-Type: application/json' \
            -d @- "$BASE/api/login"
}
panel_logs() { "${COMPOSE[@]}" logs --no-color panel 2>&1; }
# La salida se guarda antes de buscar: con grep -q y pipefail el cierre anticipado daría fallo.
logs_say() { local logs; logs="$(panel_logs)"; grep -qF -- "$1" <<<"$logs"; }
logs_hide() { local logs; logs="$(panel_logs)"; ! grep -qF -- "$1" <<<"$logs"; }
logs_hide_both() { logs_hide "$PASSWORD" && logs_hide "$OTHER_PASSWORD"; }

echo "== Arranque sin contraseña"
write_override ""
"${COMPOSE[@]}" up -d --build >/dev/null 2>&1
# Con restart: unless-stopped el contenedor alterna entre "exited" y "restarting".
panel_exited_with_error() {
    for _ in $(seq 60); do
        [[ "$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' \
            "$("${COMPOSE[@]}" ps -a -q panel)")" =~ ^(exited|restarting)\ 1$ ]] && return 0
        sleep 1
    done
    return 1
}
step "con APP_PASSWORD vacía el panel sale con código 1" panel_exited_with_error
step "el log explica que falta APP_PASSWORD" logs_say "APP_PASSWORD falta"
step "el log no contiene tracebacks" logs_hide "Traceback"

echo "== Despliegue"
write_override "$PASSWORD"
step "docker compose up -d con la contraseña definida" "${COMPOSE[@]}" up -d --wait
step "el panel no tiene el socket de Docker" "${COMPOSE[@]}" exec -T panel test ! -e /var/run/docker.sock
not_root() { [[ "$("${COMPOSE[@]}" exec -T "$1" id -u)" != 0 ]]; }
step "panel: no es root" not_root panel
step "agente: no es root" not_root agent
step "panel: raíz de solo lectura" not "${COMPOSE[@]}" exec -T panel touch /sms-e2e
step "agente: raíz de solo lectura" not "${COMPOSE[@]}" exec -T agent touch /sms-e2e
agent_has_no_ports() {
    [[ "$(docker inspect --format '{{json .HostConfig.PortBindings}}' "$("${COMPOSE[@]}" ps -q agent)")" == "{}" ]]
}
step "el agente no publica puertos" agent_has_no_ports
step "el agente no es accesible desde el anfitrión (8001)" not curl -s --max-time 3 -o /dev/null http://127.0.0.1:8001/health
agent_answers_without_token() {
    "${COMPOSE[@]}" exec -T panel python -c \
        "import urllib.request; urllib.request.urlopen('http://agent:8001/containers', timeout=5)"
}
step "el agente responde sin token desde la red interna" agent_answers_without_token
step "el agente no tiene salida a Internet" not "${COMPOSE[@]}" exec -T agent python -c \
    "import urllib.request; urllib.request.urlopen('http://1.1.1.1', timeout=3)"
step "los logs del panel no contienen la contraseña" logs_hide "$PASSWORD"

echo "== Autenticación"
step "GET /api/metrics sin sesión -> 401" expect_code 401 "$BASE/api/metrics"
step "GET /api/containers sin sesión -> 401" expect_code 401 "$BASE/api/containers"
step "login con contraseña incorrecta -> 401" test "$(login "incorrecta")" == "401"
step "login correcto -> 204 con cookie" test "$(login "$PASSWORD")" == "204"

echo "== Métricas del anfitrión"
get /api/metrics "$WORK/m1.json"
step "CPU: porcentaje entre 0 y 100 y núcleos > 0" check_json "$WORK/m1.json" \
    '0 <= d["cpu"]["percent"] <= 100 and d["cpu"]["cores"] > 0'
step "RAM: total igual a MemTotal del anfitrión" check_json "$WORK/m1.json" \
    "d['memory']['total_bytes'] == $(awk '/^MemTotal:/ {print $2 * 1024}' /proc/meminfo)"
step "RAM: usada + disponible = total y porcentaje coherente" check_json "$WORK/m1.json" \
    'd["memory"]["used_bytes"] + d["memory"]["available_bytes"] == d["memory"]["total_bytes"] and 0 <= d["memory"]["percent"] <= 100'
step "Disco raíz: total igual al de / en el anfitrión (df)" check_json "$WORK/m1.json" \
    "d['disks'][0]['path'] == '/' and d['disks'][0]['total_bytes'] == $(df -B1 --output=size / | tail -1)"
step "Discos: porcentajes entre 0 y 100" check_json "$WORK/m1.json" \
    'all(0 <= disk["percent"] <= 100 for disk in d["disks"])'
# Temperatura general: la del paquete del procesador (coretemp "Package id 0"), si existe.
HOST_TEMP="$(for h in /sys/class/hwmon/hwmon*; do
    [[ "$(cat "$h/name" 2>/dev/null)" == coretemp ]] || continue
    for l in "$h"/temp*_label; do
        [[ "$(cat "$l")" == "Package id 0" ]] && echo $(($(cat "${l%_label}_input") / 1000))
    done
done | head -1)"
if [[ -n "$HOST_TEMP" ]]; then
    step "Temperatura general igual a la del paquete del procesador (±5 °C)" check_json "$WORK/m1.json" \
        "abs(d['temperature']['celsius'] - $HOST_TEMP) <= 5"
else
    echo "AVISO  este equipo no tiene coretemp: no se compara la temperatura"
fi
# Red: las interfaces que devuelve deben existir en el anfitrión (no las del contenedor).
HOST_IFACES="$(awk -F: 'NR > 2 {gsub(/ /, "", $1); print $1}' /proc/net/dev | tr '\n' ' ')"
step "Red: interfaces del anfitrión (no solo las del contenedor) y sin lo/veth/docker" check_json "$WORK/m1.json" \
    "d['network']['interfaces'] and all(i['name'] in '$HOST_IFACES'.split() and i['name'] != 'lo' and not i['name'].startswith(('veth', 'docker', 'br-')) for i in d['network']['interfaces'])"
step "Red: el total es la suma de las interfaces" check_json "$WORK/m1.json" \
    "d['network']['rx_bytes'] == sum(i['rx_bytes'] for i in d['network']['interfaces'])"
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
step "lista el mismo número de contenedores que docker ps -a" check_json "$WORK/c1.json" \
    "len(d['containers']) == $(docker ps -a -q | wc -l)"
step "los contenedores en ejecución aparecen primero" check_json "$WORK/c1.json" \
    "[c['state'] == 'running' for c in d['containers']] == sorted((c['state'] == 'running' for c in d['containers']), reverse=True)"
docker stop -t 1 "$EXTERNAL" >/dev/null
get /api/containers "$WORK/c2.json"
step "un contenedor detenido sigue apareciendo, con estado exited" check_json "$WORK/c2.json" \
    "[c['state'] for c in d['containers'] if c['name'] == '$EXTERNAL'] == ['exited']"

echo "== Solo lectura"
# `docker events --since` tiene resolución de segundos: las esperas evitan que la ventana
# incluya la parada del contenedor de prueba. Se excluyen los healthchecks de Docker.
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
step "el agente no puede escribir en /hostfs (solo lectura)" not "${COMPOSE[@]}" exec -T agent touch /hostfs/tmp/sms-e2e
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

echo "== Cambio de contraseña"
write_override "$OTHER_PASSWORD"
step "docker compose up -d con la nueva APP_PASSWORD" "${COMPOSE[@]}" up -d --wait
step "la contraseña nueva inicia sesión (204)" test "$(login "$OTHER_PASSWORD")" == "204"
step "la contraseña antigua da 401" test "$(login "$PASSWORD")" == "401"
step "los logs no contienen ninguna de las dos contraseñas" logs_hide_both

if [[ "$FAILED" == 0 ]]; then echo "E2E correcto."; else echo "E2E con fallos."; fi
exit "$FAILED"
