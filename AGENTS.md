<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **WallSwap**. Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/WallSwap/context` | Codebase overview, check index freshness |
| `gitnexus://repo/WallSwap/clusters` | All functional areas |
| `gitnexus://repo/WallSwap/processes` | All execution flows |
| `gitnexus://repo/WallSwap/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
# WallSwap — agent instructions

**This file is the always-on bootstrap for `/catchup`** — the static Tier-0 index. Keep it an index, not a manual:
it says *where* truth lives, never restates it. The session's active user-level rules still apply (model tiering,
adversarial review gate, grilling gate, no unasked commits, no fabricated identifiers, no time units); this only
adds project context. `CLAUDE.md` only imports this file.

**Behavioral rules that bind every edit** (`.claude/rules/`): `wiki-lifecycle.md` (where durable learnings go) ·
`doc-lifecycle.md` (one class per doc folder + per-app trim).

## What this is

> **A Windows tray app that swaps the desktop and lock-screen wallpaper on a timer.** Sources: Wallhaven searches,
> one favourite game's Wallhaven searches, public-domain Met paintings and the user's own folders. One Python file
> (`wallpaper_changer.py`), no API keys, settings in `Pictures\WallSwap\settings.json`. Runs only on Windows; the
> development machine is a Mac, so logic is tested on the Mac with Windows calls stubbed, and the real app is checked
> on a Windows PC with `.claude/skills/verify-wallswap/SKILL.md`.

**Component roles** (baton `<app>` tags — roles, not directories; all live in `wallpaper_changer.py` today):

| Role | Owns |
|---|---|
| `sources` | the fetchers (Wallhaven, game, Met, local folders), safe downloads, image checks, seen history |
| `app` | tray menu, timer loop, source weights and fallback, settings, favourites |
| `windows` | Windows calls: set wallpaper, lock screen, fullscreen check, single-instance mutex |
| `tooling` | `.claude/`, `.githooks/`, tests, `pyproject.toml` |
| `docs` | planning-only sessions (no code touched) |

**Big picture on one page:** `docs/ARCHITECTURE.md` — the file's sections, the threads, what lands on disk, one
wallpaper change end to end.

## Where the truth lives

Read top-down, pull only the slice the task needs. `docs/INVARIANTS.md` wins on conflict; code establishes as-built
facts. Flag code/contract mismatches without treating observed behaviour as new ratification.

1. **`docs/INVARIANTS.md`** — the rules every change keeps (safe downloads, user files untouched, SFW only, …) and
   the hazards (trigger → hidden failure → prevention). Declared conflict winner.
2. **`docs/ARCHITECTURE.md`** — as-built map of the code, threads and files on disk.
3. **`docs/standards/`** — `feature-delivery.md` (runner `/feature`); `code-conventions.md`; `environment.md`
   (tooling footguns and recipes).
4. **`docs/decisions.md`** — the D-number ledger, tagged [PM]/[YOU].
5. **`docs/features/<date>-<name>.md`** — per-feature decision logs (Records; `/feature` writes + reconciles).
6. **`docs/handoff/<date>-<app>-<kebab>.md`** — session batons. Inventory recipe: `docs/handoff/README.md`.

## How we work

- **Session ritual:** start with `/catchup <task>`; end with `/handoff` (promote, baton, compaction, gates).
- **Ship a feature with `/feature`** — orient (+ settled-decisions ledger + grill) → impact-mapped & critiqued plan →
  approve → ratify forks → Codex builds sized slices → gate + adversarial review → reconcile → handoff. Three human
  checkpoints. Session model orchestrates, never writes slices. **Fix a bug with `/fix`.**
- **Commit messages:** subject starts with `feat:`, `fix:`, `docs:`, `test:` or `chore:`, then plain words saying
  what changed for the person using the app; internal codes go only in one final `Refs:` line. No attribution lines.
  Enforced by `.githooks/commit-msg`. Pushed history is never reworded.
- **Git hooks:** enable once per clone with `git config core.hooksPath .githooks`.
- **Gate:** `.claude/scripts/gate.sh <code|docs>... --log <file>` — the table in `docs/standards/feature-delivery.md`
  § Phase 6.
- **GitNexus MCP calls pass `repo: "WallSwap"`** (several repos are indexed; `.claude/hooks/gitnexus-repo.sh` denies
  a call without it). Re-index with `gitnexus analyze --skip-agents-md` so the block above is not rewritten.
- **First footgun every session:** importing `wallpaper_changer` writes to `~/Pictures/WallSwap` (folder, settings,
  log). Tests redirect `HOME` first (`tests/conftest.py`); never import it from a throwaway script without that.
  More in `docs/standards/environment.md`.
