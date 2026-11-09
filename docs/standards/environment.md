# Environment — footguns and recipes

> **Status:** standard-canon. One file while it is small; split into topics under `docs/standards/environment/` once
> it passes ~400 lines (`/handoff` step 3 trim rule). Each bullet's bold name is cited by runners — rename only with
> its citers (`git grep` the name first).

## Python and the app

- **Import writes to the home folder**: importing `wallpaper_changer` creates `~/Pictures/WallSwap`, writes
  `settings.json` and opens `wallswap.log` (HZ-3). Any throwaway script sets `HOME` to a temp dir *before* the import,
  and stubs the Windows-only modules the way `tests/conftest.py` does — or just reuses that conftest by putting the
  script under `tests/` in the scratch worktree.
- **The app runs only on Windows; the Mac runs logic only**: `ctypes.windll`, WinRT and `os.startfile` do not exist on
  macOS. Mac tests stub them (D2); whether they really work is proven only by the Windows check
  (`.claude/skills/verify-wallswap/SKILL.md`).
- **`winrt-*` will not build on macOS**: `uv sync` fails with "Unsupported compiler: unix" unless those dependencies
  carry `; sys_platform == 'win32'` (D4).
- **Use `uv run`** for every Python command (`uv run pytest -q`, `uv run ruff check .`) so the project's `.venv` and
  locked versions are used, not the system Python.

## Claude Code session tooling

- **`rtk` hook mangles test / diff / grep output**: redirect to a file and Read it, or use `rtk proxy <cmd>`; trust
  exit codes over summaries.
- **Claude Code refuses `rm` on a path built from a shell variable**: write literal absolute paths, or guard with
  `"${S:?}"`.
- **GitNexus calls need `repo: "WallSwap"`**: several repos are indexed on this machine; the PreToolUse hook denies a
  call without it. Re-index with `gitnexus analyze --skip-agents-md`.

## Codex lanes

- **Codex builder**: every Codex slice runs through `.claude/scripts/codex-lane.sh launch <slice> <brief.md>
  <lane-worktree>` in the background (it wraps `codex exec … -o <final.md> - < <brief.md>`); never via the Codex
  plugin or a Claude agent. Sandbox is `danger-full-access` (D6): under `workspace-write`, `uv sync` fails with
  "Failed to initialize cache at ~/.cache/uv … Operation not permitted", so a lane cannot run the gate. Every brief forbids commits, pushes, branch switches and edits outside the lane, and
  says "no canon doc edits, no baton; append a checkpoint, never rewrite other Record sections". A Codex builder can
  mistake itself for the orchestrator after reading `AGENTS.md`: the brief's first line says it is the builder of one
  slice and stops at the HARD STOP.
- **A backgrounded `codex exec` with the prompt as an argument hangs on "Reading additional input from stdin"**: pass
  the brief on stdin (`-` plus `<`), as `codex-lane.sh` does. Never end with `codex exec … &`; run it in the
  foreground of a background task.
- **Codex "model at capacity"**: no `-o` final file, partial edits on disk. Once `codex-lane.sh status <slice>` no
  longer says running, start a fresh `codex-lane.sh launch` with the brief plus "a previous builder stopped; its
  partial edits are in your worktree, treat them as a draft". Retry once before the Claude `implementer` fallback.
- **Stacking a lane on another lane's uncommitted, approved work**: cut the new worktree from the branch tip,
  `git apply --index <first-lane.patch>` (staged, never a commit), and tell the builder to leave the staged lines
  alone and make its own edits unstaged. Its patch is then plain `git diff`. Review it with `diffRef` = the branch tip
  and say in `context` which staged lines belong to the other slice.
- **Slices built on one uncommitted tree, reviewed and committed one at a time**: snapshot the tree at each "slice
  done" without touching HEAD, the index or files — `GIT_INDEX_FILE=<scratch>/x.idx git read-tree HEAD && git add -A
  && git write-tree`, then `git commit-tree <tree> -p HEAD` (a commit object on no branch). Review the next slice with
  `diffRef: <snapshot>`; a fold's snapshot is a child of the pre-fold snapshot, so `/adversarial-review` with
  `foldRescan: true, diffRef: <pre-fold>, diffHead: <fold>` sees only the fold. `git diff <snapshot>` shows untracked
  files as deleted — scope it to paths. Committing each slice before the next starts avoids all of this.
- **`codex-lane.sh status` needs `pgrep`, which Git Bash on Windows doesn't have**: launch still works; check a
  lane by the exit code and final report files in its `.scratch/codex-lanes/<slice>` folder instead.
- **One file, many slices**: almost every code slice edits `wallpaper_changer.py`. Two lanes may still share a wave
  when they edit different functions; land them with `git apply --3way` and re-run the gate on the landed tree.

## Git

- **`core.hooksPath` is one absolute path, so a hook edit is live in every worktree at once, uncommitted**: enable
  with `git config core.hooksPath .githooks`. Hooks check a script exists before calling it; try hook edits in a
  linked worktree too. `--no-verify` is allen's alone.
