# Code conventions — WallSwap

> **Status:** standard-canon. Rewrite in place when a convention lands (`.claude/rules/doc-lifecycle.md`). Cited by
> `/feature` (module-design lens, briefs) and by review.

## Module design

The `codebase-design` principles, checked by `/feature`'s module-design lens at plan critique and review.

- **Decisions are pure functions.** A rule (is this image usable, which source next, which file to delete, what a
  setting falls back to) is a plain function of its inputs, like `fits_screen` and `_merge_settings`. Code that talks
  to Windows, the network or the disk calls it and acts on the answer.
- **Deep functions.** A small interface with real behaviour behind it (`safe_get`): callers learn little, the function
  hides much.
- **The interface is the test surface.** Tests call what callers call. A test that must reach into a function's
  locals means the function is the wrong shape.
- **Deletion test.** A helper whose deletion would just move its few lines into its one caller is a pass-through;
  don't add it.
- **A seam only where something varies.** One implementation = no new class or protocol. A new source is a new fetcher
  function returning `Wallpaper | None`, wired into `fetch_source` — mirror the existing ones.
- **Pass dependencies in, don't create them inside** where a test needs to swap them (folders, settings, a fetch
  function — as `download_wallpaper(fetch, …)` and `pick_local_wallpaper(folders)` already do).
- **Every network call goes through `safe_get`** (INV-1, INV-2). Every new host is added to `ALLOWED_HOSTS`.
- **Imports at the top of the file.** Never `import pkg.sub` inside a function when `pkg` is used there (HZ-1).

## Python

- Python ≥ 3.13 (`pyproject.toml`), type hints on new functions, `Path` over string paths.
- Constants in the Configuration section, upper-case, with a one-line comment saying why the number is what it is.
- Log with `log.info` / `log.warning`; user-facing messages go through `WallSwapApp.notify`.
- A blanket `except Exception` needs a comment saying what failure it absorbs and what the user sees (HZ-2).
- Lint: `uv run ruff check .` — bug-finding rules only (D1).

## Tests

- **Where:** `tests/`, run with `uv run pytest -q`. `tests/conftest.py` points `HOME` at a temp dir and stubs the
  Windows-only modules before importing `wallpaper_changer` (HZ-3) — every test goes through it.
- **What earns a test:** a rule from `docs/INVARIANTS.md`, a pure decision function, or a bug fix (the regression test,
  RED first). Test the rule's yes case and its no case: a guard that always says "no" must fail a test (HZ-2).
- **No network.** Stub `requests.get` (or pass a fake fetch function); never call Wallhaven or the Met from a test.
- **No wording pins.** Don't assert menu labels or notification text unless the text itself is the rule.
- **Windows calls** (`ctypes.windll`, WinRT, `os.startfile`) are stubbed on the Mac; whether they really work is the
  Windows check's job (`.claude/skills/verify-wallswap/SKILL.md`), never claimed from a Mac test.
