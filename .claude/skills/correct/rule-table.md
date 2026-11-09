# Rule table

Each rule and what enforces it. `none` means nothing fails when the rule is skipped. A `none` rule broken twice goes
through `/correct`; judgment rules stay `none` on purpose and review catches them.

| Rule | Enforced by | Reaches Codex? | Repeats on record |
|---|---|---|---|
| Doc links resolve | `.claude/scripts/check-doc-links.mjs`, pre-commit | Yes | |
| Record shape, Run order, no history under plan headings | `.claude/scripts/check-record.mjs`, pre-commit | Yes | |
| Commit subject prefix, no attribution lines | `.githooks/commit-msg` | Yes | |
| Codex's runner copies match `.claude/commands/` | `.claude/scripts/sync-runner-copies.mjs`, pre-commit | Yes | |
| No pyflakes-class bugs (undefined / shadowed names, HZ-1) | `ruff check` (D1), `gate.sh code`, pre-commit | Yes | |
| Logic rules keep their tests green | `uv run pytest`, `gate.sh code`, pre-commit | Yes | |
| Tests never touch the real home folder | `tests/conftest.py` sets `HOME` before import | Yes | |
| Agents get a deliberate model tier | `~/.claude/hooks/model-tiering.py` | No | |
| GitNexus calls name the repo | `.claude/hooks/gitnexus-repo.sh` | No | |
| No commit unless allen asked | none | No | |
| No push unless allen asked | `~/.claude/hooks/git-guard.py` asks | No | |
| No skipped git hooks, no blanket checkout | `~/.claude/hooks/git-guard.py` refuses | No | |
| Every network call goes through `safe_get` (INV-1) | none, review | No | |
| Windows behaviour is checked on Windows, not claimed from a Mac test | none, judgment | No | |
| One full gate run per state of the code | none | No | |
| Orchestrator proof before a commit | none | No | |
| Impact analysis before editing a symbol | none | No | |
| Review before commit | none | No | |
| No time estimates | none, Jev could judge one | No | |
| Verify claims, no made-up identifiers, plain writing | none, judgment | No | |
