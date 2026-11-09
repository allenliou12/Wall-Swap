#!/bin/sh
set -u
# Sandbox: danger-full-access by default (allen approved it for this repo, D6): workspace-write cannot use the uv cache.

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd) || exit 1
lanes=${CODEX_LANES_DIR:-"$repo_root/.scratch/codex-lanes"}

usage() {
  echo 'Usage: codex-lane.sh launch <name> <brief.md> <lane-dir>'
  echo '       codex-lane.sh stop <name>'
  echo '       codex-lane.sh status [<name>]'
  echo '       codex-lane.sh --self-test'
  exit 2
}

validate_name() {
  case $1 in
    ''|.|..|*[!A-Za-z0-9._-]*) echo 'Lane name must contain only letters, numbers, dots, underscores or hyphens.' >&2; exit 2 ;;
  esac
}

lane_pattern() {
  escaped=$(printf '%s\n' "$1/final.md" | sed 's/[][\\.^$*+?(){}|]/\\&/g')
  printf ' -o %s -$\n' "$escaped"
}

live_pids() {
  pgrep -f -- "$(lane_pattern "$1")"
}

launch() {
  validate_name "$1"
  state="$lanes/$1"
  brief=$2
  workdir=$(CDPATH= cd -- "$3" && pwd) || exit 2
  [ -f "$brief" ] && [ -r "$brief" ] || { echo "Cannot read brief: $brief" >&2; exit 2; }
  mkdir -p "$state" || exit 1
  state=$(CDPATH= cd -- "$state" && pwd -P) || exit 1
  if pids=$(live_pids "$state"); then
    echo "Lane $1 already has live Codex pid(s) $(echo "$pids" | tr '\n' ' '); use codex-lane.sh stop $1." >&2
    exit 2
  fi
  # ponytail: Two near-simultaneous launches can both start; callers must serialize launches.
  if [ -f "$state/log" ]; then mv -f "$state/log" "$state/log.prev" || exit 1; fi
  if [ -f "$state/final.md" ]; then mv -f "$state/final.md" "$state/final.prev.md" || exit 1; fi
  rm -f "$state/exit" || exit 1
  date +%s > "$state/started" || exit 1
  cp "$brief" "$state/brief.md" || exit 1
  codex exec -m "${CODEX_MODEL:-gpt-6.1-sol}" -c model_reasoning_effort='"xhigh"' \
    -s "${CODEX_SANDBOX:-danger-full-access}" -C "$workdir" -o "$state/final.md" - < "$state/brief.md" >> "$state/log" 2>&1
  code=$?
  [ -f "$state/exit" ] || printf '%s\n' "$code" > "$state/exit" || exit 1
  exit "$code"
}

stop() {
  validate_name "$1"
  state="$lanes/$1"
  if [ ! -d "$state" ]; then
    echo "Lane $1: no Codex is running."
    return 0
  fi
  state=$(CDPATH= cd -- "$state" && pwd -P) || exit 1
  if ! pids=$(live_pids "$state"); then
    echo "Lane $1: no Codex is running."
    return 0
  fi
  own_pgid=$(ps -o pgid= -p $$ | tr -d '[:space:]')
  groups=$(for pid in $pids; do ps -o pgid= -p "$pid"; done | sort -u)
  pgids=''
  for pgid in $groups; do
    [ "$pgid" = "$own_pgid" ] || pgids="$pgids $pgid"
  done
  [ -n "$pgids" ] || { echo "Lane $1: refusing to signal the caller's process group." >&2; return 1; }
  for pgid in $pgids; do kill -TERM -- "-$pgid" 2>/dev/null; done
  deadline=$(($(date +%s) + 10))
  while [ -n "$pgids" ] && [ "$(date +%s)" -lt "$deadline" ]; do
    remaining=''
    for pgid in $pgids; do
      if kill -0 -- "-$pgid" 2>/dev/null; then remaining="$remaining $pgid"; fi
    done
    pgids=$remaining
    [ -n "$pgids" ] || break
    sleep 0.1
  done
  for pgid in $pgids; do kill -KILL -- "-$pgid" 2>/dev/null; done
  printf '%s\n' stopped > "$state/exit" || exit 1
  printf 'Stopped lane %s (pid(s) %s).\n' "$1" "$(echo "$pids" | tr '\n' ' ')"
}

