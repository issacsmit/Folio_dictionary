import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {mkdir,writeFile,readdir} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=process.cwd(),cache=path.join(os.homedir(),'AppData/Local/ms-playwright');
const cached=(await readdir(cache)).filter(x=>/^chromium-\d+$/.test(x)).sort().reverse();
const server=createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end('<body style="margin:80px"><p id="word">resonate</p></body>');});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const profile=path.join(root,'tmp','folio-reload-test-'+Date.now());
const context=await chromium.launchPersistentContext(profile,{executablePath:process.env.FOLIO_TEST_BROWSER || path.join(cache,cached[0],'chrome-win64/chrome.exe'),headless:true,args:[`--disable-extensions-except=${root}`,`--load-extension=${root}`]});
context.setDefaultTimeout(5000);
const errors=[],checks=[];
context.on('page',page=>page.on('pageerror',error=>errors.push(error.message)));
try {
  let worker=context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
  const id=new URL(worker.url()).host;
  const article=await context.newPage();await article.goto(`http://127.0.0.1:${server.address().port}`);
  async function select(){await article.locator('#word').selectText();await article.keyboard.press('Enter');}
  await select();await article.getByText('先导入一本词典，让 Folio 陪你阅读。').waitFor();
  const management=await context.newPage();await management.goto('chrome://extensions/');
  await management.locator('extensions-toolbar #devMode').click();
  const managedItem=management.locator('extensions-item').filter({hasText:'Folio'});await managedItem.waitFor();
  for(let iteration=0;iteration<3;iteration++) {
    const previous=worker;
    const restarted=context.waitForEvent('serviceworker',{predicate:w=>w!==previous});
    restarted.catch(()=>{});
    await managedItem.locator('#dev-reload-button').click();
    try {worker=await restarted;} catch(error) {console.log('AFTER_RELOAD',await managedItem.evaluate(el=>({state:el.data.state,disableReasons:el.data.disableReasons,manifestErrors:el.data.manifestErrors,runtimeErrors:el.data.runtimeErrors,views:el.data.views})));throw error;}
    if(iteration===0){
      // The old card survives extension reload. Its settings action must not throw synchronously.
      await article.getByRole('button',{name:'打开 Folio 设置'}).click();
      await article.getByText('Folio 已更新，请刷新此网页后继续查词。',{exact:true}).waitFor();
      checks.push('settings action in an old card handles extension invalidation');
    }
    await article.keyboard.press('Escape');await select();
    await article.getByText('Folio 已更新，请刷新此网页后继续查词。',{exact:true}).waitFor();
    await article.keyboard.press('Escape');await select();
    await article.getByText('Folio 已更新，请刷新此网页后继续查词。',{exact:true}).waitFor();
    assert.deepEqual(errors,[]);
    checks.push(`reload ${iteration+1}: old page shows recovery instructions without unhandled errors`);
    const options=await context.newPage();await options.goto(`chrome-extension://${id}/options.html`);
    const state=await options.evaluate(()=>chrome.runtime.sendMessage({type:'status'}));assert.equal(state.settings.trigger,'Enter');
    await options.close();
    await article.reload();await select();await article.getByText('先导入一本词典，让 Folio 陪你阅读。').waitFor();
    await article.locator('folio-dictionary .brand-mark img').evaluate(img=>img.decode());
    checks.push(`reload ${iteration+1}: service worker, refreshed page and icon recover`);
  }
  const manager=await context.newPage();await manager.goto('chrome://extensions/');
  const item=manager.locator('extensions-item').filter({hasText:'Folio'});await item.waitFor();
  const extensionErrors=await item.evaluate(el=>({manifest:el.data.manifestErrors,runtime:el.data.runtimeErrors}));
  assert.deepEqual(extensionErrors,{manifest:[],runtime:[]});assert.deepEqual(errors,[]);
  checks.push('Chrome extension manager has no script-fetch, manifest or runtime errors');
  await mkdir('test-results',{recursive:true});await writeFile('test-results/reload-verification.json',JSON.stringify({checks,errors,extensionErrors},null,2));
  console.log('PASS',JSON.stringify(checks));
} catch(error){console.error('CAPTURED_ERRORS',JSON.stringify(errors));console.error('FAILURE',error);throw error;}
finally {await context.close();server.close();console.log('TEST_PROFILE',profile);}
