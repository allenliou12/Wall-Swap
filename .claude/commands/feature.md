---
description: Deliver a feature end-to-end the WallSwap way — orient (+ settled-decisions ledger + grill) → impact-mapped & critiqued plan → approve → ratify forks → Codex builds sized slices → gate + adversarial review + Windows check → reconcile → handoff, stopping at the three human checkpoints.
---

Deliver the feature described in the argument by running the **Feature Delivery Standard**
(`docs/standards/feature-delivery.md` — the *why*; this is the *do*). Run all phases in order and **STOP at the
three checkpoints** (approve plan · ratify forks · approve commit). Honor `AGENTS.md` and the session's active
user-level rules throughout. Why the lifecycle is shaped this way: §0 of the standard.

> Argument empty → ask what feature to deliver before starting.

**Writing to the owner (every message):** first line is a status line — "Step N of 10 — <what>". Short bullets, one
idea each; bold the decision, not the explanation; prose, never a code block; ≤ 10 lines unless the owner asks for
detail. Evidence (file paths, line numbers, function names) lives in the feature Record; in chat it comes only after
the plain explanation, never instead of it.

**Decision message (steps 2 and 5)** — one message per round, plain markdown:

**Step N of 10 — decisions.** <one line: N settled from the codebase, M need you>

**Settled from the codebase** (reply "override N" to change one):
1. **<decision, ≤ 6 words>** → <answer, ≤ 12 words> · _<source: D3 / INV-5 / Record>_

**Needs you:**

**Q1 · <question, ≤ 8 words>** [PM] or [YOU]
- **A** — <option, one line: what the person using the app sees or does>
- **B** — <option, one line, same>
- **Or your own idea**
➡️ **Recommend A:** <why, one line>

A [PM] option names what changes for the person using the app, never how it is stored or built; the mechanism goes in
the Record. A [YOU] option may name the mechanism, in plain words, with what it costs (files, builder, risk).

Show at most 5 settled items ("+N more, listed in the Record") and at most 3 questions. Ask only the **frontier** — a
question whose prerequisite is still open waits for the next round. Nothing open → say so in one line and move on.
`AskUserQuestion` chips, if used, come after this message, never instead of it.

**Task list (every run):** the first action copies all 10 steps below, by name, onto the app's task list before any
other work. A step that does not apply stays on the list with `skip: <plain reason>` in its text, never dropped.

## Steps

1. **Orient (Phase 0).** Note the comparison base (`git rev-parse HEAD`, or the branch point when already on a
   feature branch). Read canonical context in the truth order (`AGENTS.md` → "Where the truth lives"):
   `docs/INVARIANTS.md` (conflict winner: invariants + hazards) → `docs/ARCHITECTURE.md` (which sections, threads and
   files on disk the change crosses) → relevant `docs/standards/` → `docs/decisions.md` → prior `docs/features/`
   Records + the latest `docs/handoff/` batons → the live code the change lands in (GitNexus `query` / `context`,
   `repo: "WallSwap"`). State, in one short message: **which component roles** (`sources` · `app` · `windows`) this
   lands in, what it **unlocks**, and its scope (§2 of the standard). Live code establishes as-built facts; it cannot
   override an invariant. Where an invariant's cited code no longer matches, check that row against live code: a
   mismatch is either a code bug (goes into the plan's **Hazards that apply**) or a rule that may have changed (goes to
   allen as a [PM]/[YOU] question). Read and report only; edit nothing at orient.
   Then write the **settled-decisions ledger**: every decision docs/code already made that bears on this change, one
   line + source (D-rows, `INV-n` / `HZ-n`, Records, shipped code). Facts, not questions. Also list every design or
   mock-up allen approved for this feature (its path), or "none".

2. **Grill (Phase 0.5).** Scope fuzzy or assumptions unexamined → run `/grilling`, scoped to **intent gaps +
   decisions the ledger does NOT cover**. Recorded decisions are never re-asked; re-open one only when the task
   contradicts it, as a single "recorded X at `<path>`, task implies Y — override?" question. Skip when the ask is
   already concrete. Each round is one **decision message** (format above). Fold answers into the Phase 0 statement.

