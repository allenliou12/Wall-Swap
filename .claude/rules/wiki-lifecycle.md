# Wiki Lifecycle — the write-side routing table

> **What this is:** where each kind of learning a session produces lands. Durable learnings are **promoted into
> canon** (the file a session that never reads this baton will still find); ephemeral state goes into **the baton**.
> This is "Where the truth lives" (`AGENTS.md`) read backwards — written *into* instead of read *from*.
> **Runners:** `/handoff` (write + compaction) · `/catchup` (read).

## The routing table

| Learning the session produced | Canonical home it writes to | Durable? |
|---|---|---|
| A tooling / env / ordering trap (a footgun) | `docs/standards/environment.md`, under its matching heading | promote |
| A rule every change must keep (safety, user files, content, behaviour) | `docs/INVARIANTS.md` § Invariants — next free `INV-n`, with the code that holds it | promote |
| A trigger with a hidden failure or prevention lesson | `docs/INVARIANTS.md` § Hazards — next free `HZ-n`: trigger → hidden failure → prevention → where verified | promote |
| A new section, thread, file on disk, dependency or module | `docs/ARCHITECTURE.md` | promote |
| A naming / module / pattern / test convention | `docs/standards/code-conventions.md` | promote |
| A how-we-deliver rule (phases, gates, lanes) | `docs/standards/feature-delivery.md` (+ the runner it changes) | promote |
| A decision that outlives one feature | `docs/decisions.md` — preserve ID, owner tag and status; the Record holds local decisions/proof | promote |
| A user-visible behaviour change | `README.md` (what the user reads) | promote |
| A cross-session principle not derivable from the repo | project auto-memory (`MEMORY.md` index + detail file); the session's active user-level write-gate applies | promote |
| Session state — dirty tree, running processes, the next step | **the baton** `docs/handoff/<YYYY-MM-DD>-<app>-<kebab>.md` | ephemeral |

> If a promotion home doesn't exist yet, **create it on first promotion**; never divert a durable learning into
> the baton. `docs/INVARIANTS.md` wins on conflict.

## The rules this enforces

- **Promote, don't hoard.** Durable knowledge belongs where the *next* session looks.
- **A baton is a baton.** It moves the next session forward, then is trimmed. A failed attempt worth remembering is a
  footgun → `environment.md`; a rule worth remembering is an invariant or hazard → `INVARIANTS.md`. Worth neither →
  noise.
- **Retention, review and invariant rules:** `.claude/rules/doc-lifecycle.md`.

## How `/handoff` uses this

`.claude/commands/handoff.md` runs this table: gather real state (never fabricate), route each durable learning to its
row and report it, write the protective lean baton, compact, then refresh that same baton.
