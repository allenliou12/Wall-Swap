import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn, spawnSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const CUTOFF = '2026-11-02'; // older Records predate the rules
const JEV_MIN = .7; // 2026-11-02 trial on 92 real headings, 51 of 58 history headings caught, one plan false flag
const required = ['What this is', 'Affected components', 'Settled-decisions ledger', 'Decision log', 'Module structure', 'Files and state', 'Interface surface', 'Invariant impact', 'Hazards that apply', 'Threat + scale notes', 'Testing & scope', 'Slice plan', 'Documented seams', 'Open decisions owed', 'Next action'];

function git(args) {
  const result = spawnSync('git', ['-C', root, ...args], { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  if (result.status !== 0) throw new Error(`git-failed ${args[0]}: ${result.stderr?.trim() || result.error?.message || result.status}`);
  return result.stdout;
}

function inScope(name) {
  return /^docs\/features\/\d{4}-\d{2}-\d{2}-.+\.md$/.test(name) && !name.slice('docs/features/'.length).includes('/') && name.slice(14, 24) >= CUTOFF;
}

function collectRecords(changed) {
  let names;
  if (changed) {
    names = [
      ...git(['diff', '--name-only', '-z', 'HEAD', '--', 'docs/features/']).split('\0'),
      ...git(['diff', '--cached', '--name-only', '-z', 'HEAD', '--', 'docs/features/']).split('\0'),
      ...git(['ls-files', '--others', '--exclude-standard', '-z', '--', 'docs/features/']).split('\0'),
    ];
  } else {
    try { names = readdirSync(path.join(root, 'docs/features')).map(name => `docs/features/${name}`); } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      names = [];
    }
  }
  return [...new Set(names)].filter(inScope).filter(name => {
    try { return statSync(path.join(root, name)).isFile(); } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      return false;
    }
  }).sort();
}

function headLines(name) {
  // A missing path is a new Record; a failed git command is still a tool error.
  if (!git(['ls-tree', '-z', 'HEAD', '--', `:(literal)${name}`])) return new Set();
  return new Set(git(['show', `HEAD:${name}`]).split(/\r?\n/));
}

