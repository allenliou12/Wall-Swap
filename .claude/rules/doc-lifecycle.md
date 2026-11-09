# Doc Lifecycle Rules

> Every doc folder has one class below, each with its own retention rule. Every session adds knowledge; this bounds
> *where* it lands and *what* gets trimmed so logs never bury canon. "Trim" is **per role** (the `AGENTS.md` component
> roles), never one global "last N".

## The classes

| Class | Where | Lifecycle | Retention |
|---|---|---|---|
| **Canon** (living truth) | see split below | edited to match reality | forever, never duplicated |
| **Record** (decision logs) | `docs/features/<date>-<name>.md` | written once per feature, reconciled to "shipped" | kept while live; eligible shipped Records → `docs/features/archive/<source-month>/` |
| **Log** (session batons) | `docs/handoff/<YYYY-MM-DD>-<app>-<kebab>.md` | written once per session; superseded by the next | **newest three per role** stay hot; eligible older batons → `docs/handoff/archive/` |
| **Planning** (decisions) | `docs/decisions.md` | status rewritten in place, never appended | forever, never archived |

## Canon splits into two — they do NOT share a retention rule

### Reference-canon — `docs/ARCHITECTURE.md`, `README.md`
- **As-built description** (HOW-IS), reconciled to live source; never authored ahead of code.
- Never hand-author a numerical claim (line ranges, counts) without the grep that establishes it.

### Standard-canon — `docs/INVARIANTS.md` + `docs/standards/` + `.claude/rules/`
- **Normative contract** (MUST/NEVER): what every change keeps, how agents work here.
- **Rewrite, never append.** A canon section is the reconciled *state*, not a changelog: a correction replaces the old
  reading in place (one "corrected <date>" tag at most); history lives in Records.
- **Conflict-spine anchor:** `docs/INVARIANTS.md` WINS on conflict. IDs (`INV-n`, `HZ-n`) are stable: never
  renumber; retire with a note.
- Hazards: trigger → hidden consequence → prevention → verified source.
- **Explicit source review, not date maintenance.** A "Verified against … on <date>" header changes only after a
  live-source review recorded in the same feature Record; never auto-stamped by a gate or handoff.

## Record — dated decision logs
- One file per feature: `docs/features/<date>-<name>.md`. Captures the design decision + build-time deviations;
  reconciled to "shipped" in place. Shape checked by `.claude/scripts/check-record.mjs`.
- **On handoff, archive eligible shipped Records** → `docs/features/archive/<source-month>/`, original basename.
  Verify completion against shipped source and later proof, not an old status line. A prerequisite, uncertain
  completion or unpromoted decision means KEEP with a reason.

## Log — session batons (single role-tagged stream)
- One baton per session: `docs/handoff/<YYYY-MM-DD>-<app>-<kebab>.md`. `<app>` = component role (`sources` · `app` ·
  `windows` · `tooling` · `docs`), not a directory name.
- **Trim per role, not global.** Keep the newest three batons for every role (all if fewer). Dirty/new files count
  toward the three but are never moved. Ordering + inventory: `docs/handoff/README.md`.

## Git is the cold spine — archive eligibility
- "Git holds all" only holds for **committed source text**. A source must be a regular tracked file, clean against
  HEAD in both index and working tree. Dirty/untracked/current or uncertain work means KEEP with a reason; never
  commit it to make it eligible.
- **Verify promotion held.** Every durable decision, rule and hazard has its canonical home before a move. Move,
  never delete; preserve content and basenames.

## The one routing rule
- Matters to a session that *never reads this baton* → **durable** → promote to canon (`.claude/rules/wiki-lifecycle.md`).
- Matters only to the *immediately next* session → **ephemeral** → the baton.
- When in doubt, promote: a baton is read once, canon is read forever.