3. **Plan via impact + map + critique (Phase 1).** Use the **`Workflow`** tool (this `/feature` invocation IS the
   opt-in — author the script inline; size every stage by job tier from the Model Tiering ladder, never a version ID:
   Map/recon readers on the mechanical tier, Design / Critique / Synthesize on the reasoning tier). Start with blast
   radius, not a single design:
   - **Impact** — GitNexus `impact` (`repo: "WallSwap"`, upstream) on every function the change touches: callers,
     execution flows (timer → change → source → download → set), threads that share the state, files on disk and
     `settings.json` keys. Name every touched role.
   - **Map** — read-only `Explore` agents over the real code the change builds on (the exemplar function to mirror,
     the settings defaults, the menu builder). Return `file:line` facts.
   - **Design** — normal work: ONE plan. Full panel: N independent lenses (e.g. scope-minimalist · seam-clean ·
     forward-compat), each a complete plan. Every design gets the impact map + code map + settled-decisions ledger.
   - **Critique** — adversarially attack each for: code smell · convention violations (`code-conventions.md`) ·
     scope violations (§2) · threading (the timer, change and tray threads; `change_lock`; the settings `RLock`) ·
     and — load-bearing — an **impact-critic lens**: challenge omitted callers, menu items and settings keys against
     the live map; an **invariant check**: for every rule or behaviour the plan changes, which `INV-n` could now break,
     and for every action it adds, which invariants and hazards apply; a **hazard check**: every `HZ-n` that applies
     but the plan's **Hazards that apply** section does not name, and any the plan re-opens (re-opened = treated like
     an invariant violation); a **trust-boundary check**: any new host, download, opened link or file, file write or
     delete, or path from settings is held to INV-1…INV-4 and INV-8…INV-10;
     a **module-design lens** (`code-conventions.md` § Module design; `codebase-design` vocabulary) on every function
     the plan adds or changes: decisions are pure functions, Windows / network / disk code only calls them · deep
     (small interface, real behaviour) · the interface is the test surface · passes the deletion test · a seam only
     where something varies · dependencies passed in where a test needs them;
     a **Windows-proof lens**: name what the Mac tests can prove and what only the Windows check can, and put the
     latter in the plan's Testing & scope as named Windows-check steps;
     a **run-order lens**: for every slice not in the earliest wave it could join, name the function it shares or the
     result it needs. Tooling is never a reason (each lane has its own worktree). A wait that exists only because of a
     small addition (a setting key, a parameter) is moved — the addition goes in with a default so both slices share a
     wave. Two slices held apart only because they edit the same function are re-cut by function before a wave is
     added; when a re-cut would leave a slice with no payoff, keep the separate wave with a `shares <function>` reason.
     a **demo lens**: the critic is handed the approved design paths from the ledger and lists every place the plan
     departs from them. All of them go to allen as one [PM] list in the step 4 summary (each: keep the design / accept
     the change). Ledger says "none" → the lens reports "no approved design" and stops.
     **A design that violates an invariant is rejected, not scored.** Normal work: one critic agent runs these
     checks on the one plan. Full panel: score + verdict per design.
   - **Synthesize** (full panel only) — ONE plan: best spine + best grafts + every confirmed fix; drop scope-creep /
     invariant breaks; the plan must **decide, not punt** the hard forks.
   **Default = normal work** (impact + map readers + one design + one critic). **Full panel** only for the trust
   boundary or a restructure of the file into modules (standard Phase 1). Say which lane in the Phase 2 summary.