show_status() {
  state=$(CDPATH= cd -- "$lanes/$1" && pwd -P) || return 1
  now=$(date +%s)
  started=$(cat "$state/started" 2>/dev/null) || started=$now
  case $started in ''|*[!0-9]*) started=$now ;; esac
  finished=$now
  if live_pids "$state" >/dev/null; then
    result=running
  elif [ -f "$state/exit" ]; then
    result="done exit $(cat "$state/exit")"
    if ! finished=$(stat -f %m "$state/exit" 2>/dev/null); then
      finished=$(stat -c %Y "$state/exit" 2>/dev/null) || return 1
    fi
  elif [ -f "$state/started" ] && [ "$((now - started))" -lt 30 ]; then
    result=starting
  else
    result='dead — no Codex is running for this lane; relaunch is safe'
  fi
  elapsed=$((finished - started))
  [ "$elapsed" -ge 0 ] || elapsed=0
  log_age='log missing'
  if [ -f "$state/log" ]; then
    if ! modified=$(stat -f %m "$state/log" 2>/dev/null); then
      modified=$(stat -c %Y "$state/log" 2>/dev/null) || return 1
    fi
    age=$((now - modified))
    [ "$age" -ge 0 ] || age=0
    log_age="log ${age}s ago"
  fi
  printf '%s · %s · elapsed %sh %sm %ss · %s\n' "$1" "$result" \
    "$((elapsed / 3600))" "$((elapsed / 60 % 60))" "$((elapsed % 60))" "$log_age"
}

status() {
  if [ "$#" -eq 1 ]; then
    validate_name "$1"
    [ -f "$lanes/$1/started" ] || { echo "Unknown lane: $1" >&2; exit 2; }
    show_status "$1" || exit 1
    if [ -f "$lanes/$1/log" ]; then
      printf '\nLog (last 15 lines):\n'
      tail -n 15 "$lanes/$1/log"
    fi
    if [ -f "$lanes/$1/final.md" ]; then
      printf '\nFinal:\n'
      cat "$lanes/$1/final.md"
    fi
  else
    for lane_dir in "$lanes"/* "$lanes"/.[!.]* "$lanes"/..?*; do
      [ -d "$lane_dir" ] && [ -f "$lane_dir/started" ] || continue
      show_status "${lane_dir##*/}" || exit 1
    done
  fi
}

self_test() (
  set -m
  fixture=$(mktemp -d "${TMPDIR:-/tmp}/codex-lane-self-test.XXXXXX") || exit 1
  export CODEX_LANES_DIR="$fixture/"'lanes .[x](y)+{z}^$|\?'
  export FAKE_CODEX_RELEASE="$fixture/release"
  lane_pid=''
  child_pid=''
  cleanup() {
    pattern=$(printf '%s\n' "$fixture/" | sed 's/[][\\.^$*+?(){}|]/\\&/g')
    fixture_pids=$(pgrep -f -- "$pattern") || fixture_pids=''
    [ -z "$fixture_pids" ] || kill -TERM $fixture_pids 2>/dev/null
    [ -z "$child_pid" ] || kill -KILL "$child_pid" 2>/dev/null
    [ -z "$lane_pid" ] || wait "$lane_pid" 2>/dev/null
    rm -rf "$fixture"
  }
  fail() { echo "FAIL $*" >&2; cleanup; exit 1; }
  mkdir -p "$fixture/bin" || fail 'fixture directories'
  test_script="$script_dir/codex-lane.sh"
  cat > "$fixture/bin/codex" <<'FAKE'
#!/bin/sh
output=''
while [ "$#" -gt 0 ]; do
  case $1 in -o) output=$2; shift 2 ;; *) shift ;; esac
