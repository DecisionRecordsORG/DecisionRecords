#!/usr/bin/env bash
# Boot a built Decision Records image and prove it actually serves requests.
#
# Building an image does not import the application. v2.1.0 was published with
# a root module missing from the image and crashed at startup, while every CI
# job stayed green. On 2026-11-21 a freshly built image could not load its
# PostgreSQL driver and took production down, because every check before the
# deploy ran on SQLite. This script is the gate that runs the real artifact,
# against the database it will be used with.
#
# Usage:
#   scripts/smoke_test_ce_image.sh <image-ref>
#
# Optional environment:
#   SMOKE_DATABASE          sqlite (default) or postgres. With postgres the
#                           script starts a throwaway PostgreSQL container on a
#                           private Docker network and points the image at it
#                           with a postgresql:// DATABASE_URL.
#   SMOKE_PROFILE           community (default) or enterprise. The enterprise
#                           profile is the deploy pre-flight: Azure Key Vault
#                           and the Cloudflare origin check are switched off so
#                           the image can boot on a CI runner.
#   SMOKE_POSTGRES_IMAGE    PostgreSQL image for SMOKE_DATABASE=postgres
#                           (default postgres:15-alpine, the self-hosting example)
#   SMOKE_PORT              host port to publish (default 18080)
#   SMOKE_TIMEOUT           seconds to wait for the HTTP health route (default 90)
#   SMOKE_HEALTHY_TIMEOUT   seconds to wait for the Docker HEALTHCHECK (default 120)
#   SMOKE_EXPECT_VERSION    fail unless /api/version reports this version
#
# The community profile gives the container the same configuration a
# self-hosting user must supply: only SECRET_KEY, plus DATABASE_URL when
# PostgreSQL is used. Everything else comes from the image defaults. The
# PostgreSQL server is a stock image without TLS and the URL carries no
# options, exactly as docs/self-hosting.md describes.

set -euo pipefail

IMAGE="${1:?usage: smoke_test_ce_image.sh <image-ref>}"
DATABASE="${SMOKE_DATABASE:-sqlite}"
PROFILE="${SMOKE_PROFILE:-community}"
POSTGRES_IMAGE="${SMOKE_POSTGRES_IMAGE:-postgres:15-alpine}"
PORT="${SMOKE_PORT:-18080}"
TIMEOUT="${SMOKE_TIMEOUT:-90}"
HEALTHY_TIMEOUT="${SMOKE_HEALTHY_TIMEOUT:-120}"
EXPECT_VERSION="${SMOKE_EXPECT_VERSION:-}"
CONTAINER="ce-smoke-$$"
PG_CONTAINER="ce-smoke-pg-$$"
NETWORK="ce-smoke-net-$$"
BASE_URL="http://127.0.0.1:${PORT}"
PG_USER="decisions"
PG_PASSWORD="smoke-test-password"
PG_DATABASE="decisions"

case "$DATABASE" in
  sqlite|postgres) ;;
  *) echo "smoke: SMOKE_DATABASE must be sqlite or postgres, got '${DATABASE}'" >&2; exit 2 ;;
esac
case "$PROFILE" in
  community|enterprise) ;;
  *) echo "smoke: SMOKE_PROFILE must be community or enterprise, got '${PROFILE}'" >&2; exit 2 ;;
esac

dump_logs() {
  echo "::group::Container state"
  docker inspect --format 'status={{.State.Status}} exit={{.State.ExitCode}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER" 2>&1 || true
  echo "::endgroup::"
  echo "::group::Container logs"
  docker logs "$CONTAINER" 2>&1 || true
  echo "::endgroup::"
  if [ "$DATABASE" = "postgres" ]; then
    echo "::group::PostgreSQL logs"
    docker logs "$PG_CONTAINER" 2>&1 || true
    echo "::endgroup::"
  fi
}

fail() {
  echo "smoke: FAILED - $*" >&2
  dump_logs
  exit 1
}

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  if [ "$DATABASE" = "postgres" ]; then
    docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

container_running() {
  [ "$(docker inspect --format '{{.State.Running}}' "$1" 2>/dev/null)" = "true" ]
}