4. **Feature doc + approve checkpoint (Phase 2).** Write `docs/features/<YYYY-MM-DD>-<name>.md` (`date +%F`).
   House shape: **What this is (and is not)** · **Affected components + comparison base** · **Settled-decisions
   ledger** · **Decision log (D1..Dn + Why)** · **Module structure** (functions added/changed, by file section) ·
   **Files and state** (files on disk, `settings.json` keys, seen history, shared state between threads) ·
   **Interface surface** (tray menu items, notifications, tooltip, settings the user edits) · **Invariant impact**
   (which `INV-n` the change touches, how each stays held) · **Hazards that apply** (each `HZ-n`, one line on how the
   plan keeps it closed) · **Threat + scale notes** (concrete to this change) · **Testing & scope** (Mac tests + the
   named Windows-check steps) · **Slice plan** (sized per Phase 5; each slice states its payoff — visible result, or
   the one it unlocks + slices away — and its **builder**: Codex by default, Claude `security-implementer` for a
   trust-boundary slice (step 7 list), plus every slice where `python3 ~/.claude/hooks/model-tiering.py --owner
   "<plain slice summary, no code>"` prints `claude`; allen ratifies the split at this checkpoint) · **Documented
   seams (flagged, not built)** · **Open decisions owed [PM]/[YOU]**. The Slice plan contains a **Run order**:
   numbered waves, e.g. "Wave 1: S1. Wave 2: S2, S3 (no shared functions). Wave 3: S4 (needs S2)." **Parallel is the
   default:** at most 4 to a wave; a slice held back states why (`check-record.mjs` refuses a lone-slice wave with no
   needs / shares / because). Summarize + **STOP** for approval before any code.
   Plan headings hold plan only — the review's spec reader takes a section down to the next same-level heading, so
   slice checkpoints, proof and review history go under `## Implementation checkpoints`, never under a plan heading.
   A revision decided during the build gets one line in the plan section's **Build revisions** list. A genuine plan
   heading the shape check misreads may end in `<!-- record-check: plan (<reason>) -->` with a nonempty reason.
   The Record ends with `## Next action`, whose first line is `Progress: <stage> | slice y/M · next <slice>: <2–5
   words> · rest: <names> → …`. Rewrite it at every slice checkpoint and at close-out, from git (a slice is done when
   its commit is in HEAD), never from memory.

5. **Ratify the forks (Phase 3).** Genuine decisions go out as a **decision message** (format above), each tagged
   **[PM]** (what the app does for its user) or **[YOU]** (eng call). Bank answers into the Record (RATIFIED) and
   into `docs/decisions.md` when they outlive this feature. Decisions settleable from code/conventions — settle them
   and say which; never infer RATIFIED from built.

6. **Understand before edit (Phase 4).** Trace every function to be touched (callers, threads, menu wiring, settings
   keys) and find the **exemplar** to mirror. No slice brief without the map.

