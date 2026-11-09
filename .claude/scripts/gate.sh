#!/usr/bin/env bash
# Phase 6 gate commands (docs/standards/feature-delivery.md) in one run.
# Usage: .claude/scripts/gate.sh <code|docs>... [--log <file>]
#   code   compile, ruff (bug-finding rules, D1), pytest
#   docs   doc links, Record shape, tooling self-tests
# Full output goes to the log; stdout gets one `EXIT <part> <step>=<code>` line per step. Exit 1 if any step failed.
set -u
root=$(git rev-parse --show-toplevel) || exit 1
log="" parts=()
while [ $# -gt 0 ]; do
  case $1 in
    --log) log=$2; shift 2 ;;
    code|docs) parts+=("$1"); shift ;;
    *) echo "gate: unknown argument '$1'" >&2; exit 2 ;;
  esac
done
[ ${#parts[@]} -gt 0 ] || { sed -n '3,6p' "$0"; exit 2; }
[ -n "$log" ] || log=$(mktemp -t gate)
: > "$log"
echo "python $(cd "$root" && uv run python -V 2>&1) node $(node -v 2>&1) log $log"
fail=0
step() { # step <part> <name> <command...>
  local part=$1 name=$2; shift 2
  echo "=== $part $name: $*" >> "$log"
  (cd "$root" && "$@") >> "$log" 2>&1
  local code=$?
  echo "EXIT $part $name=$code" | tee -a "$log"
  [ $code -eq 0 ] || fail=1
}
for p in "${parts[@]}"; do
  case $p in
    code)
      step code compile uv run python -m py_compile wallpaper_changer.py
      step code ruff uv run ruff check .
      step code pytest uv run pytest -q ;;
    docs)
      step docs links node .claude/scripts/check-doc-links.mjs
      step docs record node .claude/scripts/check-record.mjs
      step docs record-selftest node .claude/scripts/check-record.mjs --self-test
      step docs links-selftest node .claude/scripts/check-doc-links.mjs --self-test
      step docs sync-selftest node .claude/scripts/sync-runner-copies.mjs --self-test
      step docs lane-selftest sh .claude/scripts/codex-lane.sh --self-test ;;
  esac
done
exit $fail