pg_query() {
  docker exec -e PGPASSWORD="$PG_PASSWORD" "$PG_CONTAINER" psql -h 127.0.0.1 -U "$PG_USER" -d "$PG_DATABASE" -Atc "$1"
}

run_args=(-d --name "$CONTAINER" -p "127.0.0.1:${PORT}:8000"
  -e SECRET_KEY=ci-smoke-test-secret-key-0123456789abcdef)
run_command=()

# 0. With SMOKE_DATABASE=postgres, start the database the image will use.
if [ "$DATABASE" = "postgres" ]; then
  echo "smoke: starting ${POSTGRES_IMAGE} as ${PG_CONTAINER} on network ${NETWORK}"
  docker network create "$NETWORK" >/dev/null
  docker run -d --name "$PG_CONTAINER" --network "$NETWORK" \
    -e POSTGRES_USER="$PG_USER" \
    -e POSTGRES_PASSWORD="$PG_PASSWORD" \
    -e POSTGRES_DB="$PG_DATABASE" \
    "$POSTGRES_IMAGE" >/dev/null

  # Probe over TCP: while the image initialises it runs a temporary server that
  # only listens on the Unix socket, and that one must not count as ready.
  deadline=$((SECONDS + 60))
  until docker exec "$PG_CONTAINER" pg_isready -q -h 127.0.0.1 -U "$PG_USER" -d "$PG_DATABASE" >/dev/null 2>&1; do
    if ! container_running "$PG_CONTAINER"; then
      fail "PostgreSQL container exited before it accepted connections"
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
      fail "PostgreSQL did not accept connections within 60s"
    fi
    sleep 1
  done
  echo "smoke: PostgreSQL is accepting connections ($(pg_query 'show server_version'))"

  run_args+=(--network "$NETWORK"
    -e "DATABASE_URL=postgresql://${PG_USER}:${PG_PASSWORD}@${PG_CONTAINER}:5432/${PG_DATABASE}")
fi

if [ "$PROFILE" = "enterprise" ]; then
  # An empty AZURE_KEYVAULT_URL makes the Key Vault client fall back to
  # environment variables, and SKIP_CLOUDFLARE_CHECK lets a request that did
  # not come through Cloudflare reach the app. The image's own start script
  # talks to the Azure instance metadata service first, which a CI runner does
  # not provide, so gunicorn is started directly with the same worker class.
  run_args+=(-e AZURE_KEYVAULT_URL= -e SKIP_CLOUDFLARE_CHECK=true)
  run_command=(gunicorn --bind 0.0.0.0:8000 --workers 2 --worker-class gthread
    --threads 4 --timeout 120 --no-sendfile app:app)
fi

echo "smoke: starting ${IMAGE} as ${CONTAINER} on ${BASE_URL} (profile=${PROFILE}, database=${DATABASE})"
docker run "${run_args[@]}" "$IMAGE" ${run_command[@]+"${run_command[@]}"} >/dev/null

# 1. The HTTP health route used by the Dockerfile HEALTHCHECK must answer.
echo "smoke: waiting up to ${TIMEOUT}s for ${BASE_URL}/api/health"
deadline=$((SECONDS + TIMEOUT))
until curl -fsS --max-time 5 "${BASE_URL}/api/health" >/dev/null 2>&1; do
  if ! container_running "$CONTAINER"; then
    fail "container exited before /api/health answered"
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    fail "/api/health did not answer within ${TIMEOUT}s"
  fi
  sleep 2
done
echo "smoke: /api/health -> $(curl -fsS --max-time 5 "${BASE_URL}/api/health")"

# 2. Database initialisation must have succeeded (schema creation + migrations).
#    /api/health answers even when the database is unreachable; /health is the
#    route that reports the database.
health_body="$(curl -sS --max-time 30 "${BASE_URL}/health" || true)"
echo "smoke: /health -> ${health_body}"
if ! printf '%s' "$health_body" | grep -Eq '"status": ?"healthy"'; then
  fail "/health did not report a healthy database"
