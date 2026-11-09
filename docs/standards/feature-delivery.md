# WallSwap — Feature Delivery Standard

> **Status:** canonical standard for how a feature goes from request → shipped here. Runner: **`/feature`**
> (`.claude/commands/feature.md`) — the *do*, step by step; this doc is the *why* plus the tables and gate rules other
> docs cite. The session's user-level rules (model tiering · adversarial review gate · grilling gate) are baked in.

---

## 0. The shape (why this exists)

WallSwap is small, but it runs unattended on someone's PC, downloads images from the internet and writes into their
Pictures folder. The expensive mistakes are silent: a download check that stops checking, a cleanup that reaches a
folder it should not, a guard (fullscreen, SFW) that quietly returns "no". None of those fail loudly, and the app
only runs on Windows while it is built on a Mac. So the lifecycle front-loads a **settled-decisions ledger + grill +
blast radius + an invariant-lensed critique + ratified forks** before code, and back-loads **proof + adversarial
review + a Windows check + reconciliation + a baton** so the next session inherits truth, not claims. Reduced:
**ledger what's decided → grill what isn't → map the real code → critique a plan (invariant lens) → ratify forks →
build sized slices → prove + adversarial review → reconcile → hand off.**

---

## 1. The lifecycle (checkpoints are load-bearing)

| Phase | Produces | STOP for a human? |
|---|---|---|
| **0 · Orient** | request in context + comparison base + **settled-decisions ledger** | — |
| **0.5 · Grill** | intent gaps closed via `/grilling` (scoped to what the ledger does NOT cover) | answers, in conversation |
| **1 · Plan (impact + map + critique)** | blast-radius map + one plan, hard forks surfaced | — |
| **2 · Feature doc** | `docs/features/<date>-<name>.md` | ✅ **approve the plan** |
| **3 · Ratify forks** | genuine [PM]/[YOU] decisions decided | ✅ **AskUserQuestion** |
| **4 · Understand before edit** | file/pattern map (callers + exemplar) | — |
| **5 · Build** | sized slice briefs → Codex by default, `security-implementer` for trust-boundary slices; parallel waves | — |
| **6 · Gate** | proof + `/adversarial-review` (+ `/independent-test` when its conditions hold) | — |
| **7 · Reconcile + capture** | doc aligned to code; invariants promoted; memory past the write-gate | — |
| **8 · Close out** | checklist → `/handoff` → commit on ask | ✅ **approve commit + next** |

### Phase 0 — Orient + settled-decisions ledger
Steps: runner step 1. The truth order is `AGENTS.md`'s; `docs/INVARIANTS.md` wins, code establishes as-built facts,
and a mismatch is flagged rather than silently ratified. The ledger lists every decision already made that bears on
the change — recorded decisions are facts, never re-asked.

### Phase 0.5 — Grill
`/grilling` attacks the **intent** (build the right thing); the Phase 1 critique attacks the **plan**; the Phase 6
review attacks the **code**. Steps: runner step 2.