7. **Build via implementer agents (Phase 5).** **On `main`? Branch off before the first slice** (`git switch -c
   <feature>`) and name the branch in the Record. **The session model does not write slices.** Author one brief per
   slice and hand it **straight to Codex** from this session's Bash — `.claude/scripts/codex-lane.sh launch <slice>
   <brief.md> <lane-worktree>` (the lane's own worktree is required), run in the background; recipe + traps:
   `docs/standards/environment.md`, the "Codex builder" bullet. When allen asks how a slice is going, answer from
   `.claude/scripts/codex-lane.sh status <slice>`. Never wrap it in a Claude `implementer` / `codex:codex-rescue`
   agent. Run the Record's Run order, without being asked: a wave's slices start together, each in its own worktree
   cut from the branch tip. A slice that needs an earlier uncommitted wave stacks on it (`environment.md`, "Stacking
   a lane"). The orchestrator alone writes the Record. Reviews run in the lanes, in parallel, with
   `/adversarial-review` `cwd`. **Landing a wave:** once every lane has passed review, apply the lanes to the branch
   (`environment.md`, "One file, many slices"), then run the gate on the landed tree and, after the last wave, the
   smoke; a wave's review never counts as proof of the landed tree. Codex fails, stalls or reports blocked → once
   `codex-lane.sh status <slice>` no longer says running (`codex-lane.sh stop <slice>` ends a stalled one), retry
   once with a fresh launch (`environment.md`, "Codex \"model at capacity\""), then fall back to `Agent
   subagent_type: "implementer"`; say so in the slice report. Slices on the **trust boundary** — `safe_get` /
   `ALLOWED_HOSTS` / download limits, opening links or files, deleting files, reading the user's folders, settings
   persistence — stay on Claude: `subagent_type: "security-implementer"`. Never fork.
   Brief sizing: one cohesive cluster, sized to its payoff. Each brief carries: a first line saying the reader is the
   builder of one slice, not the orchestrator · scope + exemplar + the `INV-n` / `HZ-n` it must hold · a **Module
   design** line ("follow `docs/standards/code-conventions.md` § Module design"; a logic slice names the pure function
   each new decision lives in) · a **Suggested skills** section (`codebase-design`; `/tdd` on any trust-boundary or
   logic rule — RED test first, real path, no mocks of the path under test; tests follow `code-conventions.md`
   § Tests, which wins over the brief) · DoD incl. the Phase 6 gate (`.claude/scripts/gate.sh code --log <file>`,
   path in the hand-back) · an **edit list** (every existing function the slice will change, with its GitNexus
   `impact` risk, run by the orchestrator BEFORE launch; any HIGH/CRITICAL goes to allen as ONE acceptance; the
   builder stops only on a function NOT on the list, after running `impact` on any helper it adds a caller to) · the
   **must-refuse list** (no commits, pushes, branch switches, edits outside the lane, canon doc edits or batons;
   append a checkpoint, never rewrite other Record sections) · a **HARD STOP** ("do NOT start the next slice").
   Reality contradicts the plan → refine + document the deviation in the Record ("Revised from the plan: …"), never
   silently diverge. Context already heavy → the wave runs as a fresh agent with its brief, never in-session. Handing
   the rest of the build to a new session (allen's call): run `/handoff` here first, and the new session starts with
   `/catchup`.

8. **Gate — proof over promise (Phase 6).**
   - **Lane first:** light or full, as defined in `feature-delivery.md` § Phase 6, confirmed with
     `python3 ~/.claude/hooks/model-tiering.py --lane "<plain summary of the actual diff>"` (Jev can only raise it).
     Light = the gate commands + go-ahead only; full = everything below. Unsure → full. Name the lane in the report.
   - **Gate commands:** `.claude/scripts/gate.sh code docs --log <file>` (the table in `feature-delivery.md`
     § Phase 6). Read the builder's log instead of re-running it while no file changed after it.
   - **Test check:** read new and changed tests against `docs/standards/code-conventions.md` § Tests — the rule's yes
     case and no case, no network, no wording pins. A miss goes back to the builder as a test-only pass.
   - **Cleanup pass** (full lane, every slice, after its tests are green): snapshot the tree first, without a commit
     (`environment.md`, "Slices built on one uncommitted tree"). Then a fresh builder of the same kind that did not
     write the slice cleans only lines the slice changed, non-test code only, behaviour unchanged: unneeded comments ·
     nesting an early return would flatten · a helper the file already has · patterns unlike the surrounding code.
     **Never remove, move or rewrite** a check on the trust boundary, a guard under a lock, or a check or comment an
     invariant, hazard or test relies on; `ponytail:` and `[PM]` notes stay; unsure = keep. If it changed a file it
     saves a new gate log, and any mutant whose rule line it changed is re-run. The orchestrator reads
     `git diff <before> <after>` before review.
   - **Orchestrator proof (every behaviour-changing feature, never delegated, BEFORE the review)** — rules in
     `feature-delivery.md` § Phase 6, "Orchestrator proof": (a) smoke the shipped functions ONCE per feature, after
     the last slice, on the Record's worked example + junk / edge inputs, actual output into the Record's Proof table;
     (b) spot-mutant — at least one hand-reverted rule per LOGIC slice yourself (revert → named test RED → restore,
     `cmp` clean); (c) re-run the gate + smoke after any fold.
   - **`/adversarial-review`** (Skill invocation only) after tests pass, before any commit / "done" — its `context`
     states the module-design property (no decision buried in Windows / network / disk code, no pass-through helper,
     no single-implementation abstraction, no test reaching past an interface): fold only CONFIRMED
     critical/high/medium; lows + PLAUSIBLE → residual list; re-scan a fold with `foldRescan: true`. Every round passes
     `invariantsDoc`: `docs/INVARIANTS.md` (rules the scanners assert, not focus hints — keep it out of `context`).
     Round 1 passes `spec`: the Record's plan sections for this slice as `path § heading` pointers — never
     checkpoint/proof sections; `spec_scope` findings go to the user as scope calls. Before passing them, list the
     sub-headings inside each pointed section (`grep -n '^#'`); any checkpoint, proof or review heading there moves
     to `## Implementation checkpoints` first.
   - **Codex attacker** (full lane, once per slice, while `/adversarial-review` runs; adds to it, never replaces it):
     a fresh `codex exec` in a throwaway worktree of the post-cleanup snapshot gets the slice's intent and this brief:
     "Break this change. Report each finding with the exact command, its output and the output the intent requires.
     List every command you ran and say whether setup worked. Leave out anything you did not run. Keep repros in this
     worktree, fix nothing, and never commit, push or switch branch. Set HOME to a temp dir before importing
     wallpaper_changer. No findings is a valid result." An empty hand-back with no commands run means it did not run:
     retry once, then say so. The orchestrator reruns each command, rates what reproduces on the review's severity
     rubric and folds it like a CONFIRMED finding; what does not reproduce goes to the residual list as PLAUSIBLE.
     Remove the worktree after.
   - **Trust-boundary abuse check** (any slice on the step 7 trust-boundary list): write a table of abuse cases under
     `## Implementation checkpoints` — a hostile redirect, an oversized or endless response, a huge image, a
     non-https or `file:` link from API data, a settings path pointing at a system folder, a malformed
     `settings.json` — each with the state that must hold afterwards. Every row ends **VERIFIED** (a test or command,
     cited, checks the files on disk and side effects, not only the return value), **FAILED**, **UNVERIFIED** (with
     why) or **N/A** (with why). A FAILED row blocks the slice; an UNVERIFIED row needs allen's explicit acceptance at
     the commit checkpoint.
   - **Windows check** (any behaviour a person would notice): after the Mac gate is green, write the exact steps from
     the Record's Testing & scope into the Record and ask allen to run them with
     `.claude/skills/verify-wallswap/SKILL.md` on a Windows PC. Until he reports back, the slice is "Mac-proven,
     Windows unverified" — later slices may build meanwhile; the Record names which slices he has checked.
   - **`/independent-test`** when the skill's four conditions hold (here: a rule over files on disk or the seen
     history that must hold for all inputs) — the skill owns the conditions and timing.
   - **Subtract before the last commit** (once per feature, after the last fold): for each test this feature added,
     find any existing test asserting the same rule on the same or stronger inputs, and delete the weaker twin, unless
     `docs/` or `.claude/` cites it or a Record names it as a mutant's only killer. Gate re-runs green after; report
     cases deleted per file.
   - Optionally `/code-review` on the diff — an aid, not a substitute.

