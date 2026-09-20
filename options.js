import {libraryState, renamePack, selectPack, announceChange} from './lib/db.js';
import {cleanSettings, shortcutFromEvent} from './lib/core.js';
import {checkForUpdate, describeUpdateCheck, readCurrentVersion} from './lib/update-check.js';
const $ = id => document.getElementById(id);
let settings = cleanSettings(), worker, querying = 0, busy = false, updateChecking = false;
async function refreshPack() {
  const {packs, activeId} = await libraryState();
  $('pack-badge').textContent = packs.length ? `${packs.length} 部 · 离线可用` : '尚未导入';
  $('pack-meta').textContent = packs.length ? '选择一部用于查词。名称可以自由修改，也会显示在词条底部。' : '为 Folio 放入第一本词典。导入一次，即可离线查词。';
  const rows = packs.map(pack => {
    const row = document.createElement('div'); row.className = 'dictionary-row'; row.dataset.packId = pack.id;
    const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'current-dictionary'; radio.checked = pack.id === activeId; radio.setAttribute('aria-label', `使用 ${pack.name}`);
    radio.addEventListener('change', async () => {
      try {await selectPack(pack.id); await refreshPack(); status('library-status', `正在使用：${pack.name}`);}
      catch (error) {status('library-status', error.message, true); await refreshPack();}
    });
    const body = document.createElement('div'); body.className = 'dictionary-body';
    const form = document.createElement('form'); form.className = 'dictionary-name-form';
    const name = document.createElement('input'); name.value = pack.name; name.maxLength = 80; name.required = true; name.setAttribute('aria-label', '词典名称'); name.autocomplete = 'off';
    const save = document.createElement('button'); save.type = 'submit'; save.className = 'rename-button'; save.textContent = '保存'; save.disabled = true;
    name.addEventListener('input', () => {save.disabled = name.value.trim() === pack.name; name.setCustomValidity('');});
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (!name.value.trim()) {name.setCustomValidity('请输入词典名称。'); name.reportValidity(); return;}
      save.disabled = true;
      try {await renamePack(pack.id, name.value); pack.name = name.value.trim(); name.value = pack.name; radio.setAttribute('aria-label', `使用 ${pack.name}`); status('library-status', '名称已保存');}
      catch (error) {save.disabled = false; status('library-status', error.message, true);}
    });
    form.append(name, save);
    const meta = document.createElement('p'); meta.className = 'small muted'; meta.textContent = `${pack.entries.toLocaleString()} 个词条 · ${pack.keys.toLocaleString()} 个查询键 · ${new Date(pack.importedAt).toLocaleDateString()} 导入`;
    body.append(form, meta); row.append(radio, body); return row;
  });
  $('dictionary-list').replaceChildren(...rows);
}
function status(id, text, error = false) {$(id).textContent = text; $(id).classList.toggle('error', error);}
function applyUpdateView(result) {
  const view = describeUpdateCheck(result);
  const status = $('update-status'), link = $('open-release'), howto = $('update-howto');
  status.hidden = false;
  status.textContent = view.statusText;
  howto.hidden = !view.showHowto;
  if (view.showLink) {
    link.hidden = false;
    link.href = view.href;
    link.textContent = view.linkText;
  } else {
    link.hidden = true;
    link.removeAttribute('href');
  }
}
async function init() {
  settings = cleanSettings((await chrome.storage.local.get('settings')).settings);
  $('trigger').textContent = settings.trigger; $('search-key').textContent = settings.searchKey;
  $('key-hint').textContent = settings.trigger; $('theme').value = settings.theme; $('enabled').checked = settings.enabled;
  const version = readCurrentVersion();
  $('current-version').textContent = version || '未知';
  $('app-version').textContent = version ? `Folio ${version}` : 'Folio';
  await refreshPack();
}
async function saveSettings(partial) {
  settings = cleanSettings({...settings, ...partial, theme:$('theme').value, enabled:$('enabled').checked});
  try {
    await chrome.storage.local.set({settings});
    $('trigger').textContent = settings.trigger; $('search-key').textContent = settings.searchKey;
    $('key-hint').textContent = settings.trigger; status('setting-status', '已保存');
  } catch {status('setting-status', '未能保存，请重试。', true);}
}
function bindShortcut(id, field) {
  const node = $(id);
  node.addEventListener('click', () => {node.classList.add('listening'); node.textContent = '按下按键';});
  node.addEventListener('blur', () => {node.classList.remove('listening'); node.textContent = settings[field];});
  node.addEventListener('keydown', event => {
    if (event.key === 'Tab') return;
    event.preventDefault(); event.stopPropagation();
    if (event.key === 'Escape') {node.blur(); return;}
    const key = shortcutFromEvent(event);
    if (!key) {status('setting-status', '请使用 Alt、Enter、空格、F1–F12 或单个字母、数字。', true); return;}
    node.classList.remove('listening'); node.textContent = key;
    void saveSettings({[field]: key}).then(() => node.blur());
  });
}
bindShortcut('trigger', 'trigger');
bindShortcut('search-key', 'searchKey');
for (const id of ['theme', 'enabled']) $(id).addEventListener('change', () => void saveSettings({}));
$('check-update').addEventListener('click', async () => {
  if (updateChecking || busy) return;
  updateChecking = true;
  $('check-update').disabled = true;
  $('update-status').hidden = false;
  $('update-status').textContent = '正在检查…';
  $('open-release').hidden = true;
  $('update-howto').hidden = true;
  let result;
  try {result = await checkForUpdate();}
  catch {result = {status: 'unavailable'};}
  updateChecking = false;
  if (!$('update-status').isConnected) return;
  applyUpdateView(result);
  $('check-update').disabled = busy;
});
document.querySelector('.file-label').addEventListener('keydown', event => {if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); $('pack-file').click();}});
$('pack-file').addEventListener('change', () => {
  const file = $('pack-file').files[0]; if (!file || busy) return;
  busy = true; $('pack-file').disabled = true; $('check-update').disabled = true; $('import-progress').hidden = false; $('progress').value = 0;
  status('import-status', '正在准备导入…'); worker = new Worker('import-worker.js', {type:'module'});
  function finish() {busy = false; $('pack-file').disabled = false; $('check-update').disabled = updateChecking; $('pack-file').value = ''; $('import-progress').hidden = true; worker?.terminate(); worker = null;}
  worker.onmessage = async ({data}) => {
    try {
      if (data.type === 'progress') {$('progress').value = data.percent; status('import-status', data.message);}
      else if (data.type === 'complete') {await announceChange(); await refreshPack(); finish(); status('import-status', '导入完成。回到文章，选词即可查询。');}
      else if (data.type === 'error') {finish(); status('import-status', data.message + ' 原词典未被替换。', true);}
    } catch (error) {finish(); status('import-status', (error.message || '导入进程中断') + ' 原词典未被替换。', true);}
  };
  worker.onerror = event => {event.preventDefault(); finish(); status('import-status', '导入进程中断，原词典未被替换。请重新选择文件。', true);};
  worker.postMessage({file});
});
window.addEventListener('beforeunload', event => {if (busy) {event.preventDefault(); event.returnValue = '';}});
const preview = $('preview').attachShadow({mode:'open'});
let previewQuery;
async function search(query) {
  previewQuery = query;
  const token = ++querying; $('preview').hidden = false;
  const options = {theme:settings.theme === 'dark' ? 'dark' : 'light', onClose:() => {querying++; $('preview').hidden = true;}, onLookup:search, onImport:() => $('pack-file').click(), onOptions:() => {$('trigger').closest('.panel').scrollIntoView({block:'center'}); $('trigger').focus({preventScroll:true});}, onSearch: query => chrome.runtime.sendMessage({type:'google', query}).catch(() => {}), searchKey:settings.searchKey};
  FolioCard.mount(preview, {status:'loading', query}, options);
  try {const result = await chrome.runtime.sendMessage({type:'lookup', query}); if (token === querying) FolioCard.mount(preview, result, options);}
  catch {if (token === querying) FolioCard.mount(preview, {status:'error', query}, options);}
}
$('lookup-form').addEventListener('submit', event => {event.preventDefault(); void search($('query').value.trim());});
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local' || !changes.dictionaryRevision) return;
  // Preserve a name being edited in this tab; refresh the list when returning from another tab.
  if (!document.hasFocus()) void refreshPack();
  if (!$('preview').hidden && previewQuery) void search(previewQuery);
});
window.addEventListener('focus', () => {if (!document.activeElement?.closest('.dictionary-name-form')) void refreshPack();});
init().then(() => {const query = new URL(location).searchParams.get('q'); if (query) {$('query').value = query; void search(query);}}).catch(error => status('import-status', error.message, true));