### Phase 1 — Plan via impact + map + critique
Steps, stages and lenses: runner step 3. A design that violates an invariant is **rejected, not scored**. **Full
panel** (several competing designs, then synthesis) only when the change touches the trust boundary (downloads,
allowed hosts, opening links or files, deleting files, the user's folders, settings persistence) or restructures the
file into modules; everything else is normal work (one design, one critic). The Phase 2 summary names the lane.

### Phase 2 — Feature doc → approve checkpoint
House shape: runner step 4. **Threat + scale notes** are concrete to the change. Each **Slice plan** slice states its
**payoff**: what the person using the app can see when it lands, or, for groundwork, which visible result it unlocks
and how many slices away. The **Run order** is parallel by default. Stop for approval.

### Phase 3 — Ratify forks → AskUserQuestion checkpoint
Steps: runner step 5. **[PM]** = what the app does for its user; **[YOU]** = eng call. Built does not imply RATIFIED.

### Phase 4 — Understand before edit
Callers + the exemplar to mirror. No brief without the map. The single file means most slices share it: re-cut by
section or function before adding a wave (runner step 3, run-order lens).

### Phase 5 — Build via implementer agents
**The session model orchestrates; it does not write slices.** Builder split, brief contents and wave mechanics:
runner step 7. Each brief carries an **edit list** (every existing function the slice changes, `impact` run before
launch, HIGH/CRITICAL accepted once); the builder stops on an unlisted symbol. HARD STOP at the end of each brief.
Trust-boundary paths are test-first (`/tdd`): RED test before implementation, real path, no mocks of the path under
test. Deviations from the plan are documented in the doc, never silent.

### Phase 6 — Gate (proof over promise)

**Two lanes — each slice report names its lane; unsure → full gate.**
- **Light lane** — docs, README, copy (menu labels, notifications), comments, tooling text. Gate = the commands below
  + the go-ahead on a screenshot or text diff. No mutants, no `/adversarial-review`.
- **Full gate** — any change to behaviour in `wallpaper_changer.py`; anything on the trust boundary (Phase 1 list).

**One command runs a row:** `.claude/scripts/gate.sh <code|docs>... --log <file>` (one `EXIT <part> <step>=<code>`
line per step, full output in the log, exit 1 on any failure). The Windows check and mutants stay manual.

| Part | Build / type | Lint | Test |
|---|---|---|---|
| `code` | `uv run python -m py_compile wallpaper_changer.py` | `uv run ruff check .` exit 0 (bug-finding rules only, D1) | `uv run pytest -q`, pass COUNT recorded; Windows calls are stubbed (D2) |
| `docs` / tooling | — | `node .claude/scripts/check-doc-links.mjs`; `node .claude/scripts/check-record.mjs` | tooling self-tests: `node .claude/scripts/check-record.mjs --self-test`, `check-doc-links.mjs --self-test`, `sync-runner-copies.mjs --self-test`, `sh .claude/scripts/codex-lane.sh --self-test` |

**Windows check — any behaviour a person would notice** (tray, wallpaper, lock screen, notifications, files): after
the Mac gate is green, the change is checked on a Windows PC with `.claude/skills/verify-wallswap/SKILL.md`. Until
allen reports that run, the slice is "Mac-proven, Windows unverified" — say so at the commit checkpoint, never "done".

**Orchestrator proof — every behaviour-changing feature, before the review, never delegated.**
- **Smoke the shipped path — once per feature** (after the last slice). Run the real functions on the Record's worked
  example plus junk / edge inputs in a throwaway script under the scratchpad, with `HOME` pointed at a temp dir
  (`docs/standards/environment.md`, "Import writes to the home folder"), and paste the actual output into the
  Record's Proof table. Network sources: stub `requests.get` with recorded responses; a live fetch is optional extra
  proof, never the only proof.
- **Spot-mutant — logic slices only** (a branch, guard, calculation or state change). Revert the rule → a named test
  goes RED → restore (`cmp` clean). Builders run it before review; the orchestrator runs at least one per logic slice
  itself. The Proof table marks orchestrator-run versus builder-reported checks.
- **Re-run after every fold.** A review fix changes shipped code: the gate + the same smoke again before the commit
  checkpoint. Order = slice tests green → cleanup pass (full lane) → orchestrator proof → `/adversarial-review` +
  Codex attacker → fold → gate + smoke → `/independent-test` if it applies → reconcile.

Then **`/adversarial-review`** before any commit or "done" (how to call it: runner step 8). Round 1 passes the
Record's plan sections as `spec`, so plan headings hold plan only and checkpoints/proof go under
`## Implementation checkpoints`. `/code-review` = an aid, not a substitute.

### Phase 7 — Reconcile + capture
Steps: runner step 9. Doc ≡ code, deviations included; new invariants go to `docs/INVARIANTS.md`. **Prune** exists
because tests only grow otherwise; allen approves the cut list at the Phase 8 checkpoint.

### Phase 8 — Close out → commit checkpoint
Steps: runner step 10. **Commit only when the user asks.**

---

## 2. Scope discipline

Before adding a module / dependency / setting / source / file on disk: **does the ratified plan or an in-flight slice
actually need this?** Tie every addition to a live need. "Someday" surfaces (another OS, multiple monitors, a second
favourite game) get a clean **seam** now and a line under "Documented seams (flagged, not built)".

---

## 3. Operating principles

- **Proof over promise.** No "done" without evidence — diff, test counts, exit codes, review verdicts.
- **Invariants are non-negotiable.** Re-asserted at plan time and reconcile time. A violation rejects the design.
- **Understand before edit.**
- **Bug → prevention.** Regression test + lesson routed to its durable home (`wiki-lifecycle.md`).
- **Code smell = pain signal.** Flag it; unasked refactor of untouched code is not the fix — the user decides.
- **Mirror, don't invent.** New code reads like the code next to it.
- **Right-size.** Not more (speculative abstraction), not less (band-aid).
- **Doc ≡ code.**

---

## 4. Artifacts a feature leaves behind

| Artifact | Where | Purpose |
|---|---|---|
| Feature doc (Record) | `docs/features/<date>-<name>.md` | plan + decision log + invariant impact + proof |
| Slice briefs | scratchpad (transient by design) | never rescued into repo or memory |
| Handoff baton | `docs/handoff/<date>-<app>-<kebab>.md` | role-tagged context for the next session |
| Promoted canon | `docs/INVARIANTS.md` · `docs/ARCHITECTURE.md` · `docs/decisions.md` · `docs/standards/*` | durable rules/facts at their single home |
| Memory | project auto-memory (`MEMORY.md` index) | only what the repo cannot record |
| Commit | git (branch-first on `main`), on ask | the code, message states the proof |

---

## 5. Tray UX bar

Every menu item, notification and tooltip a change adds is checked against these, on the Windows check:

1. **What is it?** The label says what happens ("Next Wallpaper", not "Go").
2. **Did it work?** Every action ends in a visible result: the wallpaper changes, or a notification says what
   happened or what to fix. Nothing fails silently.
3. **What's the state?** A toggle shows its state (checkmark, paused icon); the tooltip names the current wallpaper.
4. **Can it be undone?** Anything that deletes or overwrites says so before it happens.