function headingsIn(text) {
  const lines = text.split(/\r?\n/);
  const headings = [];
  let fence = null;
  let section = '';
  for (const [index, raw] of lines.entries()) {
    if (fence) {
      const close = raw.match(/^ {0,3}(`+|~+)\s*$/);
      if (close && close[1][0] === fence[0] && close[1].length >= fence.length) fence = null;
      continue;
    }
    const open = raw.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
    if (open && (open[1][0] !== '`' || !open[2].includes('`'))) {
      fence = open[1];
      continue;
    }
    const match = raw.match(/^ {0,3}(#{2,6})[\t ]+(.+?)\s*$/);
    if (!match) continue;
    const exception = match[2].match(/\s*<!-- record-check: plan \((.*?)\) -->$/);
    const exempt = exception?.[1].trim() || null;
    const title = match[2].slice(0, exception?.index ?? match[2].length).replace(/\s+#+$/, '').replace(/^\d+\.\s+/, '').trim().replace(/\s+/g, ' ');
    const level = match[1].length;
    if (level === 2) section = title;
    headings.push({ line: index + 1, raw, title, level, section, exempt });
  }
  return { lines, headings };
}

// Parallel is the default: a lone slice in a multi-wave plan says why it waits.
function runOrderFlags(lines, at, end) {
  let stop = at + 1;
  if (!/\bWave\b/i.test(lines[at])) while (stop < end && !lines[stop].trim()) stop++;
  while (stop < end && lines[stop].trim() && !/^ {0,3}#/.test(lines[stop])) stop++;
  const block = lines.slice(at, stop).join('\n');
  const reason = /\b(because|since|needs?|shares?|waits?|after)\b/i;
  const waves = block.split(/\bWave\s+\d+\b/i).slice(1).map(chunk => {
    const head = chunk.split(/\.\s|\.$|—|\(|\n/)[0];
    const ranges = [...head.matchAll(/S(\d+)\s*[–-]\s*S?(\d+)/g)];
    const count = ranges.reduce((sum, [, a, b]) => sum + Number(b) - Number(a) + 1, 0) + (head.replace(/S\d+\s*[–-]\s*S?\d+/g, '').match(/\bS\d+[a-z]?\b/g)?.length ?? 0);
    return { count, chunk };
  });
  if (waves.length < 2) return [];
  const fix = 'parallel is the default: put slices that share no files in one wave, or say why this one waits (needs / shares / because)';
  if (waves.every(wave => wave.count === 1)) return reason.test(block) ? [] : [{ line: at + 1, fix }];
  return waves.some(wave => wave.count === 1 && !reason.test(wave.chunk)) ? [{ line: at + 1, fix }] : [];
}

function checkRecord(text) {
  const { lines, headings } = headingsIn(text);
  const checks = [];
  const add = (line, rule, fix) => checks.push({ line, rule, fix });
  const sections = headings.filter(heading => heading.level === 2);
  for (const title of required) if (!sections.some(heading => heading.title.startsWith(title))) add(1, 'missing-heading', `add "## ${title}"`);
  const plan = sections.find(heading => heading.title.startsWith('Slice plan'));
  if (plan) {
    const end = sections.find(heading => heading.line > plan.line)?.line ?? lines.length + 1;
    const at = lines.slice(plan.line, end - 1).findIndex(line => /\bRun order\b/.test(line)) + plan.line;
    if (at < plan.line) add(plan.line, 'run-order', 'add a "Run order" of numbered waves to the Slice plan');
    else for (const flag of runOrderFlags(lines, at, end - 1)) add(flag.line, 'one-by-one', flag.fix);
  }
  const next = sections.find(heading => heading.title.startsWith('Next action'));
  if (next) {
    if (sections.at(-1) !== next) add(next.line, 'next-action-last', 'move "## Next action" to the end');
    const end = sections.find(heading => heading.line > next.line)?.line ?? lines.length + 1;
    let first = next.line;
    while (first < end - 1 && !lines[first].trim()) first++;
    if (first >= end - 1 || !lines[first].trim().startsWith('Progress:')) add(first < end - 1 ? first + 1 : next.line + 1, 'progress-line', 'start the first nonempty line with "Progress:"');
    for (const checkpoint of sections.filter(heading => heading.title.startsWith('Implementation checkpoints') && heading.line > next.line)) add(checkpoint.line, 'checkpoints-order', 'move "## Implementation checkpoints" before "## Next action"');
  }
  for (const heading of headings) {
    if (heading.level === 2 || heading.exempt || heading.title === 'Build revisions' || /^(Implementation checkpoints|Next action)/.test(heading.section)) continue;
    if (/\b(checkpoints?|proof|fold)\b|\breview round\b/i.test(heading.title)) add(heading.line, 'history-under-plan', 'move history under "## Implementation checkpoints"');
  }
  return { checks, headings, lines };
}

async function jevScores(payload) {
  const hook = path.join(homedir(), '.claude/hooks/model-tiering.py');
  const command = process.env.RECORD_JEV_CMD;
  if (!command && !existsSync(hook)) return { reason: 'hook not found' };
  const result = await new Promise(resolve => {
    const child = spawn(command || 'python3', command ? [] : [hook, '--record'], {
      cwd: root, shell: Boolean(command), detached: process.platform !== 'win32', stdio: ['pipe', 'pipe', 'ignore'],
    });
    let output = '';
    let finished = false;
    const finish = value => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      resolve(value);
    };
    const kill = () => {
      try {
        if (process.platform !== 'win32' && child.pid) process.kill(-child.pid, 'SIGKILL');
        else child.kill('SIGKILL');
      } catch (error) { if (error.code !== 'ESRCH') throw error; }
    };
    const timer = setTimeout(() => { kill(); finish({ reason: 'timeout after 45000ms' }); }, 45000);
    child.on('error', error => finish({ reason: error.message }));
    child.stdout.on('data', chunk => {
      output += chunk;
      if (output.length > 1024 * 1024) { kill(); finish({ reason: 'output too large' }); }
    });
    child.on('close', code => finish(code === 0 ? { output: output.trim() } : { reason: `command exited ${code}` }));
    child.stdin.on('error', () => {}); // A failed command may close stdin before reading its payload.
    child.stdin.end(JSON.stringify(payload));
  });
  if (result.reason) return result;
  if (result.output === 'UNAVAILABLE') return { reason: 'unavailable' };
  try {
    const scores = JSON.parse(result.output);
    if (!Array.isArray(scores) || scores.length !== payload.length || scores.some(score => typeof score !== 'number' || !Number.isFinite(score))) return { reason: 'invalid output' };
    return { scores };
  } catch { return { reason: 'invalid output' }; }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 1 && args[0] === '--self-test') {
    const { selfTest } = await import('./check-record.selftest.mjs');
    selfTest();
    return;
  }
  if (args.length > 1 || args.length === 1 && args[0] !== '--changed') throw new Error('usage: node .claude/scripts/check-record.mjs [--changed | --self-test]');
  const changed = args[0] === '--changed';
  const records = collectRecords(changed);
  let flags = 0;
  const candidates = [];
  for (const file of records) {
    const { checks, headings, lines } = checkRecord(readFileSync(path.join(root, file), 'utf8'));
    for (const check of checks) {
      console.log(`FLAG ${file}:${check.line} ${check.rule} ${check.fix}`);
      flags++;
    }
    for (const heading of headings) if (heading.exempt) console.log(`EXEMPT ${file}:${heading.line} ${heading.exempt}`);
    if (!changed) continue;
    const previous = headLines(file);
    for (const heading of headings) {
      if (heading.level === 2 || heading.exempt || heading.title === 'Build revisions' || /^(Implementation checkpoints|Next action)/.test(heading.section) || checks.some(check => check.line === heading.line) || previous.has(heading.raw)) continue;
      const opening = lines.slice(heading.line, heading.line + 5).filter(line => line.trim() && !/^\s*#{1,6}(?:\s|$)/.test(line)).join(' ').replace(/\s+/g, ' ').trim();
      candidates.push({ file, line: heading.line, payload: { section: heading.section.slice(0, 80), heading: heading.title.slice(0, 120), opening_text: opening.slice(0, 240) } });
    }
  }
  if (candidates.length > 20) console.log(`WARN Jev cap: checking 20 of ${candidates.length} headings`);
  const batch = candidates.slice(0, 20);
  if (batch.length) {
    const result = await jevScores(batch.map(candidate => candidate.payload));
    if (result.reason) console.log(`WARN Jev check skipped: ${result.reason}`);
    else for (const [index, score] of result.scores.entries()) if (score >= JEV_MIN) {
      const candidate = batch[index];
      console.log(`FLAG ${candidate.file}:${candidate.line} jev-history move history under "## Implementation checkpoints" or mark a genuine plan heading`);
      flags++;
    }
  }
  console.log(`SCANNED ${records.length} records\nFLAGS ${flags}`);
  process.exitCode = flags ? 1 : 0;
}

try { await main(); } catch (error) {
  console.error(`ERROR ${error.message}`);
  process.exitCode = 2;
}
