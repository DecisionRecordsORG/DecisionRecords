#!/usr/bin/env bash
# Publish a built Enterprise image, restart the production VM on it, and put
# the previous image back when the new one does not come up healthy.
#
# Called by .github/workflows/deploy-enterprise.yml after the image has passed
# its pre-flight. It is a script rather than inline workflow steps so that every
# failure path can be run against stand-ins for docker, az and curl
# (tests/test_deploy_enterprise_script.py).
#
# The VM's systemd unit pulls and runs the `latest` tag on every start, so
# "deploying" means moving `latest` in the registry and restarting the service,
# and "rolling back" means moving `latest` back and restarting again.
#
# Required environment:
#   IMAGE_REPO        registry/repository, for example myregistry.example.io/app
#   IMAGE_TAG         tag of the image built by this run (the commit SHA); the
#                     image must already exist locally as IMAGE_REPO:IMAGE_TAG
#   RESOURCE_GROUP    Azure resource group of the VM
#   VM_NAME           Azure VM name
#   DB_HEALTH_URL     public URL of the route that reports the database
#                     (/health): it must answer with a healthy, connected body
#
# Optional environment:
#   SERVICE_NAME            systemd unit on the VM (default adr-app)
#   HEALTH_ATTEMPTS         probes after a restart (default 30)
#   HEALTH_INTERVAL         seconds between probes (default 10)
#   BASELINE_ATTEMPTS       probes of the running service before anything is
#                           changed (default 3)
#   DEPLOY_WHEN_UNHEALTHY   true to deploy although production is not healthy
#                           beforehand (deploying a fix during an outage)
#
# Exit status: 0 only when the new image is serving and healthy. Every other
# outcome exits non-zero, including a rollback that restored service.

set -euo pipefail

: "${IMAGE_REPO:?IMAGE_REPO is required}"
: "${IMAGE_TAG:?IMAGE_TAG is required}"
: "${RESOURCE_GROUP:?RESOURCE_GROUP is required}"
: "${VM_NAME:?VM_NAME is required}"
: "${DB_HEALTH_URL:?DB_HEALTH_URL is required}"
SERVICE_NAME="${SERVICE_NAME:-adr-app}"
HEALTH_ATTEMPTS="${HEALTH_ATTEMPTS:-30}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-10}"
BASELINE_ATTEMPTS="${BASELINE_ATTEMPTS:-3}"
DEPLOY_WHEN_UNHEALTHY="${DEPLOY_WHEN_UNHEALTHY:-false}"

NEW_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"
LATEST_IMAGE="${IMAGE_REPO}:latest"
# Local-only name that keeps the previous image addressable on the runner after
# the local `latest` tag has been moved to the new image. Never pushed.
PREVIOUS_LOCAL="deploy-rollback/previous:${IMAGE_TAG}"
VM_OK_MARKER="DEPLOY_VM_STEP_OK"
VM_OK_MARKER_SCRIPT="DEPLOY_VM_STEP''_OK"
PREVIOUS_DIGEST=""

log() { echo "deploy: $*"; }

summary() {
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    echo "$*" >> "$GITHUB_STEP_SUMMARY"
  fi
}

# Print the final verdict as a GitHub error annotation and stop.
die() {
  echo "::error title=Enterprise deploy failed::$*"
  summary "### Enterprise deploy FAILED"
  summary ""
  summary "$*"
  exit 1
}

# One probe of the database health route. Succeeds only on an HTTP success
# whose body says the application is healthy and its database is connected.
# The query string defeats any cache between the runner and the origin.
probe_once() {
  local body separator="?"
  case "$DB_HEALTH_URL" in *\?*) separator="&" ;; esac
  body="$(curl -fsS --max-time 15 "${DB_HEALTH_URL}${separator}deploy=${IMAGE_TAG}-${RANDOM}" 2>/dev/null)" || body=""
  LAST_PROBE_BODY="$body"
  printf '%s' "$body" | grep -Eq '"status": ?"healthy"' || return 1
  printf '%s' "$body" | grep -Eq '"database": ?"connected"' || return 1
  return 0
}

