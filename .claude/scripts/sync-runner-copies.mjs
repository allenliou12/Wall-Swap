import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, utimesSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

function syncRunnerCopies(repoRoot, log = console.log) {
  const commands = path.join(repoRoot, '.claude/commands');
  const skills = path.join(repoRoot, '.agents/skills');
  if (!existsSync(skills)) {
    log('SKIP no .agents/skills');
    return;
  }
  for (const file of readdirSync(commands).filter(name => name.endsWith('.md')).sort()) {
    const name = file.slice(0, -3);
    const source = readFileSync(path.join(commands, file), 'utf8');
    const frontMatter = source.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
    if (!frontMatter) throw new Error(`${file}: missing or malformed front matter`);
    const description = frontMatter[1].match(/^description:[\t ]+(.+)$/m)?.[1].trim();
    if (!description || /^["'|>]/.test(description)) throw new Error(`${file}: expected a single-line plain description`);
    const body = source.slice(frontMatter[0].length).replace(/^(?:[\t ]*\r?\n)+/, '');
    const skill = path.join(skills, `source-command-${name}/SKILL.md`);
    const previous = existsSync(skill) ? readFileSync(skill, 'utf8') : null;
    let prefix;
    if (previous === null) {
      prefix = `---\nname: ${JSON.stringify(`source-command-${name}`)}\ndescription: ${JSON.stringify(description)}\n---\n\n# source-command-${name}\n\nUse this skill when the user asks to run the migrated source command \`${name}\`.\n\n## Command Template\n`;
    } else {
      const heading = previous.match(/^## Command Template(?:\r?\n|$)/m);
      if (!heading) throw new Error(`${skill}: missing ## Command Template`);
      prefix = previous.slice(0, heading.index + heading[0].length);
    }
    const next = `${prefix}${prefix.endsWith('\n') ? '' : '\n'}\n${body}`;
    if (next === previous) continue;
    mkdirSync(path.dirname(skill), { recursive: true });
    writeFileSync(skill, next);
    log(`SYNCED ${name}`);
  }
}

function selfTest() {
  const repoRoot = mkdtempSync(path.join(tmpdir(), 'sync-runner-copies-'));
  try {
    const commands = path.join(repoRoot, '.claude/commands');
    const skill = path.join(repoRoot, '.agents/skills/source-command-demo/SKILL.md');
    mkdirSync(commands, { recursive: true });
    mkdirSync(path.dirname(skill), { recursive: true });
    writeFileSync(path.join(commands, 'demo.md'), '---\ndescription: Run the demo.\n---\n\n \t\nRun the current demo.\n\n');
    writeFileSync(skill, 'Keep this prefix exactly.\r\n## Command Template\r\n\r\nOld demo.\n');
    const output = [];
    syncRunnerCopies(repoRoot, line => output.push(line));
    assert.equal(readFileSync(skill, 'utf8'), 'Keep this prefix exactly.\r\n## Command Template\r\n\nRun the current demo.\n\n', 'repaired drift preserves the prefix and command body');
    assert.deepEqual(output, ['SYNCED demo']);
    console.log('PASS repaired drift');

    const backdated = new Date('2000-01-01T00:00:00Z');
    utimesSync(skill, backdated, backdated);
    output.length = 0;
    syncRunnerCopies(repoRoot, line => output.push(line));
    assert.equal(statSync(skill).mtimeMs, backdated.getTime(), 'matching copy is not rewritten');
    assert.deepEqual(output, []);
    console.log('PASS matching copy not rewritten');

    writeFileSync(path.join(commands, 'new.md'), '---\ndescription: Run a new command.\n---\n\nDo the new thing.\n');
    syncRunnerCopies(repoRoot, line => output.push(line));
    assert.equal(readFileSync(path.join(repoRoot, '.agents/skills/source-command-new/SKILL.md'), 'utf8'), '---\nname: "source-command-new"\ndescription: "Run a new command."\n---\n\n# source-command-new\n\nUse this skill when the user asks to run the migrated source command `new`.\n\n## Command Template\n\nDo the new thing.\n', 'missing copy is created with the runner description');
    assert.deepEqual(output, ['SYNCED new']);
    console.log('PASS missing copy created');

    const malformed = '---\ndescription: Broken runner.\nNo closing front matter.\n';
    writeFileSync(path.join(commands, 'demo.md'), malformed);
    const preserved = readFileSync(skill, 'utf8');
    assert.throws(() => syncRunnerCopies(repoRoot), /missing or malformed front matter/);
    assert.equal(readFileSync(skill, 'utf8'), preserved);
    writeFileSync(path.join(commands, 'demo.md'), '---\ndescription: Valid runner.\n---\n\nNew body.\n');
    writeFileSync(skill, 'A prefix without its template heading.\n');
    assert.throws(() => syncRunnerCopies(repoRoot), /missing ## Command Template/);
    assert.equal(readFileSync(skill, 'utf8'), 'A prefix without its template heading.\n');
    console.log('PASS malformed input preserves copy');

    rmSync(path.join(repoRoot, '.agents'), { recursive: true });
    output.length = 0;
    syncRunnerCopies(repoRoot, line => output.push(line));
    assert.deepEqual(output, ['SKIP no .agents/skills'], 'missing skills directory is skipped');
    assert.equal(existsSync(path.join(repoRoot, '.agents')), false);
    console.log('PASS missing skills directory skipped');
  } finally {
    rmSync(repoRoot, { recursive: true, force: true });
  }
}

function main() {
  const args = process.argv.slice(2);
  if (args.length === 1 && args[0] === '--self-test') return selfTest();
  if (args.length) throw new Error('usage: node .claude/scripts/sync-runner-copies.mjs [--self-test]');
  syncRunnerCopies(root);
}

try { main(); } catch (error) {
  console.error(`ERROR ${error.message}`);
  process.exitCode = 2;
}
