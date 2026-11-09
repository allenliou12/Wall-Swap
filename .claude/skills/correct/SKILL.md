---
name: correct
description: Turn a mistake agents keep repeating in this repo into something that fails on its own. Use when allen corrects the same thing twice, when a rule marked "none" in the rule table is broken again, or when /handoff or the user says /correct.
---

# Correct

An agent sees only the files it opened and copies the nearest example, so a rule it has to remember will be missed.
Change the repo so the next agent cannot repeat the mistake. [rule-table.md](rule-table.md) pairs each rule with what
enforces it.

## Steps

1. **Find the classes.** Start from the correction in hand. With none named, read `fix:` and revert commits, the
   feedback memory files, `~/.claude/CLAUDE-history.md`, `docs/standards/environment.md` and the rule table's `none` rows.
   Group mistakes into classes. A class counts once it has happened twice, with both cases cited. Done when every
   class has its two citations or is dropped.
2. **Pick the highest level that works,** for each class:
   1. **Architecture:** one owner, one supported way, generated instead of hand-synced, old way deleted.
   2. **Types:** the bad state cannot be written.
   3. **A check whose error names the fix:** git hook, gate script or Claude Code hook. A git hook reaches Codex; a
      Claude Code hook does not. If the pattern is already common, fail only when a change adds more.
   4. **A test** of the behaviour.
   5. **A written rule,** only for a judgment call, because nothing fails when it is skipped.
   A yes/no fact belongs at level 3 or above; Jev (`~/.claude/hooks/model-tiering.py`) can judge a fuzzy case inside a
   check, as `.claude/scripts/check-record.mjs` does.
3. **Fix the most frequent classes, one at a time,** through the normal builder and review lanes. A new check that
   could block work fails open when its own tooling is missing, and is tried in a linked worktree
   (`docs/standards/environment.md`, the `core.hooksPath` bullet).
4. **Prove it bites.** Replay a real past mistake and watch the check fail, then fix it and watch it pass.
5. **Update the rule table.** Add or change the row; keep each row to one line. A rule that now cannot fail leaves
   `AGENTS.md` or the runner, or shrinks to one line naming its enforcer. Delete a row whose mistake can no longer
   happen.

**Reply** in plain words: each class, its two cases, the level chosen, why a higher level would not work, and the
failing-then-passing output.
