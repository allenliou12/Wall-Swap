---
description: Fix a reported bug the WallSwap way — reproduce → root cause → failing test → fix → same repro passes → gate → prevention lesson, stopping at the commit checkpoint.
---

Fix the bug described in the argument. Bug = code doing the wrong thing; a wording, layout or style fix goes straight
to the light lane with no test. A change of behaviour someone wants, rather than a defect, is `/feature`. Honor
`AGENTS.md` and the session's active user-level rules throughout.

> Argument empty → ask what is broken before starting.

**Task list (every run):** the first action copies the 7 steps below, by name, onto the app's task list before any
other work. A step that does not apply stays on the list with `skip: <plain reason>` in its text, never dropped.

## Steps

1. **Reproduce.** Note `git rev-parse HEAD`: that is this run's comparison base. Reproduce on the Mac where the bug is
   in logic (a throwaway script with `HOME` redirected — `docs/standards/environment.md`, "Import writes to the home
   folder" — or a `ruff` / `pytest` run); where it only shows on Windows, write the steps from
   `.claude/skills/verify-wallswap/SKILL.md` for allen and wait for his result. Save the steps and what you saw in
   `.scratch/fix-<name>.md`, the run's proof file. Cannot reproduce → say so with what you tried and stop; no fix
   ships on a guess.
2. **Find the root cause** with `/diagnose` phases 1-4 only; this runner owns the fix. Grep every caller of the
   function at fault (GitNexus `context`, `repo: "WallSwap"`), and read `docs/INVARIANTS.md`. Each line of the fix
   traces to something a run showed. Two fixes built on one assumption failed → test the assumption first. The code
   breaks an invariant, or the invariant itself looks wrong → stop and ask ("recorded X at `<path>`, the bug implies
   Y"), tagged **[PM]** or **[YOU]**.
3. **Write the failing test first** (`/tdd`): real path, fails for the reason step 2 found. Confirm it is RED.
4. **Fix at the shared function all callers route through.** Run `impact` on each symbol first and warn on HIGH or
   CRITICAL. Builder: run `python3 ~/.claude/hooks/model-tiering.py --owner "<plain summary, no code>"`; the trust
   boundary (`/feature` step 7 list) stays on Claude `security-implementer`, everything else goes to Codex by the
   `/feature` step 7 recipe. A trivial fix (few lines, one file) may be made here.
5. **Prove it.** Remove debug logs and throwaway prototypes. The test is GREEN and the step 1 reproduction now passes
   on the same surface, with before and after output in the proof file. A Windows-only bug stays "Mac-proven,
   Windows unverified" until allen re-runs the steps. "Inconclusive" or a different surface is not a pass.
6. **Gate.** Name the lane, using `python3 ~/.claude/hooks/model-tiering.py --lane "<plain summary of the diff>"`,
   then run the `/feature` step 8 checks that lane requires. There is no Record here, so: comparison base comes from
   step 1, the cleanup builder is the kind step 4 chose, the worked example is the step 1 reproduction, the proof file
   stands in for the Proof table, and `/adversarial-review` runs without `spec`. The reproduction is this run's smoke:
   run it again on the final code, after the cleanup pass and after every fold. A fix with a logic rule also reverts
   that rule → the test goes RED → restore.
7. **Prevent and close.** Route the lesson by `.claude/rules/wiki-lifecycle.md`, usually a `HZ-n` in
   `docs/INVARIANTS.md` or `docs/standards/environment.md`; a hazard the fix closes gets its status updated in place.
   Update any `verify-wallswap` step the fix made untrue. Report what was broken, the root cause, the fix, and the
   failing-then-passing output. **Commit only when the owner asks**, with the failing test in the same commit as its
   fix.
