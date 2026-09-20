const $ = id => document.getElementById(id);
function refresh() {return chrome.runtime.sendMessage({type:'status'}).then(({pack, settings}) => {
  $('key').textContent = settings.trigger; $('state').textContent = pack ? pack.name : '还没有导入词典';
  $('meta').textContent = settings.enabled ? pack ? `${pack.entries.toLocaleString()} 个词条 · 离线可用` : '从本地选择 Folio 词典包即可开始。' : '网页查词已暂停，可在设置中开启。';
}).catch(() => {$('state').textContent = '暂时无法读取词典，请重新打开。';});}
void refresh();
chrome.storage.onChanged.addListener((changes, area) => {if (area === 'local' && (changes.dictionaryRevision || changes.settings)) void refresh();});
$('options').addEventListener('click', () => {void chrome.runtime.openOptionsPage().catch(() => {});});
$('search').addEventListener('submit', event => {event.preventDefault(); void chrome.tabs.create({url:chrome.runtime.getURL('options.html') + '?q=' + encodeURIComponent($('query').value.trim())}).catch(() => {});});
