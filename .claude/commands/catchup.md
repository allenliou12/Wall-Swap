---
description: Rebuild session context gradually — load only the slice the task needs, in tiers (read side of the WallSwap session ritual).
---

Orient for the work named in the argument by loading context **gradually, not all at once** — the read side of
`.claude/rules/wiki-lifecycle.md`. Canon + project auto-memory + the latest **role-tagged** baton rebuild working
context; deeper docs are pulled only when the task reaches for them. The truth order in `AGENTS.md` **is** the load
order.

> Name the component role (`AGENTS.md` table) the task touches to scope the context. Argument empty → print the live
> state first, then ask what the session is about before loading deeper context.

## Steps

1. **Live state — read-only, before loading task context.** Run the inventory recipe in `docs/handoff/README.md`:
   current branch, HEAD, dirty/untracked paths, the latest baton for each role, and every hot Record with its
   `Progress:` line. Status excerpts are **unverified**, including "shipped"; verify them against live source and
   later proof before calling a Record active or complete. Do not mutate files.

2. **Tier 0 — always load:**
   - `AGENTS.md` — the shared instruction source; `CLAUDE.md` only imports it.
   - Project auto-memory `MEMORY.md` — use the path supplied by the session, never guess a tool-specific path;
     follow its links only when the task reaches for them.
   - The **latest baton for the role in play**, selected by step 1's ordering. Role unknown → newest overall. Read
     Goal · Current State · Promoted · Next step.

   Then state, in one short message: what this session will do, which roles it touches, and which tiers you are
   about to pull.

3. **Tier 1 — load on task match:**
   - `docs/INVARIANTS.md` — always before any code change; it wins on conflict.
   - `docs/ARCHITECTURE.md` when the task spans sections or the session is new to the code.
   - `docs/decisions.md` before treating decisions as settled.
   - The `docs/standards/` doc the task invokes — `feature-delivery.md` before planning a build via `/feature`;
     `code-conventions.md` before writing or reviewing code; `environment.md` for tooling.
   - The Record in play — `docs/features/<date>-<name>.md`.

4. **Tier 2 — only if needed:** archived batons (`docs/handoff/archive/`), archived Records, or `git log` for "why did
   we do it this way" that current canon doesn't answer.

5. **Honor scope discipline.** A memory line or baton reflects what was true **when written** — verify any file /
   flag / line number it names still exists. Canon beats baton; `docs/INVARIANTS.md` beats both.

6. **Close** by naming the exact next action (usually the baton's **Next step**) or the open decision to resolve first.

> Pair with `/handoff` (write + compaction). Builds go through `/feature`; bugs through `/fix`.
