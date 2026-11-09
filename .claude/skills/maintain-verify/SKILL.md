---
name: maintain-verify
description: Audit the verify-wallswap flows against the current code and correct what has drifted. Use after a run of tray or behaviour changes, or before relying on the flows for a release check.
---

# Maintain verify-wallswap

Flows drift as the app changes. This pass checks every flow in `.claude/skills/verify-wallswap/SKILL.md` against the
source, then corrects the file. It ends in one outcome: **clean**, **changed** or **blocked**, and says which.

Edit only `.claude/skills/verify-wallswap/`. App behaviour that is wrong is a bug to report, never something to write
into a flow.

## Pass

1. **Read the source, per flow.** One read-only reader per flow, on the mechanical tier, reports how the flow works
   today (menu item, function, log line, file it writes), any line of the flow the code contradicts with `file:line`,
   and tray menu items or user-visible behaviours no flow covers. Done when every flow has a report.
2. **Sort each finding** and verify it yourself first:
   - **Doc drift:** the app is right and the flow is wrong. Fix the flow.
   - **Coverage gap:** a real menu item or behaviour has no flow. Add one.
   - **Product bug:** the app is wrong. Report it for `/fix` and leave the flow saying what should happen.
3. **Live check (optional).** Changed flows can go to allen as one Windows checklist (`verify-wallswap` § Prepare).

**Reply** in plain words: the outcome, each flow's result, what changed in the file, and any product bugs. Commit only
when the owner asks.
