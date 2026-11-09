# Session Batons (`docs/handoff/`)

A **baton** is the ephemeral write-down of session state: what a session was doing, what's in flight, and the *one*
next action — enough for the next session to pick up without re-deriving context. It is the **Log** class of
`.claude/rules/doc-lifecycle.md`: read once, then cold. Durable learnings do **not** live here — they get promoted
into canon first (`.claude/rules/wiki-lifecycle.md` routing table); the baton only points to where they landed.

## One stream, role-tagged

```
docs/handoff/<YYYY-MM-DD>-<app>-<kebab>.md
```

- `<YYYY-MM-DD>` — `date +%F`, never hardcode.
- `<app>` — the **component role** the session touched (`AGENTS.md` table): `sources` · `app` · `windows` ·
  `tooling` · `docs`. Cross-cutting work uses the role that *owns the decision*. Planning-only sessions use `docs`.
- `<kebab>` — short kebab title of what the session actually did.

**Never overwrite an earlier session's baton.** Each session gets its own dated file; same-day collisions are
disambiguated by slug. Write a protective baton before compaction, then refresh that SAME current-session path after
compaction/gates with actual branch/dirt, promotions, archive/KEEP outcomes, gate exits and Next step.

## The two runners

| Runner | Role | Reads / Writes |
|---|---|---|
| `/catchup <task>` | **read** — print live state, then Tier 0 = `AGENTS.md` + project auto-memory + latest baton; progressively load canon | reads |
| `/handoff` | **write + compact** — promote learnings, protect the current-session baton, retention, gates, then refresh that same baton | writes + moves |

These override the global `handoff` skill (which writes to the OS temp dir).

## Shared ordering and live inventory

Both runners use the same order: filename date descending; within a date, original Git addition commit newest
first; uncommitted files precede committed files of the same date (ties by mtime, then basename descending). Missing
addition history means ordering is uncertain and the file must be kept. Only regular files with the baton filename
shape count; aliases and archives are excluded. Record status excerpts are **unverified** until checked against live
source and later proof.

Run this read-only recipe from the repository root. `/handoff` removes `.slice(0, 1)` to print each role's full
ordered stream when deciding the newest-three boundary.

```sh
git branch --show-current
git rev-parse HEAD
git status --short
node --input-type=module <<'NODE'
import { execFileSync } from 'node:child_process';
import { existsSync, lstatSync, readdirSync, readFileSync } from 'node:fs';

const committed = new Set(execFileSync('git', ['ls-tree', '-r', '--name-only', '-z', 'HEAD', '--', 'docs/handoff/'],
  { encoding: 'utf8' }).split('\0'));
const additions = new Map();
let rank = -1;
for (const line of execFileSync('git', ['log', '--topo-order', '--diff-filter=A',
  '--format=COMMIT %H', '--name-only', '--', 'docs/handoff/'], { encoding: 'utf8' }).split('\n')) {
  if (line.startsWith('COMMIT ')) rank++;
  else if (line.startsWith('docs/handoff/')) additions.set(line, rank);
}
const batons = [];
for (const name of readdirSync('docs/handoff')) {
  const match = /^(\d{4}-\d{2}-\d{2})-(sources|app|windows|tooling|docs)-.+\.md$/.exec(name);
  const path = `docs/handoff/${name}`;
  const stat = lstatSync(path);
  if (!match || !stat.isFile()) continue;
  batons.push({ path, name, date: match[1], app: match[2], committed: committed.has(path),
    rank: additions.get(path), mtime: stat.mtimeMs });
}
batons.sort((a, b) => b.date.localeCompare(a.date) || Number(a.committed) - Number(b.committed) ||
  (a.committed ? (a.rank ?? Infinity) - (b.rank ?? Infinity) : b.mtime - a.mtime) ||
  b.name.localeCompare(a.name));
if (!batons.length) console.log('Baton none yet');
for (const app of [...new Set(batons.map(baton => baton.app))].sort()) {
  const stream = batons.filter(baton => baton.app === app);
  for (const baton of stream.slice(0, 1)) {
    const note = !baton.committed ? 'new; KEEP' : baton.rank === undefined ? 'history unknown; KEEP' : 'in HEAD';
    console.log(`Baton ${app} (${stream.length} regular): ${baton.path} [${note}]`);
  }
}
const records = existsSync('docs/features') ? readdirSync('docs/features').sort().reverse() : [];
for (const name of records) {
  const path = `docs/features/${name}`;
  if (!/^\d{4}-\d{2}-\d{2}-.+\.md$/.test(name) || !lstatSync(path).isFile()) continue;
  const lines = readFileSync(path, 'utf8').split('\n');
  const progress = lines.find(line => line.startsWith('Progress:'));
  const status = progress || lines.filter(line => /^>/.test(line)).slice(0, 2).map(line => line.trim()).join(' | ');
  console.log(`Record ${path} [unverified]: ${status || 'no status excerpt'}`);
}
NODE
```

For `/handoff` after promotions/moves, the navigation gates (save full output and exit codes):

```sh
node .claude/scripts/check-doc-links.mjs
node .claude/scripts/check-record.mjs
```

## Retention and safe moves

Every `/handoff` keeps each role's newest **three** regular batons hot (all if fewer exist). Dirty/new files count
toward that window but are never moved. For each older baton and each hot shipped Record, verify promotion into canon
and actual completion before deciding KEEP / ARCHIVE. Current/in-flight work, pending prerequisites, uncertain
completion or missing addition history means KEEP with a reason. Only a regular, tracked, committed source that is
clean against HEAD may move. Never auto-commit to make it eligible.

Keep basenames and original content: batons move to `docs/handoff/archive/`; shipped Records move to
`docs/features/archive/<source-month>/` (month from the filename). Repair inbound paths in the same batch, then run
`node .claude/scripts/check-doc-links.mjs`. Full policy: `.claude/rules/doc-lifecycle.md`.

## Lean baton template

```markdown
# Handoff — <YYYY-MM-DD> · <app> · <Title>

## Goal
What the session set out to do (1–3 lines).

## Current State
What works (verified — test counts / `file:line` / commit hashes), what's running, branch + commit.

## Files in flight
Uncommitted/created files (complete, not mid-edit). `_None._` if none.

## Promoted
Durable learnings routed to canon this session, each as `<learning> → <file:section>`. `_None._` if none.

## Next step
**One** concrete action — exact command/file to start from, not a backlog.
```

If a section has no content, write `_None._` — don't pad. Don't re-narrate what was promoted; point to it.
