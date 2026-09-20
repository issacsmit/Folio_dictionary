import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, readdirSync, statSync} from 'node:fs';
import path from 'node:path';
import {GITHUB_API_LATEST, GITHUB_RELEASES_PAGE} from '../lib/update-check.js';

const ROOT = path.resolve('.');
const MANIFEST_PATH = path.join(ROOT, 'manifest.json');
const PACKAGE_PATH = path.join(ROOT, 'package.json');
const OPTIONS_PATH = path.join(ROOT, 'options.html');
const OPTIONS_JS_PATH = path.join(ROOT, 'options.js');
const RUNTIME_JS = [
  'background.js', 'card.js', 'content.js', 'import-worker.js', 'options.js', 'popup.js',
  ...readdirSync(path.join(ROOT, 'lib')).filter(name => name.endsWith('.js')).map(name => path.join('lib', name)),
];

function readJson(file) {
  return JSON.parse(readFileSync(file, 'utf8'));
}

test('manifest sits at the clone root so Chrome can load that folder directly', () => {
  const manifest = readJson(MANIFEST_PATH);
  const packageJson = readJson(PACKAGE_PATH);

  assert.equal(manifest.manifest_version, 3);
  assert.equal(manifest.name, 'Folio');
  assert.equal(manifest.version, '1.0.0');
  assert.match(manifest.version, /^\d+\.\d+\.\d+$/u);
  assert.equal(packageJson.version, manifest.version);
  assert.equal(statSync(path.join(ROOT, 'background.js')).isFile(), true);
  assert.equal(statSync(path.join(ROOT, 'content.js')).isFile(), true);
  assert.deepEqual(manifest.permissions, ['storage', 'unlimitedStorage']);
  assert.deepEqual(manifest.host_permissions, ['https://api.github.com/*']);
  assert.match(manifest.content_security_policy.extension_pages, /script-src 'self'/u);
  assert.match(manifest.content_security_policy.extension_pages, /object-src 'none'/u);
  assert.match(manifest.content_security_policy.extension_pages, /connect-src https:\/\/api\.github\.com\b/u);
  assert.doesNotMatch(manifest.content_security_policy.extension_pages, /connect-src[^;]*\*/u);
});

test('settings page shows the installed version and a manual GitHub update check', () => {
  const html = readFileSync(OPTIONS_PATH, 'utf8');
  const script = readFileSync(OPTIONS_JS_PATH, 'utf8');
  for (const id of ['update-copy', 'current-version', 'check-update', 'update-status', 'open-release', 'update-howto', 'app-version']) {
    assert.match(html, new RegExp(`id="${id}"`, 'u'), id);
  }
  assert.match(html, /只有点击下面的按钮时，才会向 GitHub 查询公开的版本号/u);
  assert.match(script, /checkForUpdate/u);
  assert.match(script, /describeUpdateCheck/u);
  assert.match(script, /readCurrentVersion/u);
});

test('readme tells people to load the clone folder and does not ship a dictionary', () => {
  const readme = readFileSync(path.join(ROOT, 'README.md'), 'utf8');
  const ignore = readFileSync(path.join(ROOT, '.gitignore'), 'utf8');
  assert.match(readme, /打开该文件夹应能直接看到 `manifest\.json`/u);
  assert.match(readme, /仓库里没有词典/u);
  assert.match(readme, /github\.com\/issacsmit\/Folio_dictionary/u);
  assert.doesNotMatch(readme, /longman6-folio-v1\.zip/u);
  assert.doesNotMatch(readme, /research\/longman-conversion\/output/u);
  assert.doesNotMatch(readme, /extension\/manifest\.json/u);
  assert.match(ignore, /^电子词典\//mu);
  assert.match(ignore, /^\*\.mdx$/mu);
  assert.match(ignore, /^\*\.mdd$/mu);
  assert.match(ignore, /\*folio-v1\.zip/u);
  for (const image of ['folio-mark.png', 'folio-card.png', 'folio-settings.png']) {
    assert.equal(statSync(path.join(ROOT, 'docs', 'images', image)).isFile(), true, image);
  }
});

test('only update-check.js may call GitHub or fetch', () => {
  const allowed = path.join(ROOT, 'lib', 'update-check.js');
  const source = readFileSync(allowed, 'utf8');
  assert.equal(GITHUB_API_LATEST, 'https://api.github.com/repos/issacsmit/Folio_dictionary/releases/latest');
  assert.equal(GITHUB_RELEASES_PAGE, 'https://github.com/issacsmit/Folio_dictionary/releases');
  assert.match(source, /api\.github\.com\/repos\/issacsmit\/Folio_dictionary\/releases\/latest/u);
  for (const relative of RUNTIME_JS) {
    const file = path.join(ROOT, relative);
    if (file === allowed) continue;
    const text = readFileSync(file, 'utf8');
    assert.doesNotMatch(text, /api\.github\.com/u, relative);
    assert.doesNotMatch(text, /\bfetch\s*\(/u, relative);
  }
});
