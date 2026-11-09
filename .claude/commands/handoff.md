---
description: Promote durable learnings, write a lean role-tagged baton, then keep three recent batons per role and archive eligible shipped Records (WallSwap wiki-lifecycle — overrides the global handoff skill).
---

Close out the session: **promote durable knowledge into canon first, then write a lean baton.** A handoff is not a
session log — it is the write side of `.claude/rules/wiki-lifecycle.md`. Durable learnings (footguns, invariants,
hazards, conventions, decisions, architecture changes) get routed into their canonical home; only ephemeral session
state stays in the baton. Honor `AGENTS.md` and the session's active user-level rules (proof over promise, no time
units, no fabrication, no unasked commits).

## Steps

1. **Date · Role · Title.** `date +%F` for the date (never hardcode). `<app>` = component role the session touched
   (`sources` · `app` · `windows` · `tooling` · `docs`). Cross-cutting → the role that owns the decision. Reserve
   **`docs/handoff/<YYYY-MM-DD>-<app>-<kebab>.md`** for this session — never overwrite an earlier session's baton;
   disambiguate its slug. If this session already wrote a protective baton, reuse that exact path. Convention +
   template: `docs/handoff/README.md`.

2. **Gather real state — never fabricate.** `git branch --show-current` · `git rev-parse HEAD` · `git status
   --porcelain` · `git diff --stat` · `git log --oneline -15` · the last real gate result if a gate ran this session,
   else write "not verified". Empty section → `_None._`.
   > `rtk` hook can mangle `git diff` / test output — redirect noisy output to a file and Read it.

3. **Route durable learnings into canon (the load-bearing step).** For each thing this session learned that matters
   to a session that *never reads this baton*, find its row in the routing table (`.claude/rules/wiki-lifecycle.md`)
   and **write it there now**. First pick per learning: from the repo root,
   `python3 ~/.claude/hooks/model-tiering.py --canon "<one plain sentence, no code>"` prints the row's home, or
   `UNSURE` → route by hand; the specific section within that home is still yours. Home doesn't exist yet → create
   it. Invariants and hazards keep stable IDs (`INV-n`, `HZ-n`). Decisions land in `docs/decisions.md` (RATIFIED only
   when decided). Memory writes obey the session's active write-gate. The owner corrected the same mistake twice, or
   a `none` rule in `.claude/skills/correct/rule-table.md` was broken again → run `/correct` on that class, or name it
   in the baton's Next step. Keep a list of what you promoted → becomes `## Promoted`.
   **Prune what you wrote into.** Each `docs/standards/` file this step wrote to that is over 400 lines (`wc -l`) gets
   one trim pass, limited to the sections this step touched: delete a bullet a check now enforces (name the check;
   only when it binds every writer, Codex and plain git too) · shrink a dated story to its rule plus a link (only after
   the linked Record holds the story) · merge bullets that say the same thing. Before deleting or renaming any bullet,
   `git grep` the repo for its bold name; a cited bullet stays, or its citers are repointed in the same edit. Rewrite
   in place, never append. Report each file's lines before → after in step 9.

4. **Write the protective lean baton** at the reserved path, per the template in `docs/handoff/README.md`:
   **Goal · Current State · Files in flight · Promoted · Next step**. Do not re-narrate what step 3 promoted — point
   to where it landed. Next step = **one** concrete action.

5. **Compact.** Run the inventory with `.slice(0, 1)` removed and keep the newest **three batons per role** (all if
   fewer). New/dirty batons count toward the three but are always protected. Also inspect hot Records for verified
   shipment. For each candidate, record **KEEP / ARCHIVE**, destination and promotion evidence:
   - **KEEP** dirty, untracked, current/in-flight or uncertain work, pending prerequisites, unresolved proof (including
     an outstanding Windows check) or an unpromoted decision/rule/hazard. Give the exact reason.
   - **ARCHIVE** only regular tracked sources already committed and clean against HEAD, with promotion verified in
     canon. Never commit a target to make it eligible.
   - Destinations preserve basenames: batons → `docs/handoff/archive/`; shipped Records →
     `docs/features/archive/<source-month>/`.

6. **Move eligible sources.** Before each batch, re-read branch, HEAD and target status. Refuse an occupied
   destination. Search each old path across all tracked text; repair inbound paths in the same batch. Uncertain
   routing or a collision means KEEP and report; never overwrite or delete original content.

7. **Verify navigation.** Run `node .claude/scripts/check-doc-links.mjs` and `node .claude/scripts/check-record.mjs`.
   Save actual output and exit codes. Failed links leave compaction incomplete; repair in-scope pointers and rerun.

8. **Refresh the SAME current-session baton after compaction and gates.** Re-read branch, HEAD and dirty paths;
   update Current State, Files in flight, promotions, archive/KEEP outcomes, gate exits and Next step at step 4's
   exact path. Never refresh an earlier session's baton or create a second one.

9. **Report** the baton path, one-line Next step, each promotion as `promoted X → <file:section>`, archived paths,
   per-role live counts, every KEEP reason and link-gate result. No commit unless the user asks.
   **Batch doc commits, don't drip.** Doc and rule edits go in one `docs:` commit per finished step, normally here,
   when the user asks. Commit sooner only when another lane needs the change (lanes start from the last commit). A
   doc edit that belongs to a code slice rides in that slice's commit.
