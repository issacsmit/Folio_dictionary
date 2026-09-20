import {lookup, activePack} from '/lib/db.js';
import {cleanSettings, validQuery} from '/lib/core.js';
addEventListener('unhandledrejection', event => {
  const text = String(event.reason?.message || event.reason || '');
  if (text.includes('Extension context invalidated') || text.includes('message port closed')) event.preventDefault();
});
chrome.runtime.onMessage.addListener((message, sender) => {
  if (sender.id !== chrome.runtime.id) return;
  return (async () => {
    switch (message?.type) {
      case 'lookup': return lookup(message.query);
      case 'status': return {pack: await activePack(), settings: cleanSettings((await chrome.storage.local.get('settings')).settings)};
      case 'options': await chrome.runtime.openOptionsPage(); return {ok: true};
      case 'google':
        if (!validQuery(message.query)) return {error: '未知请求'};
        await chrome.tabs.create({url: 'https://www.google.com/search?q=' + encodeURIComponent(message.query.trim())});
        return {ok: true};
      default: return {error: '未知请求'};
    }
  })().catch(error => ({status: 'error', error: error.message || '查询暂时不可用'}));
});