# wait_healthy <attempts> <label>
wait_healthy() {
  local attempts="$1" label="$2" i
  LAST_PROBE_BODY=""
  for ((i = 1; i <= attempts; i++)); do
    if probe_once; then
      log "${label}: healthy on attempt ${i}/${attempts}: ${LAST_PROBE_BODY}"
      return 0
    fi
    log "${label}: attempt ${i}/${attempts} not healthy (response: ${LAST_PROBE_BODY:0:300})"
    if [ "$i" -lt "$attempts" ]; then
      sleep "$HEALTH_INTERVAL"
    fi
  done
  return 1
}

# Pull `latest` on the VM and restart the service. `az vm run-command invoke`
# exits 0 even when the command it ran on the VM failed, so the VM-side script
# prints a marker only after every command succeeded and the marker is required.
# The marker is split with '' in the script text so that it can only appear in
# the output by being printed on the VM, never by the command being echoed back.
restart_vm_on_latest() {
  local output
  log "VM: pulling ${LATEST_IMAGE} and restarting ${SERVICE_NAME}"
  if ! output="$(az vm run-command invoke \
      --resource-group "$RESOURCE_GROUP" \
      --name "$VM_NAME" \
      --command-id RunShellScript \
      --scripts "docker pull ${LATEST_IMAGE} && systemctl restart ${SERVICE_NAME} && echo ${VM_OK_MARKER_SCRIPT}" \
      --query 'value[0].message' \
      --output tsv 2>&1)"; then
    log "VM: az vm run-command failed:"
    printf '%s\n' "$output"
    return 1
  fi
  printf '%s\n' "$output"
  if ! printf '%s' "$output" | grep -Fq "$VM_OK_MARKER"; then
    log "VM: the pull or the restart failed on the VM (no ${VM_OK_MARKER} in the output)"
    return 1
  fi
  return 0
}

# Move `latest` in the registry back to the image recorded before this deploy.
repoint_latest_to_previous() {
  log "rollback: re-pointing ${LATEST_IMAGE} to the previous image ${PREVIOUS_DIGEST}"
  docker tag "$PREVIOUS_LOCAL" "$LATEST_IMAGE" || return 1
  docker push "$LATEST_IMAGE" || return 1
  return 0
}

# Print the registry digest reference (repo@sha256:...) of a local image.
repo_digest() {
  docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$1" 2>/dev/null \
    | grep -F "${IMAGE_REPO}@sha256:" | head -n 1 || true
}

# rollback <vm-touched: yes|no> <reason>
# Always ends the script with a failure; the message says whether production
# is back on the previous image.
rollback() {
  local vm_touched="$1" reason="$2" state
  echo "::warning title=Rolling back::${reason}"
  if ! repoint_latest_to_previous; then
    if [ "$vm_touched" = "yes" ]; then
      state="PRODUCTION IS STILL ON THE FAILED IMAGE."
    else
      state="The VM was never restarted, but it will pull 'latest' on its next restart."
    fi
    die "${reason} ROLLBACK FAILED: could not re-point ${LATEST_IMAGE} to ${PREVIOUS_DIGEST}. ${state} The registry tag 'latest' may still be the new image ${NEW_IMAGE}. Re-point 'latest' to ${PREVIOUS_DIGEST} by hand and restart ${SERVICE_NAME}."
  fi
  if [ "$vm_touched" = "no" ]; then
    if wait_healthy "$BASELINE_ATTEMPTS" "after tag rollback"; then
      die "${reason} The VM was never restarted and 'latest' points to the previous image ${PREVIOUS_DIGEST} again. Production is unchanged and healthy."
    fi
    die "${reason} The VM was never restarted and 'latest' points to the previous image ${PREVIOUS_DIGEST} again, but production does not report healthy at ${DB_HEALTH_URL}. Check the service."
  fi
  if ! restart_vm_on_latest; then
    log "rollback: the VM restart command did not confirm success; checking health anyway"
  fi
  if wait_healthy "$HEALTH_ATTEMPTS" "after rollback"; then
    die "${reason} ROLLBACK RESTORED SERVICE: 'latest' points to the previous image ${PREVIOUS_DIGEST} and production is healthy on it. The failed image is still in the registry as ${NEW_IMAGE} for diagnosis."
  fi
  die "${reason} ROLLBACK DID NOT RESTORE SERVICE: 'latest' points to the previous image ${PREVIOUS_DIGEST} but production is still not healthy at ${DB_HEALTH_URL}. PRODUCTION IS DOWN. Read the service journal on the VM (journalctl -u ${SERVICE_NAME})."
}

