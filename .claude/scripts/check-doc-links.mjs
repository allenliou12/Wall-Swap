#!/usr/bin/env node
import assert from 'node:assert/strict';
import { existsSync, lstatSync, readdirSync, readFileSync, realpathSync,
  mkdtempSync, mkdirSync, writeFileSync, unlinkSync, symlinkSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const SCAN_ROOTS = ['docs', '.claude', 'AGENTS.md', '.agents/skills/source-command-catchup',
  '.agents/skills/source-command-feature', '.agents/skills/source-command-handoff'];

const excluded = new Set(['.git', '.gitnexus', 'node_modules', '.next', 'dist', 'cache', 'caches', 'worktrees', '.worktrees']);
const docPath = String.raw`(?:[~./\w{}<>*@,…-]+/)*[\w{}<>*@,….-]+\.md(?:#[^\s\x60)>,;]+|:\d+(?:[-–]\d+)?)?`;
const slug = text => text.toLowerCase().replace(/<[^>]*>/g, '').replace(/[^\p{L}\p{N}_\-\s]/gu, '').replace(/\s/g, '-');

function codeSpans(text) {
  const runs = [...text.matchAll(/`+/g)];
  const spans = [];
  for (let at = 0; at < runs.length; at++) {
    const opening = runs[at];
    if ((/\\+$/.exec(text.slice(0, opening.index))?.[0].length ?? 0) % 2) continue;
    let end = at + 1;
    while (end < runs.length && runs[end][0].length !== opening[0].length) end++;
    if (end === runs.length) continue;
    const bodyAt = opening.index + opening[0].length;
    spans.push({ index: opening.index, end: runs[end].index + runs[end][0].length,
      bodyAt, content: text.slice(bodyAt, runs[end].index) });
    at = end;
  }
  return spans;
}

const plain = text => {
  const spans = codeSpans(text);
  for (let at = spans.length - 1; at >= 0; at--) text = text.slice(0, spans[at].index) + `\0${at}\0` + text.slice(spans[at].end);
  text = text.replace(/<[^>]*>/g, '');
  let previous;
  do {
    previous = text;
    text = text.replace(/(?<!\w)(\*{1,3}|_{1,3})(?=\S)(.+?)\1(?!\w)/g, (_, delimiter, emphasis) => emphasis);
  } while (text !== previous);
  return text.replace(/\0(\d+)\0/g, (_, at) => {
    let value = spans[at].content.replace(/\r\n|\r|\n/g, ' ');
    if (value.startsWith(' ') && value.endsWith(' ') && /[^ ]/.test(value)) value = value.slice(1, -1);
    return value;
  }).trim();
};

function anchors(text) {
  const result = new Set();
  const headings = [];
  const duplicates = new Map();
  const unfenced = text.replace(/^[ \t]*(`{3,}|~{3,})[^\n]*\n[\s\S]*?^[ \t]*\1[^\n]*$/gm, '');
  const titles = [...unfenced.matchAll(/^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$/gm),
    ...unfenced.matchAll(/^ {0,3}([^\n]+)\n {0,3}(?:=+|-+)\s*$/gm)].sort((a, b) => a.index - b.index);
  for (const match of titles) {
    const heading = plain(match[1]);
    headings.push(heading);
    const base = slug(heading);
    let id = base;
    let duplicate = duplicates.get(base) ?? 0;
    while (result.has(id)) id = `${base}-${++duplicate}`;
    duplicates.set(base, duplicate);
    result.add(id);
  }
  for (const match of unfenced.matchAll(/<(?:a|[a-z][\w-]*)\b[^>]*\b(?:id|name)=["']([^"']+)["'][^>]*>/gi)) result.add(match[1]);
  return { ids: result, headings, lines: text.length ? text.split('\n').length - Number(text.endsWith('\n')) : 0 };
}

function references(text) {
  const refs = [];
  const occupied = [];
  const spans = codeSpans(text);
  const add = (at, end, target, form, section) => {
    refs.push({ at, end, target, form, section });
    occupied.push([at, end]);
  };
  // Labels may wrap or nest; destinations may contain balanced parentheses.
  for (let at = 0; at < text.length; at++) {
    if (text[at] === '\\') { at++; continue; }
    if (text[at] !== '[' || spans.some(span => at >= span.index && at < span.end)) continue;
    let end = at + 1;
    let depth = 1;
    for (; end < text.length && depth; end++) {
      const span = spans.find(span => span.index === end);
      if (span) end = span.end - 1;
      else if (text[end] === '\\') end++;
      else if (text[end] === '[') depth++;
      else if (text[end] === ']') depth--;
    }
    if (depth || text[end] !== '(') continue;
    const start = ++end;
    depth = 1;
    let angle = false, quote = '';
    for (; end < text.length && depth; end++) {
      if (text[end] === '\\') end++;
      else if (angle) { if (text[end] === '>') angle = false; }
      else if (quote) { if (text[end] === quote) quote = ''; }
      else if (text[end] === '<' && !text.slice(start, end).trim()) angle = true;
      else if ((text[end] === '"' || text[end] === "'") && /\s/.test(text[end - 1])) quote = text[end];
      else if (text[end] === '(') depth++;
      else if (text[end] === ')') depth--;
    }
    if (depth) continue;
    const destination = text.slice(start, end - 1).trim();
    const target = destination.startsWith('<') ? destination.slice(1, destination.indexOf('>')) : destination.split(/\s+["']/)[0].trim();
    add(at, end, target.replace(/\\([()])/g, '$1'), 'markdown');
    at = end - 1;
  }
  for (const match of text.matchAll(/^ {0,3}\[([^\]\n]+)\]:\s*(<[^>]+>|\S+)/gm)) {
    add(match.index, match.index + match[0].length, match[2].replace(/^<|>$/g, ''), 'reference-definition');
  }
  // Undefined bracket pairs are literal Markdown (including research evidence tags), not links.
  for (const match of text.matchAll(new RegExp('(`?)(' + docPath + ')\\1\\s*§\\s*', 'g'))) {
    if (occupied.some(([start, end]) => match.index >= start && match.index < end)) continue;
    const section = text.slice(match.index + match[0].length).split(/[\n|]/)[0].trim();
    add(match.index, match.index + match[0].length, match[2], 'section', section);
  }
  for (const span of spans) {
    for (const match of span.content.matchAll(new RegExp(docPath, 'g'))) {
      const at = span.bodyAt + match.index;
      if (!occupied.some(([start, end]) => at >= start && at < end)) add(at, at + match[0].length, match[0], 'bare-path');
    }
  }
  return refs;
}

const skipKinds = ['other-repo', 'external', 'future-home'];

// markdown-link-check style: <!-- link-check-disable-line|disable-next-line|disable: <kind> — <reason> --> and
// <!-- link-check-enable -->. Anything malformed fails closed; markers inside fenced or inline code are literal text.
function markers(text, fences) {
  const code = [...fences, ...codeSpans(text).map(span => [span.index, span.end])];
  const lines = new Map(), blocks = [], problems = [];
  let open;
  for (const match of text.matchAll(/<!--[ \t]*link-check-/g)) {
    const at = match.index;
    if (code.some(([start, end]) => at >= start && at < end)) continue;
    const line = text.slice(0, at).split('\n').length;
    const rest = text.slice(at).split('\n')[0];
    const close = rest.indexOf('-->');
    const body = close < 0 ? rest : rest.slice(4, close).trim();
    const parsed = close < 0 ? null : /^link-check-(disable-line|disable-next-line|disable|enable)(?::\s*(.*))?$/.exec(body);
    const payload = parsed?.[2] === undefined ? null : /^(\S+)\s+—\s+(\S.*)$/.exec(parsed[2]);
    const problem = (kind, detail = '') => problems.push({ line, kind, target: body, detail });
    if (!parsed || (parsed[1] === 'enable') !== (parsed[2] === undefined) || parsed[1] !== 'enable' && !payload ||
        payload && !skipKinds.includes(payload[1])) {
      problem('invalid-link-check-marker', `expected link-check-disable-line|disable-next-line|disable: <${skipKinds.join('|')}> — <reason>, or link-check-enable, closed on the same line`);
      continue;
    }
    const skip = payload && { kind: payload[1], reason: payload[2].trim() };
    if (parsed[1] === 'disable-line') lines.set(line, skip);
    else if (parsed[1] === 'disable-next-line') lines.set(line + 1, skip);
    else if (parsed[1] === 'disable') { if (open) problem('nested-link-check-disable'); else open = { ...skip, start: at + close + 3, line, body }; }
    else if (!open) problem('unmatched-link-check-enable');
    else { blocks.push({ ...open, end: at }); open = undefined; }
  }
  if (open) problems.push({ line: open.line, kind: 'unterminated-link-check-disable', target: open.body, detail: 'no matching link-check-enable' });
  return { lines, blocks, problems };
}

export function scan(root, roots) {
  root = realpathSync(root);
  const result = { errors: [], checked: 0, files: 0, forms: {}, anchorsChecked: 0, linesChecked: 0, sectionsChecked: 0, skips: [], unchecked: [] };
  const files = [], aliases = [];
  const inside = target => target === root || target.startsWith(root + path.sep);
  const record = (list, source, line, kind, target, detail = '') => result[list].push({ source, line, kind, target, detail });
  function walk(target) {
    if (!existsSync(target)) {
      record('errors', path.relative(root, target), 1, 'missing-scan-root', target);
      return;
    }
    const relative = path.relative(root, target);
    const stat = lstatSync(target);
    if (stat.isSymbolicLink()) {
      if (!inside(realpathSync(target))) record('errors', relative, 1, 'outside-repo-alias', target);
      else {
        record('skips', relative, 1, 'in-repo-alias', target, 'target checked through references; not counted twice');
        if (target.endsWith('.md')) aliases.push(target);
      }
    } else if (stat.isDirectory()) {
      if (excluded.has(path.basename(target))) record('skips', relative, 1, 'excluded-surface', target, 'cache/worktree/generated surface');
      else for (const name of readdirSync(target).sort()) walk(path.join(target, name));
    } else if (target.endsWith('.md')) files.push(target);
  }
  for (const entry of roots) walk(path.resolve(root, entry));
  const basenames = new Map();
  for (const file of [...files, ...readdirSync(root).filter(p => p.endsWith('.md')).map(p => path.join(root, p))]) {
    const name = path.basename(file);
    const matches = basenames.get(name) ?? new Set();
    matches.add(file);
    basenames.set(name, matches);
  }
  // Filter before adding so duplicate alias names remain ambiguous without a regular file.
  for (const alias of aliases.filter(file => !basenames.has(path.basename(file)))) {
    const name = path.basename(alias);
    const matches = basenames.get(name) ?? new Set();
    matches.add(alias);
    basenames.set(name, matches);
  }
  const cache = new Map();
  for (const source of files) {
    const text = readFileSync(source, 'utf8');
    const sourceName = path.relative(root, source);
    result.files++;
    const fences = [...text.matchAll(/^[ \t]*(`{3,}|~{3,})[^\n]*\n[\s\S]*?^[ \t]*\1[^\n]*$/gm)].map(m => [m.index, m.index + m[0].length]);
    // ponytail: markers are literal syntax; add negation handling if documents need it.
    const scratchpadGroups = [...text.matchAll(/\bscratchpad only\s*(?:\(`[\w.-]+\.md`(?:\s*,\s*`[\w.-]+\.md`)*\)|`[\w.-]+\.md`)/g)]
      .map(m => [m.index, m.index + m[0].length]);
    const marked = markers(text, fences);
    for (const problem of marked.problems) record('errors', sourceName, problem.line, problem.kind, problem.target, problem.detail);
    const refs = references(text);
    for (const ref of refs) {
      result.forms[ref.form] = (result.forms[ref.form] ?? 0) + 1;
      const line = text.slice(0, ref.at).split('\n').length;
      const skip = (kind, detail) => record('skips', sourceName, line, kind, ref.target, detail);
      const error = (kind, detail) => record('errors', sourceName, line, kind, ref.target, detail);
      const context = text.slice(Math.max(0, text.lastIndexOf('\n\n', ref.at)), text.indexOf('\n\n', ref.at) < 0 ? text.length : text.indexOf('\n\n', ref.at));
      if (fences.some(([start, end]) => ref.at >= start && ref.at < end)) { skip('fenced-example'); continue; }
      if (/^(?:[a-z][\w+.-]*:|\/\/)/i.test(ref.target) && !/^[^/:]+\.md:\d+(?:[-–]\d+)?$/i.test(ref.target)) { skip('external'); continue; }
      if (/^(?:~\/|\/(?:Users|private|tmp|Applications|opt|home|var)\/|[A-Z]:\\)/.test(ref.target)) { skip('absolute-machine-path'); continue; }
      if (/[*{},<>…]|\.\.\./.test(ref.target)) { skip(/[*]/.test(ref.target) ? 'glob' : 'template'); continue; }
      if (ref.target.startsWith('/') && !/\.[a-z0-9]+(?:#|$)/i.test(ref.target)) { skip('web-route', 'absolute application route'); continue; }
      if (ref.target.startsWith('@')) { skip('inline-example', 'Claude import shown as an example'); continue; }
      if (/^(?:feedback_|project_|MEMORY\.md)/.test(ref.target) && /memory/i.test(context)) { skip('absolute-machine-path', 'explicit auto-memory shorthand; outside repository'); continue; }
      if (ref.form === 'bare-path' && !ref.target.includes('/') && !basenames.has(ref.target) &&
        scratchpadGroups.some(([start, end]) => ref.at >= start && ref.end <= end)) { skip('transient-example', 'explicit attached scratchpad-only filename'); continue; }
      const marker = marked.lines.get(line) ?? marked.blocks.find(block => ref.at >= block.start && ref.at < block.end);
      const separator = ref.target.indexOf('#');
      let rawPath, fragment;
      try {
        rawPath = decodeURIComponent(separator < 0 ? ref.target : ref.target.slice(0, separator));
        fragment = separator < 0 ? undefined : decodeURIComponent(ref.target.slice(separator + 1));
      } catch {
        if (marker) skip(marker.kind, marker.reason);
        else error('invalid-target-encoding');
        continue;
      }
      const localPath = rawPath.replace(/:\d+(?:[-–]\d+)?$/, '');
      const repoRelative = /^(?:docs|\.claude|\.agents|tests)\//.test(localPath) || localPath.startsWith('/') ||
        !['markdown', 'reference-definition'].includes(ref.form) && localPath.includes('/') && !localPath.startsWith('.') && existsSync(path.join(root, localPath.split('/')[0]));
      let target = !localPath ? source : path.resolve(repoRelative ? root : path.dirname(source), localPath.replace(/^\//, ''));
      if (!existsSync(target) && ref.form !== 'markdown' && ref.form !== 'reference-definition' && !localPath.includes('/')) {
        const matches = [...(basenames.get(localPath) ?? [])];
        if (matches.length > 1) { record('unchecked', sourceName, line, 'ambiguous-basename', ref.target, matches.map(p => path.relative(root, p)).join(', ')); continue; }
        if (matches.length === 1) target = matches[0];
      }
      if (!inside(target)) {
        if (marker) skip(marker.kind, marker.reason);
        else error('outside-repo-target');
        continue;
      }
      if (!existsSync(target)) {
        if (marker) skip(marker.kind, marker.reason);
        else error('missing-target');
        continue;
      }
      if (!inside(realpathSync(target))) { error('outside-repo-alias'); continue; }
      result.checked++;
      if (fragment || ref.section) {
        if (!cache.has(target)) cache.set(target, anchors(readFileSync(target, 'utf8')));
        const info = cache.get(target);
        if (fragment) {
          const locator = /^L(\d+)(?:-L?(\d+))?$/.exec(fragment);
          if (locator) {
            const from = Number(locator[1]), to = Number(locator[2] ?? locator[1]);
            if (from < 1 || to < from || to > info.lines) error('invalid-line-fragment', `${info.lines} lines`);
            else result.linesChecked++;
          } else if (!target.endsWith('.md')) record('unchecked', sourceName, line, 'non-markdown-anchor', ref.target);
          else if (!info.ids.has(fragment)) error('missing-anchor');
          else result.anchorsChecked++;
        }
        if (ref.section) {
          const section = plain(ref.section).replace(/^["“]/, '').split(/[(),;:+"”]|\s+[—–]|\.\s/)[0].trim().replace(/\.$/, '');
          const number = /^(\d+[a-z]?(?:\.\d+)*)(?=[^\w]|$)/i.exec(section)?.[1];
          const query = section;
          const matches = info.headings.filter(h => {
            if (number) return new RegExp('^' + number.replaceAll('.', '\\.') + '(?:\\.?(?:\\s|$))', 'i').test(h);
            const heading = h.replace(/^\d+[a-z]?(?:\.\d+)*[.)]?\s+/i, '').split(/\s+[—–(]/)[0].toLowerCase();
            return heading === query.toLowerCase() || heading.startsWith(query.toLowerCase() + ' ');
          });
          if (/^\d.*(?:§|[–/])/.test(section)) matches.length = 0;
          if (matches.length !== 1) record('unchecked', sourceName, line, 'human-section', ref.target, ref.section);
          else result.sectionsChecked++;
        }
      }
    }
  }
  return result;
}

function selfTest() {
  const root = mkdtempSync(path.join(tmpdir(), 'wallswap-doc-links-'));
  try {
    mkdirSync(path.join(root, 'docs'));
    const target = path.join(root, 'docs/target.md');
    const body = '# Target\n\n## Kept heading\n\n## Duplicate\n\n## Duplicate\n\n## 2. Numbered heading\n\n<a id="named"></a>\n';
    writeFileSync(target, body);
    writeFileSync(path.join(root, 'docs/target.txt'), 'first\nsecond\n');
    writeFileSync(path.join(root, 'docs/start.md'), [
      '# Start',
      '[relative](target.md#kept-heading)',
      '[root](docs/target.md#kept-heading)',
      '![image](target.md#named)',
      '[reference][target]',
      '[target]: target.md#duplicate-1',
      '`docs/target.md` § Kept heading',
      'target.md §',
      '  Kept heading',
      '`target.md`',
      '`target.md` § "Numbered heading". Follow-up prose.',
      '[line](target.md#L1-L3)',
      '[text line](target.txt#L1-L2)',
    ].join('\n'));
    const valid = scan(root, ['docs']);
    assert.deepEqual(valid.errors, [], 'existing targets and heading forms pass');
    assert.deepEqual(valid.unchecked, [], 'multiline and numbered heading prefixes checked');
    assert.ok(valid.checked >= 8, 'relative/root/basename/multiline/reference forms checked');
    unlinkSync(target);
    assert.ok(scan(root, ['docs']).errors.some(e => e.kind === 'missing-target'), 'removed target detected');
    writeFileSync(target, body.replaceAll('## Kept heading', '## Removed heading'));
    assert.ok(scan(root, ['docs']).errors.some(e => e.kind === 'missing-anchor'), 'removed heading detected');
    writeFileSync(target, body);
    writeFileSync(path.join(root, 'docs/start.md'), '[bad line](target.txt#L3)');
    assert.ok(scan(root, ['docs']).errors.some(e => e.kind === 'invalid-line-fragment'), 'line range excludes trailing newline');
    writeFileSync(target, '## foo_bar\n\n## `code_value`\n');
    writeFileSync(path.join(root, 'docs/start.md'), '[literal](target.md#foo_bar)\n[code](target.md#code_value)');
    assert.deepEqual(scan(root, ['docs']).errors, [], 'literal/code underscore anchors retained');
    writeFileSync(path.join(root, 'docs/start.md'), '[invalid](target.md#foobar)');
    assert.ok(scan(root, ['docs']).errors.some(e => e.kind === 'missing-anchor'), 'removed underscore anchor refused');
    writeFileSync(target, '## **Outer _inner_ words**\n\n## **Outer `_code_value_` words**\n');
    writeFileSync(path.join(root, 'docs/start.md'), '[nested](target.md#outer-inner-words)\n[protected code](target.md#outer-_code_value_-words)');
    assert.deepEqual(scan(root, ['docs']).errors, [], 'nested emphasis unwraps while code underscores remain literal');
    writeFileSync(path.join(root, 'docs/start.md'), '[bogus](target.md#outer-_inner_-words)');
    assert.ok(scan(root, ['docs']).errors.some(e => e.kind === 'missing-anchor'), 'nested emphasis delimiters cannot become anchors');
    writeFileSync(target, '## Outer `` code `` words\n\n## **Outer `` _code_value_ `tick` `` words**\n');
    writeFileSync(path.join(root, 'docs/start.md'), '[padded](target.md#outer-code-words)\n[literal code](target.md#outer-_code_value_-tick-words)');
    assert.deepEqual(scan(root, ['docs']).errors, [], 'code span padding normalizes without stripping literal code');
    writeFileSync(path.join(root, 'docs/start.md'), '[bogus padding](target.md#outer--code--words)');
    assert.ok(scan(root, ['docs']).errors.some(e => e.kind === 'missing-anchor'), 'code padding cannot introduce extra anchor hyphens');
    assert.equal(plain('Outer `` first\r\nsecond\rthird\nfourth `` words'), 'Outer first second third fourth words', 'code line endings become spaces');
    assert.equal(plain('Outer ``   `` words'), 'Outer     words', 'all-space code content keeps its padding');
    assert.equal(plain('Outer ``  code  `` words'), 'Outer  code  words', 'code strips exactly one surrounding space');
    assert.equal(plain('Outer `` code`` words'), 'Outer  code words', 'one-sided code padding remains literal');
    assert.equal(plain('Outer `` \t `` words'), 'Outer \t words', 'tabs are not all-space code content');
    writeFileSync(path.join(root, 'docs/start.md'), [
      '[missing\ncontract](missing.md)', '[[[missing]]](missing.md)',
      '[escaped \\] label](missing.md)', '\\[literal](not-a-link.md)',
    ].join('\n'));
    assert.equal(scan(root, ['docs']).errors.filter(e => e.kind === 'missing-target').length, 3,
      'multiline/nested/escaped labels checked; escaped opening ignored');
    writeFileSync(path.join(root, 'docs/start.md'), [
      '[label `]` text](missing.md)', '[link](<missing(.md>)',
      '[link](missing.md "example (title")',
    ].join('\n'));
    assert.deepEqual(scan(root, ['docs']).errors.filter(e => e.kind === 'missing-target').map(e => e.target),
      ['missing.md', 'missing(.md', 'missing.md'], 'code labels, angle destinations and quoted titles remain navigation');
    writeFileSync(path.join(root, 'docs/start.md'), '[label `` `]` `` text](missing.md)');
    const tickRuns = scan(root, ['docs/start.md']);
    assert.ok(tickRuns.errors.some(e => e.kind === 'missing-target' && e.target === 'missing.md'),
      'equal backtick runs keep internal shorter runs literal in labels');
    assert.equal(tickRuns.forms.markdown, 1, 'complete code span leaves enclosing link checked');
    writeFileSync(target, '## Existing\n');
    writeFileSync(path.join(root, 'docs/file#name.md'), '## Existing\n');
    writeFileSync(path.join(root, 'docs/start.md'), [
      '[suffix](target.md#existing#missing)', '[encoded filename](file%23name.md#existing)',
      '[encoded suffix](target.md#existing%23missing)',
    ].join('\n'));
    const fragments = scan(root, ['docs']);
    assert.equal(fragments.errors.filter(e => e.kind === 'missing-anchor').length, 2, 'full fragment suffix checked');
    assert.ok(!fragments.errors.some(e => e.kind === 'missing-target'), 'encoded filename hash remains in path');
    writeFileSync(path.join(root, 'docs/start.md'), '[Required standard](missing.md). This gate must not rely on scratchpad; only canonical docs count.');
    assert.ok(scan(root, ['docs']).errors.some(e => e.kind === 'missing-target'), 'scratchpad prose cannot hide Markdown navigation');
    writeFileSync(path.join(root, 'docs/start.md'), '`required.md` is mandatory. This gate must not rely on scratchpad; only canonical docs count.');
    assert.ok(scan(root, ['docs']).errors.some(e => e.kind === 'missing-target' && e.target === 'required.md'),
      'mandatory bare navigation cannot inherit scratchpad context');
    writeFileSync(path.join(root, 'docs/start.md'), 'PM brief lives in the session scratchpad only (`pm-brief.md`, `pm-brief-detailed.md`) — copy out or regenerate from the research docs.');
    const scratchExamples = scan(root, ['docs/start.md']);
    assert.deepEqual(scratchExamples.errors, [], 'explicit scratchpad-only citations remain examples');
    assert.equal(scratchExamples.skips.filter(e => e.kind === 'transient-example').length, 2, 'scratchpad evidence attaches to each citation');
    for (const separator of [', and ', ' and ']) {
      writeFileSync(path.join(root, 'docs/start.md'), 'Use `contract.md` as the canonical reference' + separator + 'scratchpad only examples are temporary files.');
      assert.ok(scan(root, ['docs/start.md']).errors.some(e => e.kind === 'missing-target' && e.target === 'contract.md'),
        'unattached scratchpad prose never waives canonical citation');
    }
    writeFileSync(path.join(root, 'docs/start.md'), 'scratchpad only (`scratch.md`, but the canonical reference is `contract.md`).');
    assert.deepEqual(scan(root, ['docs/start.md']).errors.filter(e => e.kind === 'missing-target').map(e => e.target),
      ['scratch.md', 'contract.md'], 'scratchpad group accepts code filenames and commas only');
    writeFileSync(path.join(root, 'docs/start.md'), 'scratchpad only `scratch.md`; the canonical reference is `contract.md`.');
    const singleScratch = scan(root, ['docs/start.md']);
    assert.ok(singleScratch.skips.some(e => e.kind === 'transient-example' && e.target === 'scratch.md'), 'directly attached single code filename is explicit');
    assert.ok(singleScratch.errors.some(e => e.kind === 'missing-target' && e.target === 'contract.md'), 'attached single example does not waive another citation');
    for (const separator of ['; ', ' and ']) {
      writeFileSync(path.join(root, 'docs/start.md'), 'Use `scratch.md` as a temporary file' + separator + 'the canonical reference is `contract.md`.');
      const clauses = scan(root, ['docs/start.md']);
      assert.ok(clauses.errors.some(e => e.kind === 'missing-target' && e.target === 'contract.md'),
        'unrelated canonical citation cannot inherit transient evidence');
      assert.ok(clauses.errors.some(e => e.kind === 'missing-target' && e.target === 'scratch.md'),
        'temporary-file prose lacks explicit attached scratch syntax');
    }
    writeFileSync(path.join(root, 'docs/start.md'), 'Use `contract.md` as the canonical reference; scratchpad only examples are temporary files.');
    assert.ok(scan(root, ['docs/start.md']).errors.some(e => e.kind === 'missing-target' && e.target === 'contract.md'),
      'another clause cannot supply transient evidence to canonical navigation');
    writeFileSync(path.join(root, 'docs/start.md'), 'PM brief (short + detailed) lives in\nthe session scratchpad only (`pm-brief.md`, `pm-brief-detailed.md`) — copy out or regenerate from the research docs.');
    const grouped = scan(root, ['docs/start.md']);
    assert.deepEqual(grouped.errors, [], 'wrapped production scratchpad group remains classified');
    assert.equal(grouped.skips.filter(e => e.kind === 'transient-example').length, 2, 'both production group citations retain transient evidence');
    const errorsOf = result => result.errors.map(e => `${e.line} ${e.kind} ${e.target}`);
    writeFileSync(path.join(root, 'docs/start.md'), '`missing-a.md` <!-- link-check-disable-line: other-repo — fixture upstream path -->\n`missing-b.md`\n');
    const sameLine = scan(root, ['docs/start.md']);
    assert.ok(sameLine.skips.some(e => e.line === 1 && e.kind === 'other-repo' && e.target === 'missing-a.md' && e.detail === 'fixture upstream path'),
      'disable-line skips its own line and prints kind + reason');
    assert.deepEqual(errorsOf(sameLine), ['2 missing-target missing-b.md'], 'disable-line does not reach the next line');
    writeFileSync(path.join(root, 'docs/start.md'), '<!-- link-check-disable-next-line: future-home — created on first promotion -->\n`missing-a.md`\n`missing-b.md`\n');
    const nextLine = scan(root, ['docs/start.md']);
    assert.ok(nextLine.skips.some(e => e.line === 2 && e.kind === 'future-home' && e.detail === 'created on first promotion'), 'disable-next-line skips the next line');
    assert.deepEqual(errorsOf(nextLine), ['3 missing-target missing-b.md'], 'disable-next-line covers one line only');
    writeFileSync(path.join(root, 'docs/start.md'), [
      '<!-- link-check-disable: external — another product\'s docs -->', '`missing-a.md`', '', '`missing-b.md`',
      '<!-- link-check-enable -->', '`missing-c.md`',
    ].join('\n'));
    const block = scan(root, ['docs/start.md']);
    assert.equal(block.skips.filter(e => e.kind === 'external' && e.detail === 'another product\'s docs').length, 2, 'block skips every line until enable');
    assert.deepEqual(errorsOf(block), ['6 missing-target missing-c.md'], 'block ends at enable');
    for (const [body, kind] of [
      ['<!-- link-check-disable: other-repo — never closed -->\n`missing-a.md`', 'unterminated-link-check-disable'],
      ['<!-- link-check-disable-line: elsewhere — unknown kind --> `missing-a.md`', 'invalid-link-check-marker'],
      ['<!-- link-check-disable-line: other-repo --> `missing-a.md`', 'invalid-link-check-marker'],
      ['<!-- link-check-disable-line: other-repo — no close `missing-a.md`', 'invalid-link-check-marker'],
      ['<!-- link-check-enable -->', 'unmatched-link-check-enable'],
      ['<!-- link-check-disabled-line: other-repo — typo --> `missing-a.md`', 'invalid-link-check-marker'],
    ]) {
      writeFileSync(path.join(root, 'docs/start.md'), body);
      const invalid = scan(root, ['docs/start.md']);
      assert.ok(invalid.errors.some(e => e.line === 1 && e.kind === kind), `fail closed: ${kind} for ${JSON.stringify(body)}`);
      assert.ok(!invalid.skips.some(e => e.target === 'missing-a.md'), `invalid marker skips nothing: ${JSON.stringify(body)}`);
    }
    writeFileSync(path.join(root, 'docs/start.md'), '<!-- link-check-disable: other-repo — first -->\n<!-- link-check-disable: other-repo — second -->\n<!-- link-check-enable -->\n');
    assert.ok(scan(root, ['docs/start.md']).errors.some(e => e.line === 2 && e.kind === 'nested-link-check-disable'), 'fail closed: nested disable');
    writeFileSync(path.join(root, 'docs/start.md'), '```\n<!-- link-check-disable: other-repo — example -->\n```\nShown inline: `<!-- link-check-disable: other-repo — example -->`.\n`missing-a.md`\n');
    assert.deepEqual(errorsOf(scan(root, ['docs/start.md'])), ['5 missing-target missing-a.md'], 'markers inside fenced or inline code are ignored');
    writeFileSync(path.join(root, 'AGENTS.md'), '3. Standards: `event-conventions.md` holds event conventions.\n7. Contracts are created on first promotion.\n');
    assert.ok(scan(root, ['AGENTS.md']).errors.some(e => e.kind === 'missing-target' && e.target === 'event-conventions.md'),
      'paragraph prose never hides a missing bare reference');
    unlinkSync(path.join(root, 'AGENTS.md'));
    mkdirSync(path.join(root, 'docs/research'));
    writeFileSync(path.join(root, 'docs/research/2026-09-07-everything-card-data-sources.md'), [
      '# Research', '`docs/ONBOARDING.md` <!-- link-check-disable-line: other-repo — upstream repo path -->', '## 8. What this changes in `docs/rnd/plan.md`',
    ].join('\n'));
    const research = scan(root, ['docs']);
    assert.ok(research.errors.some(e => e.target === 'docs/rnd/plan.md' && e.kind === 'missing-target'), 'reference-repo document checks local section navigation');
    assert.ok(research.skips.some(e => e.target === 'docs/ONBOARDING.md' && e.kind === 'other-repo'), 'marked upstream path remains classified');
    mkdirSync(path.join(root, 'docs/rnd'));
    writeFileSync(path.join(root, 'docs/rnd/plan.md'), '## Existing\n');
    writeFileSync(path.join(root, 'docs/research/2026-09-07-everything-card-data-sources.md'), [
      '[local](../rnd/plan.md#missing-line) [upstream](../upstream.md) <!-- link-check-disable-line: other-repo — upstream path -->',
      '<!-- link-check-disable: external — upstream documentation -->',
      '[local](../rnd/plan.md#missing-block) [upstream](../upstream.md)',
      '<!-- link-check-enable -->',
      '[future](../future.md) <!-- link-check-disable-line: future-home — created on first promotion -->',
    ].join('\n'));
    const markedLocal = scan(root, ['docs/research']);
    assert.deepEqual(errorsOf(markedLocal), [
      '1 missing-anchor ../rnd/plan.md#missing-line', '3 missing-anchor ../rnd/plan.md#missing-block',
    ], 'line and block markers cannot hide broken anchors in existing local targets');
    assert.deepEqual(markedLocal.skips.map(e => [e.kind, e.target]), [
      ['other-repo', '../upstream.md'], ['external', '../upstream.md'], ['future-home', '../future.md'],
    ], 'markers retain missing upstream and future-home exemptions');
    mkdirSync(path.join(root, 'repo/docs'), { recursive: true });
    mkdirSync(path.join(root, 'sibling'));
    writeFileSync(path.join(root, 'sibling/UP.md'), '## Upstream\n');
    writeFileSync(path.join(root, 'repo/docs/start.md'), [
      '[marked sibling](../../sibling/UP.md) <!-- link-check-disable-line: other-repo — sibling repository -->',
      '[marked missing sibling](../../sibling/missing.md) <!-- link-check-disable-line: other-repo — sibling repository -->',
      '[marked encoding](bad%encoding.md) <!-- link-check-disable-line: external — upstream documentation -->',
      '[sibling](../../sibling/UP.md)',
      '[missing sibling](../../sibling/missing.md)',
      '[encoding](bad%encoding.md)',
    ].join('\n'));
    const markedRemote = scan(path.join(root, 'repo'), ['docs']);
    assert.deepEqual(errorsOf(markedRemote), [
      '4 outside-repo-target ../../sibling/UP.md', '5 outside-repo-target ../../sibling/missing.md',
      '6 invalid-target-encoding bad%encoding.md',
    ], 'markers exempt outside-repo and malformed targets while unmarked failures remain errors');
    assert.deepEqual(markedRemote.skips.map(e => [e.kind, e.target]), [
      ['other-repo', '../../sibling/UP.md'], ['other-repo', '../../sibling/missing.md'], ['external', 'bad%encoding.md'],
    ], 'marked remote targets retain their exemption kind');
    writeFileSync(path.join(root, 'docs/start.md'), '`target.md` § Existing nonexistent subsection');
    const subsection = scan(root, ['docs/start.md']);
    assert.ok(subsection.unchecked.some(e => e.kind === 'human-section'), 'invented subsection remains unchecked');
    assert.equal(subsection.sectionsChecked, 0, 'invented subsection adds no section proof');
    writeFileSync(path.join(root, 'docs/start.md'), '[external](https://example.com:443)\n[local line](target.md:1)');
    const ports = scan(root, ['docs/start.md']);
    assert.deepEqual(ports.errors, [], 'URL port is external; .md:line stays local');
    assert.ok(ports.skips.some(e => e.kind === 'external' && e.target === 'https://example.com:443'), 'URL port classified external');
    assert.equal(ports.checked, 1, 'local .md:line citation checked');
    mkdirSync(path.join(root, 'docs/sub'));
    mkdirSync(path.join(root, 'docs/citations'));
    writeFileSync(path.join(root, 'docs/new-name.md'), '# Renamed\n');
    symlinkSync('../new-name.md', path.join(root, 'docs/sub/old-name.md'));
    writeFileSync(path.join(root, 'docs/citations/start.md'), '`old-name.md`');
    const aliasRoots = ['docs/new-name.md', 'docs/sub', 'docs/citations'];
    const bareAlias = scan(root, aliasRoots);
    assert.deepEqual(bareAlias.errors, [], 'bare alias name resolves from another folder');
    assert.deepEqual(bareAlias.unchecked, [], 'unique bare alias is checked');
    assert.equal(bareAlias.checked, 1, 'bare alias reference adds checked proof');
    assert.equal(bareAlias.files, 2, 'alias is not counted as another file');
    assert.deepEqual(bareAlias.skips, [{ source: 'docs/sub/old-name.md', line: 1, kind: 'in-repo-alias',
      target: path.join(realpathSync(root), 'docs/sub/old-name.md'), detail: 'target checked through references; not counted twice' }],
    'alias retains its existing skip record');
    symlinkSync('../new-name.md', path.join(root, 'docs/sub/new-name.md'));
    writeFileSync(path.join(root, 'docs/citations/start.md'), '`old-name.md`\n`new-name.md`');
    const regularWins = scan(root, aliasRoots);
    assert.deepEqual(regularWins.errors, [], 'regular file and same-name alias resolve');
    assert.deepEqual(regularWins.unchecked, [], 'same-name alias cannot make regular file ambiguous');
    assert.equal(regularWins.checked, 2, 'regular and alias bare names both checked');
    writeFileSync(path.join(root, 'docs/citations/start.md'), '`no-such-name.md`');
    assert.deepEqual(errorsOf(scan(root, aliasRoots)), ['1 missing-target no-such-name.md'], 'unknown bare name remains missing');
    mkdirSync(path.join(root, 'docs/other'));
    symlinkSync('../new-name.md', path.join(root, 'docs/other/old-name.md'));
    writeFileSync(path.join(root, 'docs/citations/start.md'), '`old-name.md`');
    const duplicateAliases = scan(root, [...aliasRoots, 'docs/other']);
    assert.deepEqual(duplicateAliases.errors, [], 'duplicate aliases remain unchecked rather than missing');
    assert.deepEqual(duplicateAliases.unchecked.map(e => [e.kind, e.target, e.detail]), [
      ['ambiguous-basename', 'old-name.md', 'docs/sub/old-name.md, docs/other/old-name.md'],
    ], 'all aliases participate when no regular file has their basename');
    assert.equal(duplicateAliases.checked, 0, 'ambiguous aliases add no checked proof');
    symlinkSync(fileURLToPath(import.meta.url), path.join(root, 'docs/outside.md'));
    assert.ok(scan(root, ['docs']).errors.some(e => e.kind === 'outside-repo-alias'), 'outside-repo symlink rejected');
    console.log('SELF-TEST PASS: reference forms; removed target; removed heading; line range; alias bare names; outside-repo alias');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--self-test')) selfTest();
  else {
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
    const result = scan(root, SCAN_ROOTS);
    for (const category of ['errors', 'unchecked', 'skips']) {
      for (const item of result[category]) console.log(`${category.toUpperCase()} ${item.source}:${item.line} ${item.kind} ${item.target}${item.detail ? ' — ' + item.detail : ''}`);
    }
    console.log(`SUMMARY files=${result.files} checked=${result.checked} errors=${result.errors.length} unchecked=${result.unchecked.length} skips=${result.skips.length}`);
    console.log(`FORMS ${Object.entries(result.forms).map(([form, count]) => `${form}=${count}`).join(' ')}; anchors=${result.anchorsChecked} lines=${result.linesChecked} sections=${result.sectionsChecked}`);
    console.log('COVERAGE: inline links/images, reference definitions, concrete backtick doc paths, plain/multiline path § sections; human sections are unchecked when no unique heading matches. No external fetches.');
    console.log('EXCLUDED SURFACES: cache/worktree/generated directories; .agents except the three source-command copies; application docs outside the scan roots.');
    process.exitCode = result.errors.length ? 1 : 0;
  }
}
