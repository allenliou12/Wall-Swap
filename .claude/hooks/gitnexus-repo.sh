#!/bin/sh
# PreToolUse on mcp__gitnexus__*: several repos are indexed on this machine, so a call without `repo` fails with
# "Multiple repositories indexed". Deny it up front with the fix. Tools that take no repo pass through.
input=$(cat)
case $(printf '%s' "$input" | jq -r '.tool_name') in
  *__list_repos|*__group_list|*__group_sync) exit 0 ;;
esac
[ -n "$(printf '%s' "$input" | jq -r '.tool_input.repo // empty')" ] && exit 0
jq -n '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny",
  permissionDecisionReason: "GitNexus calls in this project need repo: \"WallSwap\" (several repos are indexed). Retry with it."}}'
