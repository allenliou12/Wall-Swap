import assert from 'node:assert/strict';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const here = path.dirname(fileURLToPath(import.meta.url));
const name = 'docs/features/2026-11-02-example.md';
const titles = ['What this is', 'Affected components', 'Settled-decisions ledger', 'Decision log', 'Module structure', 'Files and state', 'Interface surface', 'Invariant impact', 'Hazards that apply', 'Threat + scale notes', 'Testing & scope', 'Slice plan', 'Documented seams', 'Open decisions owed', 'Next action'];
const runOrder = 'Run order: Wave 1: S1.';
const valid = (titles.map(title => `## ${title}\n${title === 'Next action' ? 'Progress: ready' : 'Plan.'}`).join('\n\n') + '\n').replace('\n\n## Documented seams', `\n${runOrder}\n## Documented seams`);
const quote = value => `'${value.replaceAll("'", "'\\''")}'`;

export function selfTest() {
  const root = mkdtempSync(path.join(tmpdir(), 'wallswap-record-'));
  const fixtureEnv = () => Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('GIT_') && key !== 'RECORD_JEV_CMD'));
  let cases = 0;
  let fixtures = 0;
  const test = (label, check) => {
    try { check(); cases++; } catch (error) { error.message = `${label}: ${error.message}`; throw error; }
  };
  const fixture = () => {
    const dir = path.join(root, String(++fixtures));
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(dir, file)), { recursive: true });
      writeFileSync(path.join(dir, file), text);
    };
    put('.claude/scripts/.keep', '');
    if (existsSync(path.join(here, 'check-record.mjs'))) copyFileSync(path.join(here, 'check-record.mjs'), path.join(dir, '.claude/scripts/check-record.mjs'));
    const git = (...args) => {
      const result = spawnSync('git', ['-C', dir, ...args], { encoding: 'utf8', env: fixtureEnv() });
      assert.equal(result.status, 0, result.stderr);
      return result.stdout.trim();
    };
    git('init', '-qb', 'main');
    git('config', 'core.hooksPath', path.join(dir, 'no-hooks'));
    const commit = () => {
      git('add', '.');
      git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture');
    };
    commit();
    const fake = body => {
      put('fake-jev.mjs', body);
      return `${quote(process.execPath)} ${quote(path.join(dir, 'fake-jev.mjs'))}`;
    };
    const cli = (args = [], command = fake("console.log('UNAVAILABLE');")) => spawnSync(process.execPath, [path.join(dir, '.claude/scripts/check-record.mjs'), ...args], {
      cwd: dir, encoding: 'utf8', timeout: 60000,
      env: { ...fixtureEnv(), RECORD_JEV_CMD: command },
    });
    const spy = (score = 0) => fake(`import { readFileSync, writeFileSync } from 'node:fs'; const payload = JSON.parse(readFileSync(0, 'utf8')); writeFileSync(${JSON.stringify(path.join(dir, 'payload.json'))}, JSON.stringify(payload)); console.log(JSON.stringify(payload.map(() => ${score})));`);
    const payload = () => JSON.parse(readFileSync(path.join(dir, 'payload.json'), 'utf8'));
    return { dir, put, git, commit, cli, fake, spy, payload };
  };
  const check = (body, expected = []) => {
    const f = fixture();
    f.put(name, body);
    const result = f.cli();
    assert.equal(result.status, expected.some(line => line.startsWith('FLAG ')) ? 1 : 0, result.stdout + result.stderr);
    assert.equal(result.stdout, [...expected, 'SCANNED 1 records', `FLAGS ${expected.filter(line => line.startsWith('FLAG ')).length}`, ''].join('\n'));
    assert.equal(result.stderr, '');
  };
  try {
    test('valid Record passes through the CLI', () => {
      const f = fixture();
      f.put(name, valid);
      const result = f.cli();
      assert.equal(result.status, 0, result.stdout + result.stderr);
      assert.equal(result.stdout, 'SCANNED 1 records\nFLAGS 0\n');
      assert.equal(result.stderr, '');
    });
    for (const title of titles) test(`missing heading: ${title}`, () => {
      const f = fixture();
      f.put(name, valid.replace(`## ${title}\n`, ''));
      const result = f.cli();
      assert.equal(result.status, 1, result.stdout + result.stderr);
      assert.equal(result.stdout, `FLAG ${name}:1 missing-heading add "## ${title}"\nSCANNED 1 records\nFLAGS 1\n`);
    });
    test('Next action is last', () => check(valid + '\n## More plans\n', [
      `FLAG ${name}:43 next-action-last move "## Next action" to the end`,
    ]));
    test('first nonempty Next action line reports its physical line', () => check(valid.replace('Progress: ready', '\n\nReady.'), [
      `FLAG ${name}:46 progress-line start the first nonempty line with "Progress:"`,
    ]));
    test('Slice plan needs a run order', () => check(valid.replace(`${runOrder}\n`, '\n'), [
      `FLAG ${name}:34 run-order add a "Run order" of numbered waves to the Slice plan`,
    ]));
    const oneByOne = `FLAG ${name}:36 one-by-one parallel is the default: put slices that share no files in one wave, or say why this one waits (needs / shares / because)`;
    const order = text => valid.replace(runOrder, text);
    test('one slice per wave with no reason is refused', () => check(order('Run order: Wave 1: S1. Wave 2: S2. Wave 3: S3.'), [oneByOne]));
    test('one slice per wave with a reason passes', () => check(order('Run order: Wave 1: S1. Wave 2: S2. All sequential, because each edits page.tsx.')));
    test('a lone wave among parallel ones needs its own reason', () => check(order('Run order:\n- **Wave 1:** S1, S2.\n- **Wave 2:** S3.'), [oneByOne]));
    test('a lone wave that says why passes', () => check(order('Run order:\n- **Wave 1:** S1, S2.\n- **Wave 2:** S3 — needs S1.')));
    test('ranges count as several slices', () => check(order('Run order:\n- Wave 1: S1–S3.\n- Wave 2: S4-S7.')));
    test('slice text after the run order is not read', () => check(order('Run order: Wave 1: S1, S2. Wave 2: S3, S4.\n\n**S1 · Wave 9: S9.**')));
    test('empty Next action still needs progress', () => check(valid.replace('Progress: ready\n', ''), [
      `FLAG ${name}:44 progress-line start the first nonempty line with "Progress:"`,
    ]));
    test('checkpoints after Next action violate both ordering rules', () => check(valid + '\n## Implementation checkpoints\n', [
      `FLAG ${name}:43 next-action-last move "## Next action" to the end`,
      `FLAG ${name}:46 checkpoints-order move "## Implementation checkpoints" before "## Next action"`,
    ]));
    for (const heading of ['Checkpoint 1', 'CHECKPOINTS', 'Proof', 'Fold fixes', 'Review round 2', 'Deep proof']) {
      test(`history heading: ${heading}`, () => check(valid.replace('## Slice plan\nPlan.', `## Slice plan\nPlan.\n${heading === 'Deep proof' ? '######' : '###'} ${heading}`), [
        `FLAG ${name}:36 history-under-plan move history under "## Implementation checkpoints"`,
      ]));
    }
    test('whole words and exact Build revisions remain plan', () => check(valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Build revisions\n### Folder layout\n### Checkpointing\n### Proofreading')));
    test('protected sections may contain history', () => check(valid.replace('## Next action', '## Implementation checkpoints\n### Checkpoint proof fold review round\n\n## Next action') + '\n### Proof\n'));
    test('numbered headings and required prefixes', () => check(valid.replace(/^## (.+)$/gm, '## 5. $1 (details)')));
    for (const delimiter of ['```', '~~~', '````', '~~~~']) test(`fenced headings ignored: ${delimiter}`, () => {
      check(valid + `\n${delimiter}markdown\n## Wrong final heading\n### Proof\n${delimiter.length === 4 ? delimiter.slice(1) + '\n## Still fenced\n' : ''}${delimiter}\n`);
      check(valid.replace('## What this is\n', '') + `\n${delimiter}\n## What this is\n${delimiter}\n`, [
        `FLAG ${name}:1 missing-heading add "## What this is"`,
      ]);
    });
    test('nonempty plan exception is explicit', () => check(valid.replace('## Slice plan\nPlan.', '## Slice plan\nPlan.\n### Proof strategy <!-- record-check: plan ( prospective test design ) -->'), [
      `EXEMPT ${name}:36 prospective test design`,
    ]));
    test('empty reason is not an exception', () => check(valid.replace('## Slice plan\nPlan.', '## Slice plan\nPlan.\n### Proof <!-- record-check: plan (   ) -->'), [
      `FLAG ${name}:36 history-under-plan move history under "## Implementation checkpoints"`,
    ]));
    test('old Records and every nested archive are ignored', () => {
      const f = fixture();
      f.put('docs/features/2026-11-01-old.md', 'bad');
      f.put('docs/features/archive/2026-11/2026-11-02-old.md', 'bad');
      f.put('docs/features/other/2026-11-03-nested.md', 'bad');
      f.put('docs/features/README.md', 'bad');
      f.put('docs/features/2026-11-03-new.md', valid);
      assert.equal(f.cli().stdout, 'SCANNED 1 records\nFLAGS 0\n');
    });
    test('default never calls Jev', () => {
      const f = fixture();
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Build detail'));
      assert.equal(f.cli([], f.spy(.99)).stdout, 'SCANNED 1 records\nFLAGS 0\n');
      assert.equal(existsSync(path.join(f.dir, 'payload.json')), false);
    });
    for (const state of ['untracked', 'unstaged', 'staged']) test(`changed checks ${state} Records`, () => {
      const f = fixture();
      if (state !== 'untracked') { f.put(name, valid); f.commit(); }
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Build detail'));
      if (state === 'staged') f.git('add', name);
      const result = f.cli(['--changed'], f.spy(.71));
      assert.equal(result.status, 1, result.stdout + result.stderr);
      assert.equal(result.stdout, `FLAG ${name}:35 jev-history move history under "## Implementation checkpoints" or mark a genuine plan heading\nSCANNED 1 records\nFLAGS 1\n`);
      assert.deepEqual(f.payload(), [{ section: 'Slice plan', heading: 'Build detail', opening_text: `${runOrder} Plan.` }]);
    });
    test('Jev threshold accepts .69 and flags .70', () => {
      const f = fixture();
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Build detail'));
      assert.equal(f.cli(['--changed'], f.spy(.69)).stdout, 'SCANNED 1 records\nFLAGS 0\n');
      const result = f.cli(['--changed'], f.spy(.70));
      assert.equal(result.status, 1, result.stdout + result.stderr);
      assert.match(result.stdout, /:35 jev-history /);
    });
    test('only new raw headings enter the payload', () => {
      const f = fixture();
      const baseline = valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Existing design\nOld explanation.');
      f.put(name, baseline);
      f.commit();
      f.put(name, baseline.replace('Old explanation.', 'Changed explanation.\n### New design\nOpening detail.'));
      const result = f.cli(['--changed'], f.spy(.69));
      assert.equal(result.status, 0, result.stdout + result.stderr);
      assert.deepEqual(f.payload(), [{ section: 'Slice plan', heading: 'New design', opening_text: `Opening detail. ${runOrder} Plan.` }]);
    });
    test('unchanged Records do not invoke Jev', () => {
      const f = fixture();
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Existing design'));
      f.commit();
      assert.equal(f.cli(['--changed'], f.spy(.99)).stdout, 'SCANNED 0 records\nFLAGS 0\n');
      assert.equal(existsSync(path.join(f.dir, 'payload.json')), false);
    });
    test('changed body under an old raw heading does not invoke Jev', () => {
      const f = fixture();
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Existing design\nBefore.'));
      f.commit();
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Existing design\nAfter.'));
      assert.equal(f.cli(['--changed'], f.spy(.99)).stdout, 'SCANNED 1 records\nFLAGS 0\n');
      assert.equal(existsSync(path.join(f.dir, 'payload.json')), false);
    });
    test('exact flags, exceptions, Build revisions and protected headings never enter Jev', () => {
      const f = fixture();
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Proof\n### Build revisions\n### Future review <!-- record-check: plan (planned review) -->')
        .replace('## Next action', '## Implementation checkpoints\n### Shipped detail\n\n## Next action') + '\n### Next detail\n');
      const result = f.cli(['--changed'], f.spy(.99));
      assert.equal(result.status, 1, result.stdout + result.stderr);
      assert.equal(result.stdout, `FLAG ${name}:35 history-under-plan move history under "## Implementation checkpoints"\nEXEMPT ${name}:37 planned review\nSCANNED 1 records\nFLAGS 1\n`);
      assert.equal(existsSync(path.join(f.dir, 'payload.json')), false);
    });
    test('new spelling of a raw heading is checked', () => {
      const f = fixture();
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Existing design'));
      f.commit();
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n###  Existing design'));
      assert.equal(f.cli(['--changed'], f.spy(.71)).status, 1);
      assert.equal(f.payload()[0].heading, 'Existing design');
    });
    test('payload contains only bounded fields and five physical opening lines', () => {
      const f = fixture();
      f.put(name, valid.replace('## Slice plan\nPlan.', `## 5. Slice plan ${'s'.repeat(100)}\n### ${'h'.repeat(150)}\nOne.\n\n#### Skip heading\nTwo.\nThree.\nNot in the first five.`));
      const result = f.cli(['--changed'], f.spy());
      assert.equal(result.status, 0, result.stdout + result.stderr);
      assert.deepEqual(f.payload()[0], { section: `Slice plan ${'s'.repeat(69)}`, heading: 'h'.repeat(120), opening_text: 'One. Two. Three.' });
      f.put(name, valid.replace('## Slice plan\nPlan.', `## Slice plan\n### Design\n${'x'.repeat(300)}`));
      f.cli(['--changed'], f.spy());
      assert.equal(f.payload()[0].opening_text, 'x'.repeat(240));
    });
    test('Jev global cap spans Records', () => {
      const f = fixture();
      const body = valid.replace('## Slice plan\nPlan.', `## Slice plan\n${Array.from({ length: 11 }, (_, i) => `### Design ${i}`).join('\n')}`);
      f.put(name, body);
      f.put('docs/features/2026-11-03-second.md', body);
      const result = f.cli(['--changed'], f.spy(.69));
      assert.equal(result.status, 0, result.stdout + result.stderr);
      assert.equal(result.stdout, 'WARN Jev cap: checking 20 of 22 headings\nSCANNED 2 records\nFLAGS 0\n');
      assert.equal(f.payload().length, 20);
    });
    for (const [score, status] of [[2, 1], [-1, 0]]) test(`finite numeric score ${score} follows the threshold`, () => {
      const f = fixture();
      f.put(name, valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Design detail'));
      const result = f.cli(['--changed'], f.spy(score));
      assert.equal(result.status, status, result.stdout + result.stderr);
      assert.equal(result.stdout, score === 2
        ? `FLAG ${name}:35 jev-history move history under "## Implementation checkpoints" or mark a genuine plan heading\nSCANNED 1 records\nFLAGS 1\n`
        : 'SCANNED 1 records\nFLAGS 0\n');
    });
    for (const [label, fake, reason] of [
      ['unavailable', "console.log('UNAVAILABLE');", 'unavailable'],
      ['crash', 'process.exit(7);', 'command exited 7'],
      ['invalid JSON', "console.log('garbage');", 'invalid output'],
      ['wrong count', "console.log('[]');", 'invalid output'],
      ['wrong shape', "console.log('{}');", 'invalid output'],
      ['wrong score type', `console.log('["0.9"]');`, 'invalid output'],
      ['null score', "console.log('[null]');", 'invalid output'],
    ]) test(`Jev ${label} fails open while exact flags remain failures`, () => {
      const f = fixture();
      const body = valid.replace('## Slice plan\nPlan.', '## Slice plan\n### Design detail');
      f.put(name, body);
      const command = f.fake(fake);
      const result = f.cli(['--changed'], command);
      assert.equal(result.status, 0, result.stdout + result.stderr);
      assert.equal(result.stdout, `WARN Jev check skipped: ${reason}\nSCANNED 1 records\nFLAGS 0\n`);
      f.put(name, body.replace('Progress: ready', 'Ready.'));
      const flagged = f.cli(['--changed'], command);
      assert.equal(flagged.status, 1, flagged.stdout + flagged.stderr);
      assert.equal(flagged.stdout, `FLAG ${name}:44 progress-line start the first nonempty line with "Progress:"\nWARN Jev check skipped: ${reason}\nSCANNED 1 records\nFLAGS 1\n`);
    });
    test('changed scope and deletion do not run Jev', () => {
      const f = fixture();
      f.put(name, valid);
      f.commit();
      rmSync(path.join(f.dir, name));
      f.put('docs/features/2026-11-01-old.md', 'bad');
      f.put('docs/features/archive/2026-11/2026-11-02-old.md', 'bad');
      const result = f.cli(['--changed'], f.spy(.99));
      assert.equal(result.status, 0, result.stdout + result.stderr);
      assert.equal(result.stdout, 'SCANNED 0 records\nFLAGS 0\n');
      assert.equal(existsSync(path.join(f.dir, 'payload.json')), false);
    });
    test('bad CLI arguments are tool errors', () => {
      const f = fixture();
      for (const args of [['--unknown'], ['main'], ['--changed', '--self-test']]) {
        const result = f.cli(args);
        assert.equal(result.status, 2, result.stdout + result.stderr);
        assert.match(result.stderr, /^ERROR usage:/);
      }
    });
    test('real git failure is a tool error', () => {
      const f = fixture();
      f.put(name, valid);
      renameSync(path.join(f.dir, '.git'), path.join(f.dir, '.git-hidden'));
      const result = f.cli(['--changed']);
      assert.equal(result.status, 2, result.stdout + result.stderr);
      assert.match(result.stderr, /^ERROR git-failed diff:/);
    });
    console.log(`SELF-TEST PASS: ${cases} cases`);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) selfTest();