# --- 1. Nothing has been changed yet: check what we are about to replace ------

docker image inspect "$NEW_IMAGE" >/dev/null 2>&1 \
  || die "The image ${NEW_IMAGE} does not exist on this runner. Nothing was published or deployed."

log "checking production before changing anything: ${DB_HEALTH_URL}"
if wait_healthy "$BASELINE_ATTEMPTS" "before deploy"; then
  :
elif [ "$DEPLOY_WHEN_UNHEALTHY" = "true" ]; then
  echo "::warning title=Deploying onto an unhealthy service::Production did not report healthy before the deploy; continuing because deploy_when_unhealthy was set. A rollback would return to that unhealthy state."
else
  die "Production does not report a healthy, connected database at ${DB_HEALTH_URL} before the deploy, so this run could not tell a good deploy from a bad one. Nothing was published or deployed. If production is down and this deploy is the fix, run the workflow again with deploy_when_unhealthy enabled."
fi

log "recording the image 'latest' points to before the deploy"
if ! docker pull "$LATEST_IMAGE"; then
  die "Could not pull ${LATEST_IMAGE}, so there would be no image to roll back to. Nothing was published or deployed."
fi
PREVIOUS_DIGEST="$(repo_digest "$LATEST_IMAGE")"
if [ -z "$PREVIOUS_DIGEST" ]; then
  die "Could not read the registry digest of ${LATEST_IMAGE}, so there would be no image to roll back to. Nothing was published or deployed."
fi
docker tag "$LATEST_IMAGE" "$PREVIOUS_LOCAL" \
  || die "Could not keep a local copy of the previous image. Nothing was published or deployed."
log "previous image: ${PREVIOUS_DIGEST}"
summary "Previous image (rollback target): \`${PREVIOUS_DIGEST}\`"

# --- 2. Publish the commit tag. `latest` is still the previous image ----------

if ! docker push "$NEW_IMAGE"; then
  die "Pushing ${NEW_IMAGE} failed. 'latest' was not moved and the VM was not touched; production is unchanged."
fi

# --- 3. Point of no return: move `latest`, restart, verify --------------------

if ! docker tag "$NEW_IMAGE" "$LATEST_IMAGE" || ! docker push "$LATEST_IMAGE"; then
  rollback no "Pushing ${NEW_IMAGE} as 'latest' failed part-way."
fi
NEW_DIGEST="$(repo_digest "$NEW_IMAGE")"
log "'latest' now points to ${NEW_DIGEST:-$NEW_IMAGE}"

if ! restart_vm_on_latest; then
  rollback yes "The VM could not pull or restart on the new image ${NEW_IMAGE}."
fi

if ! wait_healthy "$HEALTH_ATTEMPTS" "after deploy"; then
  rollback yes "The new image ${NEW_IMAGE} did not report a healthy, connected database at ${DB_HEALTH_URL} after the restart."
fi

log "deployed ${NEW_IMAGE} (${NEW_DIGEST:-digest unknown}); previous image was ${PREVIOUS_DIGEST}"
summary "### Enterprise deploy succeeded"
summary ""
summary "Now serving \`${NEW_IMAGE}\` (\`${NEW_DIGEST:-digest unknown}\`)."