fi
if ! printf '%s' "$health_body" | grep -Eq '"database": ?"connected"'; then
  fail "/health did not report a connected database"
fi

# 2a. Start-up logs errors it survives. A failed migration is only a warning to
#     the app, but it is a broken install.
app_logs="$(docker logs "$CONTAINER" 2>&1 || true)"
for marker in "Database initialization failed" "Schema migration check failed"; do
  if printf '%s' "$app_logs" | grep -Fq "$marker"; then
    fail "container log contains '${marker}'"
  fi
done

# 2b. With PostgreSQL, the schema must really be in that server (not in a
#     SQLite file the image fell back to), created by the app's own start-up.
if [ "$DATABASE" = "postgres" ]; then
  table_count="$(pg_query "select count(*) from information_schema.tables where table_schema = 'public'" || true)"
  migration_count="$(pg_query "select count(*) from schema_migrations" || true)"
  echo "smoke: PostgreSQL has ${table_count:-?} tables and ${migration_count:-?} recorded migrations"
  case "$table_count" in
    ''|*[!0-9]*) fail "could not count tables in PostgreSQL" ;;
  esac
  [ "$table_count" -ge 10 ] || fail "PostgreSQL has only ${table_count} tables after start-up"
  case "$migration_count" in
    ''|*[!0-9]*) fail "could not read schema_migrations in PostgreSQL" ;;
  esac
  [ "$migration_count" -ge 1 ] || fail "no migrations recorded in PostgreSQL"
  driver_versions="$(docker exec "$CONTAINER" python -c 'import sqlalchemy, psycopg2; print("SQLAlchemy", sqlalchemy.__version__, "psycopg2", psycopg2.__version__)' 2>&1)" \
    || fail "the PostgreSQL driver cannot be imported inside the image: ${driver_versions}"
  echo "smoke: ${driver_versions}"
fi

# 3. The version endpoint must answer, and match the release when asked to.
version_body="$(curl -fsS --max-time 10 "${BASE_URL}/api/version" || true)"
echo "smoke: /api/version -> ${version_body}"
[ -n "$version_body" ] || fail "/api/version did not answer"
if [ -n "$EXPECT_VERSION" ]; then
  if ! printf '%s' "$version_body" | grep -Fq "\"${EXPECT_VERSION}\""; then
    fail "/api/version does not report version ${EXPECT_VERSION}"
  fi
fi

# 4. The Angular frontend must have been built into the image.
index_body="$(curl -fsS --max-time 10 "${BASE_URL}/" || true)"
case "$index_body" in
  *"<app-root"*) echo "smoke: / serves the Angular application shell" ;;
  *) fail "/ did not serve the Angular application shell" ;;
esac

# 5. Files that must never ship are absent from the Community runtime image.
#    (The Enterprise image contains ee/ by design.)
if [ "$PROFILE" = "community" ]; then
  for forbidden in /app/ee /app/tests /app/run_local.py /app/.env /app/local_secrets.py; do
    if docker exec "$CONTAINER" test -e "$forbidden"; then
      fail "${forbidden} exists in the image"
    fi
  done
  echo "smoke: no private, test or local-only files in /app"
fi

# 6. The image's own HEALTHCHECK must turn healthy (proves curl and the probe
#    command inside the image, which is what orchestrators rely on).
echo "smoke: waiting up to ${HEALTHY_TIMEOUT}s for the Docker HEALTHCHECK"
deadline=$((SECONDS + HEALTHY_TIMEOUT))
while :; do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER" 2>/dev/null || echo unknown)"
  case "$status" in
    healthy) break ;;
    none) fail "image defines no HEALTHCHECK" ;;
    unhealthy) fail "Docker HEALTHCHECK reported unhealthy" ;;
  esac
  if ! container_running "$CONTAINER"; then
    fail "container exited while waiting for the Docker HEALTHCHECK"
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    fail "Docker HEALTHCHECK still '${status}' after ${HEALTHY_TIMEOUT}s"
  fi
  sleep 3
done
echo "smoke: Docker HEALTHCHECK is healthy"

echo "smoke: PASSED for ${IMAGE} (profile=${PROFILE}, database=${DATABASE})"
