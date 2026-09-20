import test from 'node:test';
import assert from 'node:assert/strict';
import {
  GITHUB_API_LATEST,
  GITHUB_RELEASES_PAGE,
  checkForUpdate,
  describeUpdateCheck,
  isNewerVersion,
  normalizeVersion,
  readCurrentVersion,
  sanitizeReleaseUrl,
} from '../lib/update-check.js';

test('current version comes from the loaded extension manifest without a stale fallback', () => {
  assert.equal(readCurrentVersion({runtime: {getManifest: () => ({version: '1.1.3'})}}), '1.1.3');
  assert.equal(readCurrentVersion(null), null);
  assert.equal(normalizeVersion('v0.1.0'), '0.1.0');
  assert.equal(normalizeVersion('not-a-version'), null);
});

test('update check fails closed when the loaded extension version is unavailable', async () => {
  let fetched = false;
  const result = await checkForUpdate({
    chrome: null,
    fetch: async () => {
      fetched = true;
      return {ok: true, json: async () => ({tag_name: 'v9.9.9'})};
    },
  });
  assert.equal(fetched, false);
  assert.deepEqual(result, {
    status: 'unavailable',
    current: null,
    code: 'CURRENT_VERSION_UNAVAILABLE',
    htmlUrl: GITHUB_RELEASES_PAGE,
  });
});

test('semver comparison treats dotted numbers as newer, not strings', () => {
  assert.equal(isNewerVersion('1.1.0', '1.0.0'), true);
  assert.equal(isNewerVersion('v1.1.0', '1.0.0'), true);
  assert.equal(isNewerVersion('1.0.0', '1.0.0'), false);
  assert.equal(isNewerVersion('1.9.0', '1.10.0'), false);
  assert.equal(isNewerVersion('1.10.0', '1.9.0'), true);
  assert.equal(isNewerVersion('2.0', '1.9.9'), true);
  assert.equal(isNewerVersion('not-a-version', '1.0.0'), false);
});

test('checkForUpdate reports a newer GitHub release', async () => {
  const result = await checkForUpdate({
    currentVersion: '1.0.0',
    fetch: async url => {
      assert.equal(url, GITHUB_API_LATEST);
      return {
        ok: true,
        json: async () => ({
          tag_name: 'v1.1.0',
          html_url: 'https://github.com/issacsmit/Folio_dictionary/releases/tag/v1.1.0',
        }),
      };
    },
  });
  assert.deepEqual(result, {
    status: 'available',
    current: '1.0.0',
    latest: '1.1.0',
    htmlUrl: 'https://github.com/issacsmit/Folio_dictionary/releases/tag/v1.1.0',
  });
});

test('checkForUpdate treats matching versions as current', async () => {
  const result = await checkForUpdate({
    currentVersion: '1.0.0',
    fetch: async () => ({
      ok: true,
      json: async () => ({tag_name: 'v1.0.0', html_url: 'https://evil.example/x'}),
    }),
  });
  assert.equal(result.status, 'current');
  assert.equal(result.latest, '1.0.0');
  assert.equal(result.htmlUrl, GITHUB_RELEASES_PAGE);
});

test('checkForUpdate fails closed when GitHub is missing or broken', async () => {
  const missing = await checkForUpdate({
    currentVersion: '1.0.0',
    fetch: async () => ({ok: false, status: 404}),
  });
  assert.equal(missing.status, 'unavailable');
  assert.equal(missing.htmlUrl, GITHUB_RELEASES_PAGE);

  const crashed = await checkForUpdate({
    currentVersion: '1.0.0',
    fetch: async () => { throw new Error('offline'); },
  });
  assert.equal(crashed.status, 'unavailable');
  assert.equal(crashed.code, 'NETWORK');
});

test('checkForUpdate times out instead of hanging', async () => {
  const result = await checkForUpdate({
    currentVersion: '1.0.0',
    timeoutMs: 20,
    fetch: () => new Promise(() => {}),
  });
  assert.equal(result.status, 'unavailable');
  assert.equal(result.code, 'TIMEOUT');
});

test('release links stay on the Folio GitHub repository', () => {
  assert.equal(
    sanitizeReleaseUrl('https://github.com/issacsmit/Folio_dictionary/releases/tag/v0.2.0'),
    'https://github.com/issacsmit/Folio_dictionary/releases/tag/v0.2.0',
  );
  assert.equal(sanitizeReleaseUrl('https://evil.example/x'), GITHUB_RELEASES_PAGE);
  assert.equal(
    sanitizeReleaseUrl('https://github.com/issacsmit/Folio_dictionary/releases\\tag'),
    GITHUB_RELEASES_PAGE,
  );
});

test('update copy only offers a GitHub link when a newer version exists or the check failed', () => {
  assert.deepEqual(describeUpdateCheck({
    status: 'available',
    latest: '1.1.0',
    htmlUrl: 'https://github.com/issacsmit/Folio_dictionary/releases/tag/v1.1.0',
  }), {
    statusText: '发现新版本 v1.1.0。',
    showLink: true,
    linkText: '打开 GitHub 更新说明（v1.1.0）',
    href: 'https://github.com/issacsmit/Folio_dictionary/releases/tag/v1.1.0',
    showHowto: true,
  });
  assert.equal(describeUpdateCheck({status: 'current', current: '0.1.0'}).showLink, false);
  assert.match(describeUpdateCheck({status: 'current', current: '0.1.0'}).statusText, /已是最新版本（v0\.1\.0）/);
  const failed = describeUpdateCheck({status: 'unavailable', htmlUrl: GITHUB_RELEASES_PAGE});
  assert.equal(failed.statusText, '暂时无法检查更新。');
  assert.equal(failed.showLink, true);
  assert.equal(failed.href, GITHUB_RELEASES_PAGE);
});