9. **Reconcile + capture (Phase 7).** Align the Record with what shipped (deviations included) — a green test that
   doesn't drive the shipped path proves nothing. Re-assert the **Invariant impact** section against shipped code;
   new invariants or hazards → `docs/INVARIANTS.md` (next free ID, with the code that holds it; update cited line
   numbers the change moved). A new section, thread, file on disk or dependency → `docs/ARCHITECTURE.md`. A
   user-visible change → `README.md`. Update any `verify-wallswap` step this feature made untrue; a new user flow gets
   a step. Route durable learnings per `.claude/rules/wiki-lifecycle.md`. Memory only past the global write-gate.
   **Prune (tests only grow otherwise):** list existing tests this feature's new tests make redundant. Each cut needs
   proof run by the orchestrator: break the rule the test guards → a remaining test goes RED → restore; nothing RED =
   it was the only guard, keep it. Never cut the only test for an invariant or a regression test tied to a fix. The
   cut list goes to allen at the Phase 8 checkpoint.

10. **Close out + commit checkpoint (Phase 8).** Done / left checklist, including the Windows check status.
    `AskUserQuestion` for the **commit strategy** (branch first if on `main`) and **next-step forks**. Write the baton
    via **`/handoff`**. **Commit only when the user asks**; message format follows `AGENTS.md` (enforced by
    `.githooks/commit-msg`). Stage by exact path from the slice's own file list (never `git add <dir>` / `-A`), and
    commit only when `git diff --cached --name-only` equals that list.