done
case $output in /*) ;; *) exit 8 ;; esac
[ "$(cat)" = 'fixture brief' ] || exit 9
echo 'fake codex stderr' >&2
echo 'fake codex running'
if [ "${FAKE_CODEX_CHILD:-0}" = 1 ]; then
  sleep 300 &
  printf 'fake child pid %s\n' "$!"
fi
: > "$FAKE_CODEX_READY"
while [ ! -f "$FAKE_CODEX_RELEASE" ]; do sleep 0.05; done
echo 'fixture final' > "$output"
exit 3
FAKE
  chmod +x "$fixture/bin/codex" || fail 'fake codex executable'
  export PATH="$fixture/bin:$PATH"
  printf 'fixture brief\n' > "$fixture/test brief.md"
  touch "$FAKE_CODEX_RELEASE"
  sh "$test_script" launch smoke "$fixture/test brief.md" > "$fixture/missing-dir" 2>&1
  [ "$?" -eq 2 ] || fail 'launch without lane-dir must exit 2'
  grep -Fq 'launch <name> <brief.md> <lane-dir>' "$fixture/missing-dir" || fail 'usage requires lane-dir'
  echo 'PASS launch requires lane-dir (exit 2)'

  state="$CODEX_LANES_DIR/watcher"
  mkdir -p "$state" || fail 'watcher state'
  state=$(CDPATH= cd -- "$state" && pwd -P) || fail 'absolute watcher state'
  printf '%s\n' "$(($(date +%s) - 60))" > "$state/started"
  : > "$state/final.md"
  sh -c 'while [ ! -s "$1" ]; do sleep 1; done' watcher "$state/final.md" &
  watcher_pid=$!
  tail -f "$state/final.md" > "$fixture/tail" 2>&1 &
  tail_pid=$!
  sh "$test_script" status watcher > "$fixture/status" || fail 'watcher status'
  grep -q 'watcher · dead — ' "$fixture/status" || fail 'watchers must not make a lane live'
  sh "$test_script" stop watcher > "$fixture/stop" || fail 'stop watcher-only lane'
  grep -q 'no Codex is running' "$fixture/stop" || fail 'watcher-only stop must find no Codex'
  kill -0 "$watcher_pid" 2>/dev/null && kill -0 "$tail_pid" 2>/dev/null || fail 'stop killed a watcher'
  echo 'PASS watcher loop and tail do not make a lane live and survive stop'

  wait_for_codex() {
    attempts=0
    until [ -f "$FAKE_CODEX_READY" ]; do
      kill -0 "$lane_pid" 2>/dev/null || fail 'launcher exited before Codex started'
      attempts=$((attempts + 1))
      [ "$attempts" -lt 100 ] || fail 'fake codex did not start'
      sleep 0.05
    done
  }
  start_lane() {
    state="$CODEX_LANES_DIR/$1"
    export FAKE_CODEX_RELEASE="$fixture/release-$1"
    export FAKE_CODEX_READY="$fixture/ready-$1"
    rm -f "$FAKE_CODEX_READY"
    # Give Codex its own group so stop leaves the launcher alive to record its exit.
    sh -c 'set -m; . "$0"' "$test_script" launch "$1" "$fixture/test brief.md" "$fixture" > "$fixture/launch-$1" 2>&1 &
    lane_pid=$!
    wait_for_codex
  }
  start_lane watcher
  kill -TERM "$watcher_pid" "$tail_pid" 2>/dev/null
  wait "$watcher_pid" "$tail_pid" 2>/dev/null
  printf '%s\n' stopped > "$state/exit"
  touch "$FAKE_CODEX_RELEASE"
  wait "$lane_pid"
  [ "$?" -eq 3 ] || fail 'watchers blocked launch'
  lane_pid=''
  [ "$(cat "$state/exit")" = stopped ] || fail 'launcher replaced an existing stopped exit'
  rm -rf "$CODEX_LANES_DIR/watcher"
  echo 'PASS watchers do not block launch; launcher preserves an existing stopped exit'
  start_lane smoke
  sh "$test_script" status smoke > "$fixture/status" || fail 'running status'
  grep -q 'smoke · running · elapsed ' "$fixture/status" || fail 'running state'
  sh "$test_script" launch smoke "$fixture/test brief.md" "$fixture" > "$fixture/duplicate" 2>&1
  [ "$?" -eq 2 ] || fail 'duplicate launch must exit 2'
  grep -Eq 'pid\(s\) [0-9]+' "$fixture/duplicate" || fail 'duplicate refusal names live processes'
  grep -Fq 'codex-lane.sh stop smoke' "$fixture/duplicate" || fail 'duplicate refusal explains stop'
  echo 'PASS live lane refuses a second launch with pids and stop command (exit 2)'
  touch "$FAKE_CODEX_RELEASE"
  wait "$lane_pid"
  code=$?
  lane_pid=''
  [ "$code" -eq 3 ] || fail 'launch must return Codex exit 3'
  [ -s "$state/started" ] && [ "$(cat "$state/exit")" = 3 ] || fail 'started/exit state'
  [ "$(cat "$state/final.md")" = 'fixture final' ] || fail 'final output'
  cmp "$fixture/test brief.md" "$state/brief.md" || fail 'copied brief'
  [ "$(ls -A "$state" | sort)" = "$(printf '%s\n' brief.md exit final.md log started)" ] || fail 'unexpected lane state files'
  echo 'PASS launch writes only brief, started, log, final and exit and returns 3'
  sh "$test_script" status smoke > "$fixture/status" || fail 'completed status'
  grep -Eq 'smoke · done exit 3 · elapsed [0-9]+h [0-9]+m [0-9]+s · log [0-9]+s ago' "$fixture/status" || fail 'completed state and elapsed field'
  grep -q 'fake codex stderr' "$fixture/status" && grep -q 'fixture final' "$fixture/status" || fail 'status log and final output'
  echo 'PASS status shows exit, elapsed, log age, log and final output'
  printf '%s\n' 1577934180 > "$state/started"
  TZ=UTC touch -t 202001020304.05 "$state/exit" || fail 'finished timestamp fixture'
  sh "$test_script" status smoke > "$fixture/status" || fail 'finished elapsed status'
  grep -q 'smoke · done exit 3 · elapsed 0h 1m 5s · ' "$fixture/status" || fail 'elapsed must stop at exit mtime'
  echo 'PASS completed elapsed stops at exit mtime (65 seconds)'

  rm -f "$FAKE_CODEX_RELEASE"
  start_lane smoke
  [ ! -f "$state/exit" ] || fail 'relaunch retained previous exit'
  [ -f "$state/log.prev" ] && grep -q 'fake codex stderr' "$state/log.prev" || fail 'previous log was not preserved'
  [ "$(cat "$state/final.prev.md")" = 'fixture final' ] || fail 'previous final was not preserved'
  [ "$(grep -c 'fake codex running' "$state/log")" -eq 1 ] || fail 'relaunch appended to old log'
  echo 'PASS relaunch rotates log and final output and removes exit'
  kill -KILL "$lane_pid" || fail 'kill launcher'
  wait "$lane_pid" 2>/dev/null
  lane_pid=''
  sh "$test_script" status smoke > "$fixture/status" || fail 'status after killing launcher'
  grep -q 'smoke · running · elapsed ' "$fixture/status" || fail 'killing launcher hides live Codex'
  sh "$test_script" launch smoke "$fixture/test brief.md" "$fixture" > "$fixture/duplicate" 2>&1
  [ "$?" -eq 2 ] || fail 'second launch accepted while orphaned Codex runs'
  sh "$test_script" stop smoke > "$fixture/stop" || fail 'stop orphaned Codex'
  grep -Eq 'Stopped lane smoke .*pid\(s\) [0-9]+' "$fixture/stop" || fail 'stop must name the processes'
  sh "$test_script" status smoke > "$fixture/status" || fail 'stopped status'
  grep -q 'smoke · done exit stopped · elapsed ' "$fixture/status" || fail 'orphaned lane must read done exit stopped'
  echo 'PASS SIGKILL leaves live Codex visible; stop ends it and reports done exit stopped'
  start_lane smoke
  touch "$FAKE_CODEX_RELEASE"
  wait "$lane_pid"
  code=$?
  lane_pid=''
  [ "$code" -eq 3 ] || fail 'relaunch after stop must return Codex exit 3'
  echo 'PASS relaunch after killing launcher and stopping Codex is accepted'
  sh "$test_script" stop smoke > "$fixture/stop" || fail 'stop completed lane'
  grep -q 'no Codex is running' "$fixture/stop" || fail 'stop completed lane message'
  [ "$(cat "$state/exit")" = 3 ] || fail 'empty stop changed completed exit'
  sh "$test_script" stop absent > "$fixture/stop" || fail 'stop absent lane'
  grep -q 'no Codex is running' "$fixture/stop" || fail 'stop absent lane message'
  [ ! -d "$CODEX_LANES_DIR/absent" ] || fail 'empty stop created state'
  echo 'PASS stop with nothing running exits 0 and preserves completed exit'

  mkdir -p "$CODEX_LANES_DIR/dead" "$CODEX_LANES_DIR/not-a-lane" "$CODEX_LANES_DIR/.not-a-lane" || fail 'status fixtures'
  date +%s > "$CODEX_LANES_DIR/dead/started"
  sh "$test_script" status dead > "$fixture/status" || fail 'starting status'
  grep -q 'dead · starting · elapsed ' "$fixture/status" || fail 'recent launch must say starting'
  echo 'PASS a recent launch without Codex or exit says starting'
  printf '%s\n' "$(($(date +%s) - 30))" > "$CODEX_LANES_DIR/dead/started"
  sh "$test_script" status > "$fixture/status" || fail 'all-lane status'
  grep -Fq 'dead · dead — no Codex is running for this lane; relaunch is safe · elapsed ' "$fixture/status" || fail 'dead state and safe relaunch message'
  [ "$(wc -l < "$fixture/status" | tr -d ' ')" -eq 2 ] || fail 'status must skip folders without started'
  sh "$test_script" status not-a-lane > "$fixture/status" 2>&1
  [ "$?" -eq 2 ] || fail 'named status must require started'
  echo 'PASS status reports dead lanes and skips folders without started'

  export FAKE_CODEX_CHILD=1
  start_lane tree
  unset FAKE_CODEX_CHILD
  child_pid=$(sed -n 's/^fake child pid //p' "$state/log")
  [ -n "$child_pid" ] && kill -0 "$child_pid" 2>/dev/null || fail 'fake Codex child did not start'
  sh "$test_script" stop tree > "$fixture/stop" || fail 'stop Codex with child'
  wait "$lane_pid" 2>/dev/null
  [ "$?" -eq 143 ] || fail 'stopped launcher must return Codex signal exit'
  lane_pid=''
  attempts=0
  while kill -0 "$child_pid" 2>/dev/null && [ "$attempts" -lt 100 ]; do
    attempts=$((attempts + 1))
    sleep 0.05
  done
  if kill -0 "$child_pid" 2>/dev/null; then fail 'stop left the Codex child sleep running'; fi
  child_pid=''
  echo 'PASS stop ends the Codex child sleep'
  [ "$(cat "$state/exit")" = stopped ] || fail 'launcher overwrote stopped exit'
  echo 'PASS stopped exit survives the launcher'

  (
    set +m
    export FAKE_CODEX_RELEASE="$fixture/release-own"
    export FAKE_CODEX_READY="$fixture/ready-own"
    sh "$test_script" launch own "$fixture/test brief.md" "$fixture" > "$fixture/launch-own" 2>&1 &
    lane_pid=$!
    wait_for_codex
    sh "$test_script" stop own > "$fixture/stop-own" 2>&1
    [ "$?" -eq 1 ] || fail 'stop must refuse its own process group'
    grep -q "refusing to signal the caller's process group" "$fixture/stop-own" || fail 'own-group refusal message'
    kill -0 "$lane_pid" 2>/dev/null || fail 'own-group stop killed launcher'
    touch "$FAKE_CODEX_RELEASE"
    wait "$lane_pid"
    [ "$?" -eq 3 ] || fail 'own-group refusal changed Codex result'
  ) &
  own_test_pid=$!
  wait "$own_test_pid" || fail 'caller process group must be protected'
  echo 'PASS stop refuses to signal its own process group'

  start_lane a
  a_pid=$lane_pid
  mkdir -p "$CODEX_LANES_DIR/ab"
  printf '%s\n' "$(($(date +%s) - 30))" > "$CODEX_LANES_DIR/ab/started"
  sh "$test_script" status ab > "$fixture/status" || fail 'prefix peer status'
  grep -q 'ab · dead — ' "$fixture/status" || fail 'running a must not make ab live'
  start_lane ab
  sh "$test_script" stop a > "$fixture/stop" || fail 'stop a with ab running'
  wait "$a_pid"
  [ "$?" -eq 143 ] || fail 'stop must end foreground Codex with TERM'
  [ "$(cat "$CODEX_LANES_DIR/a/exit")" = stopped ] || fail 'stopped lane must keep stopped exit'
  sh "$test_script" status a > "$fixture/status" || fail 'completed prefix peer status'
  grep -q 'a · done exit stopped · ' "$fixture/status" || fail 'running ab must not make a live'
  sh "$test_script" status ab > "$fixture/status" || fail 'ab status after stopping a'
  grep -q 'ab · running · ' "$fixture/status" || fail 'stopping a must leave ab running'
  sh "$test_script" stop ab > "$fixture/stop" || fail 'stop ab'
  wait "$lane_pid"
  [ "$?" -eq 143 ] || fail 'stop ab must return Codex signal exit'
  lane_pid=''
  echo 'PASS prefix lanes a and ab launch, report and stop independently'

  touch "$FAKE_CODEX_RELEASE"
  (
    cd "$fixture" || exit 1
    export CODEX_LANES_DIR='relative lanes'
    sh "$test_script" launch relative "$fixture/test brief.md" "$fixture" > "$fixture/relative-launch" 2>&1
    [ "$?" -eq 3 ] || exit 1
    sh "$test_script" status relative > "$fixture/status" || exit 1
    grep -q 'relative · done exit 3 · ' "$fixture/status"
  ) || fail 'relative state root must pass an absolute output path to Codex'
  echo 'PASS relative state root resolves to an absolute output path'
  cleanup
)

case ${1-} in
  launch) [ "$#" -eq 4 ] || usage; launch "$2" "$3" "$4" ;;
  stop) [ "$#" -eq 2 ] || usage; stop "$2" ;;
  status) [ "$#" -le 2 ] || usage; shift; status "$@" ;;
  --self-test) [ "$#" -eq 1 ] || usage; self_test ;;
  *) usage ;;
esac
