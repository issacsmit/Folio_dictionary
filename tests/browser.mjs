import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile, mkdir, writeFile, readdir} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {deflateRawSync} from 'node:zlib';

const root = path.resolve('.'), output = path.join(root, 'test-results');
const installedVersion = JSON.parse(await readFile(path.join(root,'manifest.json'),'utf8')).version;
await mkdir(output,{recursive:true});
const browserCache = path.join(os.homedir(), 'AppData/Local/ms-playwright');
const cached = existsSync(browserCache) ? (await readdir(browserCache)).filter(x=>/^chromium-\d+$/.test(x)).sort().reverse() : [];
const executablePath = process.env.FOLIO_TEST_BROWSER || (cached[0] ? path.join(browserCache,cached[0],'chrome-win64/chrome.exe') : chromium.executablePath());
const server = createServer(async (req,res) => {
  const url = new URL(req.url,'http://localhost'), pathname = decodeURIComponent(url.pathname);
  if (!['/tests/reading.html','/tests/frame.html'].includes(pathname)) {res.writeHead(404).end();return;}
  res.setHeader('Content-Type','text/html; charset=utf-8'); res.end(await readFile(path.join(root,pathname)));
});
await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const context = await chromium.launchPersistentContext(path.join(root,'tmp','browser-test-'+Date.now()), {
  executablePath, headless:true, viewport:{width:1280,height:950},
  ignoreDefaultArgs:['--hide-scrollbars'],
  args:[`--disable-extensions-except=${root}`,`--load-extension=${root}`],
});
context.setDefaultTimeout(15000);
await context.route(/google\./i, route => route.fulfill({status:200, contentType:'text/html', body:'<!doctype html><title>Google</title>'}));
const errors=[],network=[]; const metrics={browser:context.browser()?.version(),checks:[]};
context.on('page',page => page.on('pageerror',error=>{if(!/google\./i.test(page.url())) errors.push(error.message);}));
context.on('request',req=>{if(/^https?:/.test(req.url())&&!req.url().startsWith(origin)&&!/google\./i.test(req.url()))network.push(req.url());});
const check = text => {metrics.checks.push(text); console.log('PASS',text);};
function zip(files) {
  const blocks=[],central=[];let offset=0;
  for(const [name,text] of Object.entries(files)) {
    const raw=Buffer.from(text),data=deflateRawSync(raw),n=Buffer.from(name),h=Buffer.alloc(30),c=Buffer.alloc(46);
    h.writeUInt32LE(0x04034b50);h.writeUInt16LE(20,4);h.writeUInt16LE(8,8);h.writeUInt32LE(data.length,18);h.writeUInt32LE(raw.length,22);h.writeUInt16LE(n.length,26);blocks.push(h,n,data);
    c.writeUInt32LE(0x02014b50);c.writeUInt16LE(20,6);c.writeUInt16LE(8,10);c.writeUInt32LE(data.length,20);c.writeUInt32LE(raw.length,24);c.writeUInt16LE(n.length,28);c.writeUInt32LE(offset,42);central.push(c,n);offset+=h.length+n.length+data.length;
  }
  const dir=Buffer.concat(central),end=Buffer.alloc(22);end.writeUInt32LE(0x06054b50);end.writeUInt16LE(3,8);end.writeUInt16LE(3,10);end.writeUInt32LE(dir.length,12);end.writeUInt32LE(offset,16);return Buffer.concat([...blocks,dir,end]);
}
function fixture({badRef=false,badHash=false}={}) {
  const entries=JSON.stringify({id:'self-authored',headword:'foliofixture',kind:'word',pos_groups:[{pos:['noun'],senses:[{id:'s',definition:{en:'A small page made for testing.',zh:'一张用于测试的小书页。'}}]}]})+'\n';
  const lookup=JSON.stringify({norm:'foliofixture',matches:[{entry_id:badRef?'missing':'self-authored',match:'headword',headword:'foliofixture'}]})+'\n';
  const sha=v=>createHash('sha256').update(v).digest('hex');
  const manifest={format:'folio-dict-pack',format_version:'1.0',pack_id:'fixture',source:{name:'自编测试词典'},counts:{entries:1,lookup_keys:1},checksums:{'entries.jsonl':badHash?'0'.repeat(64):sha(entries),'lookup.jsonl':sha(lookup)}};
  return zip({'manifest.json':JSON.stringify(manifest),'entries.jsonl':entries,'lookup.jsonl':lookup});
}
try {
  let worker=context.serviceWorkers()[0]; if(!worker)worker=await context.waitForEvent('serviceworker');
  const id=new URL(worker.url()).host;
  let options=await context.newPage();
  await options.goto(`chrome-extension://${id}/options.html`); await options.locator('#pack-file').waitFor();
  assert.match(await options.locator('#update-copy').textContent(), new RegExp(`当前版本 ${installedVersion.replaceAll('.','\\.')}`));
  assert.equal(await options.locator('#check-update').isVisible(), true);
  assert.equal(await options.locator('#open-release').isHidden(), true);
  check('settings shows the installed version and does not query GitHub until clicked');
  const api=(query)=>options.evaluate(query=>chrome.runtime.sendMessage({type:'lookup',query}),query);
  assert.equal((await api('resonate')).status,'no-dictionary'); check('first-run empty state');
  const article=await context.newPage(); await article.goto(origin+'/tests/reading.html');
  async function select(selector,key='Alt',page=article) {
    await page.locator(selector).scrollIntoViewIfNeeded();
    await page.locator(selector).evaluate(node=>{document.activeElement?.blur();const range=document.createRange();range.selectNodeContents(node);const s=getSelection();s.removeAllRanges();s.addRange(range);});
    await page.keyboard.press(key);
  }
  await select('#word'); await article.getByText('先导入一本词典，让 Folio 陪你阅读。').waitFor(); check('selection shortcut and import call-to-action'); await article.keyboard.press('Escape');
  async function importFile(file, success=true) {
    await options.locator('#pack-file').setInputFiles(file);
    await options.waitForFunction(()=>!document.getElementById('pack-file').disabled,{},{timeout:180000});
    const text=await options.locator('#import-status').textContent();
    if(success)assert.match(text,/导入完成/);else assert.match(text,/未被替换/);
    return text;
  }
  const started=performance.now();
  const timer=setInterval(async()=>console.log('IMPORT',await options.locator('#import-status').textContent().catch(()=>'')),10000);
  try {await importFile(path.join(root,'research/longman-conversion/output/longman6-folio-v1.zip'));} finally {clearInterval(timer);}
  metrics.importSeconds=+( (performance.now()-started)/1000).toFixed(2);
  check('real Longman ZIP import with all checksums, counts and references');
  const pack=await options.evaluate(()=>chrome.runtime.sendMessage({type:'status'})); assert.equal(pack.pack.entries,60465);assert.equal(pack.pack.keys,364887);
  // Recreate the old single-dictionary metadata, then exercise adoption by the settings page.
  await options.evaluate(async()=>{const {openDB,complete}=await import('./lib/db.js');const db=await openDB(),tx=db.transaction('meta','readwrite'),done=complete(tx);tx.objectStore('meta').delete('library');await done;});
  await options.reload(); await options.locator('.dictionary-row').waitFor();
  assert.equal(await options.locator('.dictionary-row').count(),1);
  assert.equal((await api('resonate')).status,'ok');check('legacy single dictionary is adopted without reimport or data loss');
  const cases=[['resonate','resonate'],['throughout','throughout'],['studies','study'],['running','running'],['went','went'],['U.','U.'],['U','U'],['v.','v.'],['V','V'],['run.','run'],['propagation','propagation'],['refraction','refraction']];
  const timings=[];
  for(const [query,expected] of cases){const t=performance.now();const data=await api(query);timings.push(performance.now()-t);assert.equal(data.status,'ok',query);assert.equal(data.results[0].entry.headword,expected,query);}
  metrics.queryMilliseconds=timings.map(t=>+t.toFixed(1));check('headwords, inflections, punctuation, abbreviations and derived locators');
  assert.ok((await api('running')).results.some(r=>r.entry.headword==='run'));check('exact running entries retain the associated run inflection');
  assert.ok((await api('went')).results.some(r=>r.entry.headword==='go'));check('went retains its original entry and links to go');
  const phrase=await api('run out of');assert.equal(phrase.status,'ok');assert.ok(phrase.results.some(r=>r.senseIds.length||r.entry.kind==='phrasal_verb'));check('phrase-to-sense lookup');
  assert.equal((await api('zznonexistentword')).status,'not-found');
  await select('#word');await article.getByText('引起共鸣',{exact:true}).first().waitFor();
  await article.locator('folio-dictionary .brand-mark img').evaluate(img => img.decode());
  assert.equal(await article.locator('folio-dictionary .brand-mark img').evaluate(img => img.naturalWidth),256);
  const style=await article.locator('folio-dictionary h2').first().evaluate(el=>({color:getComputedStyle(el).color,size:getComputedStyle(el).fontSize}));assert.notEqual(style.color,'rgb(255, 0, 0)');assert.equal(style.size,'32px');
  assert.equal(await article.locator('folio-dictionary .scrollport').evaluate(el => getComputedStyle(el).getPropertyValue('--scroll-visibility').trim()), '0');
  // Close the initial settings tab so the card action must actually open it again.
  await options.close();
  const openedSettings = context.waitForEvent('page');
  await article.getByRole('button', {name:'打开 Folio 设置'}).click();
  const settingsTab = await openedSettings;
  await settingsTab.waitForURL(`chrome-extension://${id}/options.html`);
  await settingsTab.locator('#trigger').waitFor();
  options = settingsTab;
  assert.equal(await article.getByRole('button',{name:'打开 Folio 设置'}).textContent(),'');
  assert.equal(await article.getByRole('button',{name:'打开 Folio 设置'}).locator('svg').count(),1);
  check('entry footer opens the settings page after dictionary import');
  await options.locator('.dictionary-name-form input').fill('我的朗文');
  await options.getByRole('button',{name:'保存',exact:true}).click();
  await article.locator('folio-dictionary .source').filter({hasText:/^我的朗文$/}).waitFor();
  assert.equal((await api('resonate')).source,'我的朗文');
  await options.locator('#query').fill('resonate');await options.getByRole('button',{name:'查词',exact:true}).click();await options.locator('#preview .source').filter({hasText:/^我的朗文$/}).waitFor();
  await options.locator('.dictionary-name-form input').fill('朗文 · 阅读用');await options.getByRole('button',{name:'保存',exact:true}).click();
  await options.locator('#preview .source').filter({hasText:/^朗文 · 阅读用$/}).waitFor();
  await article.locator('folio-dictionary .source').filter({hasText:/^朗文 · 阅读用$/}).waitFor();
  check('custom dictionary names immediately update open entry cards and settings preview');
  await article.screenshot({path:path.join(output,'folio-light.png'),animations:'disabled'});check('real card styling isolated from hostile page rules');
  await article.locator('folio-dictionary').getByText('英文原释义',{exact:true}).first().click();await article.locator('folio-dictionary details[open]').first().waitFor();check('English definition disclosure');
  await article.keyboard.press('Escape');assert.equal(await article.locator('folio-dictionary').count(),0);check('Escape dismisses card');
  await select('#run');await article.locator('folio-dictionary .word').first().waitFor();await article.getByText(/更多释义/).first().click();check('multiple homographs and long-entry expansion');
  const scroller = article.locator('folio-dictionary .scrollport');
  const frameBounds = await article.locator('folio-dictionary .card').boundingBox(), scrollBounds = await scroller.boundingBox();
  const rightInset = frameBounds.x + frameBounds.width - scrollBounds.x - scrollBounds.width;
  assert.ok(rightInset >= 1 && rightInset <= 2.1);
  assert.ok(scrollBounds.y > frameBounds.y + 7 && scrollBounds.y + scrollBounds.height < frameBounds.y + frameBounds.height - 7);
  assert.ok(await scroller.evaluate(el => el.scrollHeight > el.clientHeight));
  assert.equal(await scroller.evaluate(el => getComputedStyle(el, '::-webkit-scrollbar').width), '3px');
  // Clicking an off-screen disclosure can itself scroll the native region; wait for it to settle.
  await article.waitForFunction(() => !document.querySelector('folio-dictionary').shadowRoot.querySelector('.scrollport').hasAttribute('data-scrolling'));
  assert.equal(await scroller.evaluate(el => getComputedStyle(el).getPropertyValue('--scroll-visibility').trim()), '0');
  const idleWidth = await scroller.evaluate(el => el.clientWidth);
  const pageScroll = await article.evaluate(() => scrollY);
  const beforeWheel = await scroller.evaluate(el => el.scrollTop);
  await article.mouse.move(scrollBounds.x + 100, scrollBounds.y + 100); await article.mouse.wheel(0, 240);
  await article.waitForFunction(before => {const el = document.querySelector('folio-dictionary').shadowRoot.querySelector('.scrollport');return el.scrollTop !== before && el.hasAttribute('data-scrolling');}, beforeWheel);
  assert.equal(await article.evaluate(() => scrollY), pageScroll);
  assert.equal(await scroller.getAttribute('data-scrolling'), 'true');
  await article.waitForFunction(() => !document.querySelector('folio-dictionary').shadowRoot.querySelector('.scrollport').hasAttribute('data-scrolling'));
  assert.equal(await scroller.evaluate(el => el.clientWidth), idleWidth);
  await article.screenshot({path:path.join(output,'folio-scrollbar-idle.png'),animations:'disabled'});
  await scroller.evaluate(el => el.scrollTop = 0);
  await article.mouse.move(scrollBounds.x + scrollBounds.width - 1.5, scrollBounds.y + 14);
  await article.mouse.down(); await article.mouse.move(scrollBounds.x + scrollBounds.width - 1.5, scrollBounds.y + 140, {steps:8}); await article.mouse.up();
  assert.ok(await scroller.evaluate(el => el.scrollTop > 0));
  const settingsBounds = await article.getByRole('button', {name:'打开 Folio 设置'}).boundingBox();
  assert.ok(settingsBounds.y >= frameBounds.y && settingsBounds.y + settingsBounds.height <= frameBounds.y + frameBounds.height);
  await article.screenshot({path:path.join(output,'folio-inset-scrollbar.png'),animations:'disabled'});
  await article.waitForFunction(() => !document.querySelector('folio-dictionary').shadowRoot.querySelector('.scrollport').hasAttribute('data-scrolling'));
  await scroller.focus(); await article.keyboard.press('PageDown');
  await article.waitForFunction(() => document.querySelector('folio-dictionary').shadowRoot.querySelector('.scrollport').hasAttribute('data-scrolling'));
  check('3px edge scrollbar appears on scrolling, fades while idle, and supports wheel, dragging and keyboard without layout shifts'); await article.keyboard.press('Escape');
  await select('#derived');await article.getByText('本词在词典中作为派生词收录，没有独立释义。').waitFor();await article.getByRole('button',{name:'关联词条 · propagate'}).click();await article.locator('folio-dictionary .word').filter({hasText:/^propagate/}).first().waitFor();check('derived entry links to parent without inventing a definition');await article.keyboard.press('Escape');
  await select('#fish');await article.getByText('英文释义',{exact:true}).first().waitFor();check('English-only sense fallback');await article.keyboard.press('Escape');
  await select('#unknown');await article.getByText(/词典未收录这个词/).waitFor();
  const googleTab=context.waitForEvent('page');
  await article.keyboard.press('Enter');
  const google=await googleTab;
  await google.waitForURL(/zznonexistentword/);
  assert.match(google.url(),/zznonexistentword/);
  await google.close();
  check('not-found card opens Google search with Enter');
  await select('#unknown');await article.getByText(/词典未收录这个词/).waitFor();
  const googleClick=context.waitForEvent('page');
  await article.getByRole('button',{name:'用 Google 搜索'}).click();
  const googleFromButton=await googleClick;
  await googleFromButton.waitForURL(/google\./);
  await googleFromButton.close();
  await article.keyboard.press('Escape');
  await select('#unknown');await article.getByText(/词典未收录这个词/).waitFor();await article.mouse.click(30,30);assert.equal(await article.locator('folio-dictionary').count(),0);check('not-found and outside-click dismissal');
  await article.locator('#input').focus();await article.locator('#input').selectText();await article.keyboard.press('Alt');assert.equal(await article.locator('folio-dictionary').count(),0);
  await article.locator('#editor').focus();await article.locator('#editor').selectText();await article.keyboard.press('Alt');assert.equal(await article.locator('folio-dictionary').count(),0);check('inputs and contenteditable do not trigger');
  await article.evaluate(()=>document.body.classList.add('dark'));await select('#word');await article.locator('folio-dictionary .card.dark').waitFor();await article.screenshot({path:path.join(output,'folio-dark.png'),animations:'disabled'});check('automatic dark reading-surface theme');await article.keyboard.press('Escape');
  await article.setViewportSize({width:390,height:844});await select('#bottom');await article.locator('folio-dictionary .word').first().waitFor();
  const bounds=await article.locator('folio-dictionary .card').boundingBox();assert.ok(bounds.x>=0&&bounds.x+bounds.width<=391&&bounds.y>=0&&bounds.y+bounds.height<=845,JSON.stringify(bounds));await article.screenshot({path:path.join(output,'folio-narrow.png'),animations:'disabled'});check('narrow viewport and bottom-edge positioning');await article.keyboard.press('Escape');
  await article.setViewportSize({width:1280,height:950});await article.evaluate(()=>document.body.classList.remove('dark'));
  await options.locator('#trigger').click();await options.keyboard.press('d');await options.getByText('已保存',{exact:true}).waitFor();
  await select('#word','d');await article.locator('folio-dictionary .word').first().waitFor();check('custom single-letter shortcut updates existing pages');await article.keyboard.press('Escape');
  await options.locator('#enabled').uncheck();await select('#word','d');assert.equal(await article.locator('folio-dictionary').count(),0);check('disable switch updates existing pages');await options.locator('#enabled').check();
  await options.locator('#trigger').click();await options.keyboard.press('Alt');
  await options.waitForFunction(async()=>((await chrome.storage.local.get('settings')).settings.trigger==='Alt'));
  const frame=article.frameLocator('iframe');await frame.locator('#frame-word').click();await frame.locator('#frame-word').selectText();await article.keyboard.press('Alt');await frame.locator('folio-dictionary .word').first().waitFor();check('same-origin iframe selection');
  for(const flags of [{badHash:true},{badRef:true}]){await importFile({name:'invalid.zip',mimeType:'application/zip',buffer:fixture(flags)},false);assert.equal((await api('resonate')).status,'ok');}check('failed checksum/reference imports preserve active dictionary');
  await options.reload();assert.equal((await api('resonate')).status,'ok');check('dictionary persists after page reload');
  await options.screenshot({path:path.join(output,'folio-settings.png'),fullPage:true});
  const popup=await context.newPage();await popup.goto(`chrome-extension://${id}/popup.html`);await popup.getByText(/60,465/).waitFor();await popup.screenshot({path:path.join(output,'folio-popup.png')});check('toolbar popup reports dictionary state');
  // Interrupt a replacement after staging data exists, then verify the old generation and cleanup recovery.
  await options.locator('#pack-file').setInputFiles(path.join(root,'research/longman-conversion/output/longman6-folio-v1.zip'));
  await options.waitForFunction(()=>document.getElementById('progress').value>=10,{},{timeout:60000});
  options.once('dialog',dialog=>dialog.accept());await options.reload();assert.equal((await api('resonate')).status,'ok');check('interrupted replacement retains active dictionary');
  await importFile({name:'self-authored.zip',mimeType:'application/zip',buffer:fixture()});
  assert.equal((await api('foliofixture')).status,'ok');assert.equal((await api('resonate')).status,'not-found');
  assert.equal(await options.locator('.dictionary-row').count(),2);
  await options.getByRole('radio',{name:'使用 朗文 · 阅读用',exact:true}).check();
  assert.equal((await api('resonate')).status,'ok');assert.equal((await api('foliofixture')).status,'not-found');
  await select('#word');await article.locator('folio-dictionary .source').filter({hasText:/^朗文 · 阅读用$/}).waitFor();
  await options.getByRole('radio',{name:'使用 自编测试词典',exact:true}).check();
  await article.getByText(/词典未收录这个词/).waitFor();
  await article.locator('folio-dictionary .source').filter({hasText:/^自编测试词典$/}).waitFor();
  check('multiple dictionaries remain available and selection updates an already open card');
  const fixtureRow = options.locator('.dictionary-row').filter({has:options.getByRole('radio',{name:'使用 自编测试词典',exact:true})});
  await fixtureRow.getByRole('textbox',{name:'词典名称'}).fill('我的小词库');await fixtureRow.getByRole('button',{name:'保存',exact:true}).click();
  await options.getByText('名称已保存',{exact:true}).waitFor();
  await importFile({name:'updated.zip',mimeType:'application/zip',buffer:fixture()});
  assert.equal(await options.locator('.dictionary-row').count(),2);assert.equal((await api('foliofixture')).source,'我的小词库');
  for(const flags of [{badHash:true},{badRef:true}]) await importFile({name:'invalid.zip',mimeType:'application/zip',buffer:fixture(flags)},false);
  assert.equal((await api('foliofixture')).status,'ok');
  await options.getByRole('radio',{name:'使用 朗文 · 阅读用',exact:true}).check();assert.equal((await api('resonate')).status,'ok');
  const counts=await options.evaluate(async()=>{const {openDB,result}=await import('./lib/db.js');const db=await openDB();return Promise.all(['entries','lookup'].map(s=>result(db.transaction(s).objectStore(s).count())));});assert.deepEqual(counts,[60466,364888]);
  check('same-pack updates preserve custom names and other dictionaries; only obsolete or abandoned generations are cleaned');
  await options.reload();await options.locator('.dictionary-row').first().waitFor();assert.equal(await options.locator('.dictionary-row').count(),2);assert.equal((await api('resonate')).source,'朗文 · 阅读用');
  assert.ok(await options.getByRole('radio',{name:'使用 朗文 · 阅读用',exact:true}).isChecked());
  check('dictionary library, custom names and selection persist across reload');
  await options.screenshot({path:path.join(output,'folio-settings.png'),fullPage:true});
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);check('no page errors or external data requests');
  metrics.errors=errors;metrics.externalRequests=network;await writeFile(path.join(output,'verification.json'),JSON.stringify(metrics,null,2));
  console.log('COMPLETE',JSON.stringify(metrics));
} catch(error) {console.error('ERRORS',errors);throw error;}
finally {await context.close();server.close();}
