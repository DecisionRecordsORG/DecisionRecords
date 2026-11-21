#!/usr/bin/env bash
# Boot a built Community Edition image and prove it actually serves requests.
#
# Building an image does not import the application. v2.1.0 was published with
# a root module missing from the image and crashed at startup, while every CI
# job stayed green. This script is the gate that runs the real artifact.
#
# Usage:
#   scripts/smoke_test_ce_image.sh <image-ref>
#
# Optional environment:
#   SMOKE_PORT              host port to publish (default 18080)
#   SMOKE_TIMEOUT           seconds to wait for the HTTP health route (default 90)
#   SMOKE_HEALTHY_TIMEOUT   seconds to wait for the Docker HEALTHCHECK (default 120)
#   SMOKE_EXPECT_VERSION    fail unless /api/version reports this version
#
# The container gets the same configuration a self-hosting user must supply:
# only SECRET_KEY. Everything else comes from the image defaults (SQLite under
# /data, community edition).

set -euo pipefail

IMAGE="${1:?usage: smoke_test_ce_image.sh <image-ref>}"
PORT="${SMOKE_PORT:-18080}"
TIMEOUT="${SMOKE_TIMEOUT:-90}"
HEALTHY_TIMEOUT="${SMOKE_HEALTHY_TIMEOUT:-120}"
EXPECT_VERSION="${SMOKE_EXPECT_VERSION:-}"
CONTAINER="ce-smoke-$$"
BASE_URL="http://127.0.0.1:${PORT}"

dump_logs() {
  echo "::group::Container state"
  docker inspect --format 'status={{.State.Status}} exit={{.State.ExitCode}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER" 2>&1 || true
  echo "::endgroup::"
  echo "::group::Container logs"
  docker logs "$CONTAINER" 2>&1 || true
  echo "::endgroup::"
}

fail() {
  echo "smoke: FAILED - $*" >&2
  dump_logs
  exit 1
}

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

container_running() {
  [ "$(docker inspect --format '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" = "true" ]
}

echo "smoke: starting ${IMAGE} as ${CONTAINER} on ${BASE_URL}"
docker run -d --name "$CONTAINER" \
  -p "127.0.0.1:${PORT}:8000" \
  -e SECRET_KEY=ci-smoke-test-secret-key-0123456789abcdef \
  "$IMAGE" >/dev/null

# 1. The HTTP health route used by the Dockerfile HEALTHCHECK must answer.
echo "smoke: waiting up to ${TIMEOUT}s for ${BASE_URL}/api/health"
deadline=$((SECONDS + TIMEOUT))
until curl -fsS --max-time 5 "${BASE_URL}/api/health" >/dev/null 2>&1; do
  if ! container_running; then
    fail "container exited before /api/health answered"
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    fail "/api/health did not answer within ${TIMEOUT}s"
  fi
  sleep 2
done
echo "smoke: /api/health -> $(curl -fsS --max-time 5 "${BASE_URL}/api/health")"

# 2. Database initialisation must have succeeded (schema creation + migrations).
health_body="$(curl -sS --max-time 10 "${BASE_URL}/health" || true)"
echo "smoke: /health -> ${health_body}"
if ! printf '%s' "$health_body" | grep -Eq '"status": ?"healthy"'; then
  fail "/health did not report a healthy database"
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

# 5. Files that must never ship are absent from the runtime image.
for forbidden in /app/ee /app/tests /app/run_local.py /app/.env /app/local_secrets.py; do
  if docker exec "$CONTAINER" test -e "$forbidden"; then
    fail "${forbidden} exists in the image"
  fi
done
echo "smoke: no private, test or local-only files in /app"

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
  if ! container_running; then
    fail "container exited while waiting for the Docker HEALTHCHECK"
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    fail "Docker HEALTHCHECK still '${status}' after ${HEALTHY_TIMEOUT}s"
  fi
  sleep 3
done
echo "smoke: Docker HEALTHCHECK is healthy"

echo "smoke: PASSED for ${IMAGE}"
