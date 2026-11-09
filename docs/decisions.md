# WallSwap — Decisions ledger

> **Status:** planning canon. One ledger for decisions that outlive a single feature. Each row: ID, owner tag
> ([PM] = what the app does for the person using it; [YOU] = engineering call), status, one-line decision, source.
> Edit status in place; never renumber. Feature-local decisions stay in their Record.

| ID | Owner | Status | Decision | Source |
|---|---|---|---|---|
| D1 | [YOU] | RATIFIED 2026-11-09 | Gate lint = ruff bug-finding rules only (`E7`, `E9`, `F`); style is a review call | `pyproject.toml` `[tool.ruff.lint]` |
| D2 | [YOU] | RATIFIED 2026-11-09 | Logic is tested on the Mac with Windows calls stubbed; the real app is proven on a Windows PC by checklist | `tests/`, `.claude/skills/verify-wallswap/SKILL.md` |
| D3 | [YOU] | RATIFIED 2026-11-09 | The workflow (`.claude/`, `docs/`, `.githooks/`) is tracked in this public repo, kept free of other projects' details | `.gitignore` |
| D4 | [YOU] | RATIFIED 2026-11-09 | `winrt-*` dependencies install on Windows only, so the project installs on the Mac | `pyproject.toml` |
| D6 | [YOU] | RATIFIED 2026-11-09 | Codex lanes run with `danger-full-access`: the restricted sandbox cannot use the uv cache, so it cannot run the gate; briefs still forbid commits, pushes, branch switches and edits outside the lane | `.claude/scripts/codex-lane.sh` |
| D5 | [YOU] | RATIFIED 2026-11-09 | GitNexus indexes this repo as `WallSwap`; the AGENTS.md block is written once, re-index with `--skip-agents-md` | `.gitnexusrc`, `AGENTS.md` |
| D7 | [PM] | RATIFIED 2026-11-09 | A source that is off, empty or at 0% is never used, not even as a fallback; the window's % is the real share | `docs/features/2026-11-09-settings-window.md` F2 |
| D8 | [YOU] | RATIFIED 2026-11-09 | The settings window lives in `settings_window.py` and never imports `wallpaper_changer`; it gets its data and actions passed in | `docs/features/2026-11-09-settings-window.md` R3 |
