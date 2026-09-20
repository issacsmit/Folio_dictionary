import {chromium} from 'playwright';
import {mkdir, writeFile, readdir, readFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {GITHUB_API_LATEST, GITHUB_RELEASES_PAGE} from '../lib/update-check.js';

const root = path.resolve('.'), output = path.join(root, 'test-results');
const version = JSON.parse(await readFile(path.join(root, 'manifest.json'), 'utf8')).version;
const newer = version.replace(/\d+$/u, n => String(Number(n) + 1));
await mkdir(output, {recursive: true});
const browserCache = path.join(os.homedir(), 'AppData/Local/ms-playwright');
const cached = existsSync(browserCache) ? (await readdir(browserCache)).filter(x => /^chromium-\d+$/.test(x)).sort().reverse() : [];
const executablePath = process.env.FOLIO_TEST_BROWSER || (cached[0] ? path.join(browserCache, cached[0], 'chrome-win64/chrome.exe') : chromium.executablePath());
const context = await chromium.launchPersistentContext(path.join(root, 'tmp', 'update-ui-' + Date.now()), {
  executablePath, headless: true, viewport: {width: 1280, height: 900},
  args: [`--disable-extensions-except=${root}`, `--load-extension=${root}`],
});
context.setDefaultTimeout(15000);
const errors = [], network = [];
context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
context.on('request', req => {
  if (/^https?:/.test(req.url()) && !req.url().startsWith('https://api.github.com/')) network.push(req.url());
});

let payload = {
  tag_name: `v${newer}`,
  html_url: `https://github.com/issacsmit/Folio_dictionary/releases/tag/v${newer}`,
};
let httpStatus = 200;
await context.route('https://api.github.com/**', async route => {
  assert.equal(route.request().url(), GITHUB_API_LATEST);
  if (httpStatus !== 200) {
    await route.fulfill({status: httpStatus, contentType: 'application/json', body: '{"message":"Not Found"}'});
    return;
  }
  await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(payload)});
});

try {
  let worker = context.serviceWorkers()[0];
  if (!worker) worker = await context.waitForEvent('serviceworker');
  const id = new URL(worker.url()).host;
  const page = await context.newPage();
  await page.route('https://api.github.com/**', async route => {
    assert.equal(route.request().url(), GITHUB_API_LATEST);
    if (httpStatus !== 200) {
      await route.fulfill({status: httpStatus, contentType: 'application/json', body: '{"message":"Not Found"}'});
      return;
    }
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(payload)});
  });
  await page.goto(`chrome-extension://${id}/options.html`);
  await page.locator('#check-update').waitFor();
  assert.match(await page.locator('#update-copy').textContent(), new RegExp(`当前版本 ${version.replaceAll('.', '\\.')}`));
  assert.equal(await page.locator('#app-version').textContent(), `Folio ${version}`);
  assert.equal(await page.locator('#open-release').isHidden(), true);
  assert.equal(await page.locator('#update-howto').isHidden(), true);

  await page.locator('#check-update').click();
  await page.getByText(`发现新版本 v${newer}。`, {exact: true}).waitFor();
  assert.equal(await page.locator('#open-release').isVisible(), true);
  assert.equal(await page.locator('#open-release').getAttribute('href'), payload.html_url);
  assert.equal(await page.locator('#open-release').textContent(), `打开 GitHub 更新说明（v${newer}）`);
  assert.equal(await page.locator('#update-howto').isVisible(), true);
  await page.screenshot({path: path.join(output, 'folio-update-available.png'), fullPage: true, animations: 'disabled'});

  payload = {tag_name: `v${version}`, html_url: 'https://evil.example/x'};
  await page.locator('#check-update').click();
  await page.getByText(`已是最新版本（v${version}）。`, {exact: true}).waitFor();
  assert.equal(await page.locator('#open-release').isHidden(), true);
  assert.equal(await page.locator('#update-howto').isHidden(), true);

  httpStatus = 404;
  await page.locator('#check-update').click();
  await page.getByText('暂时无法检查更新。', {exact: true}).waitFor();
  assert.equal(await page.locator('#open-release').isVisible(), true);
  assert.equal(await page.locator('#open-release').getAttribute('href'), GITHUB_RELEASES_PAGE);
  assert.equal(await page.locator('#open-release').textContent(), '打开 GitHub 发布页');
  await page.screenshot({path: path.join(output, 'folio-update-unavailable.png'), fullPage: true, animations: 'disabled'});

  assert.deepEqual(errors, []);
  assert.deepEqual(network, []);
  await writeFile(path.join(output, 'update-ui.json'), JSON.stringify({errors, network, checks: ['available', 'current', 'unavailable']}, null, 2));
  console.log('PASS update UI: available, current, unavailable');
} finally {
  await context.close();
}
