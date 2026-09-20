(() => {
  'use strict';
  let settings = {trigger:'Alt', searchKey:'Enter', theme:'auto', enabled:true};
  let host, root, card, range, sequence = 0, resizeObserver, currentData;
  const media = matchMedia('(prefers-color-scheme: dark)');
  addEventListener('unhandledrejection', event => {
    const text = String(event.reason?.message || event.reason || '');
    if (text.includes('Extension context invalidated') || text.includes('message port closed')) event.preventDefault();
  });
  try {
    chrome.storage.local.get('settings').then(value => Object.assign(settings, value.settings || {})).catch(() => {});
    chrome.storage.onChanged.addListener((changes, area) => {if (area === 'local' && changes.settings) {settings = {...settings, ...changes.settings.newValue}; close();}});
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== 'local' || !changes.dictionaryRevision || !host || !currentData?.query) return;
      const request = sequence;
      Promise.resolve().then(() => chrome.runtime.sendMessage({type:'status'})).then(({pack} = {}) => {
        if (request !== sequence || !host) return;
        if (pack?.generation === currentData.generation) {
          currentData.source = pack.name;
          const source = card.querySelector('.source');
          if (source) {source.textContent = pack.name; source.title = pack.name;}
        } else void lookup(currentData.query);
      }).catch(() => {});
    });
  } catch {}
  function close() {sequence++; resizeObserver?.disconnect(); card?.dispose?.(); host?.remove(); host = root = card = range = null;}
  function connected() {try {return Boolean(chrome.runtime?.id);} catch {return false;}}
  function matchesShortcut(event, name) {
    if (!name) return false;
    const key = event.key === ' ' ? 'Space' : event.key === 'Control' ? 'Ctrl' : event.key.length === 1 ? event.key.toLowerCase() : event.key;
    if (key !== name) return false;
    return !((event.altKey && name !== 'Alt') || (event.ctrlKey && name !== 'Ctrl') || (event.metaKey && name !== 'Meta') || (event.shiftKey && name !== 'Shift'));
  }
  function showConnectionError(query) {
    const extensionUnavailable = !connected();
    render({status:'error', query, extensionUnavailable, error:extensionUnavailable ? 'Folio 已更新，请刷新此网页后继续查词。' : 'Folio 暂时无法连接，请刷新网页后再试。'});
  }
  async function openOptions() {
    try {
      if (!connected()) {sequence++; showConnectionError(currentData?.query); return;}
      await chrome.runtime.sendMessage({type:'options'});
    } catch {if (host) {sequence++; showConnectionError(currentData?.query);}}
  }
  function editable(event) {return event.composedPath().some(n => n instanceof Element && (n.matches('input,textarea,select,button,a,[role="textbox"],[role="combobox"]') || n.isContentEditable));}
  function valid(text) {return text.length <= 160 && /[a-zA-Z]/.test(text) && text.split(/\s+/).length <= 12 && !/[\r\n<>]/.test(text);}
  function theme() {
    if (settings.theme !== 'auto') return settings.theme;
    // Follow the reading surface, falling back to the system for transparent pages.
    let node = range?.commonAncestorContainer; node = node?.nodeType === 1 ? node : node?.parentElement;
    for (; node instanceof Element; node = node.parentElement) {
      const color = getComputedStyle(node).backgroundColor.match(/[\d.]+/g)?.map(Number);
      if (color?.length >= 3 && (color.length < 4 || color[3] >= .8)) return .2126 * color[0] + .7152 * color[1] + .0722 * color[2] < 120 ? 'dark' : 'light';
    }
    return media.matches ? 'dark' : 'light';
  }
  function position() {
    if (!host || !card || !range) return;
    if (!range.commonAncestorContainer.isConnected) return close();
    const anchor = range.getBoundingClientRect(), viewport = window.visualViewport;
    const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0, width = viewport?.width || innerWidth, height = viewport?.height || innerHeight;
    if (anchor.bottom < top || anchor.top > top + height || anchor.right < left || anchor.left > left + width) return close();
    const below = top + height - anchor.bottom - 12, above = anchor.top - top - 12;
    const contentHeight = (card.querySelector('.scrollport')?.scrollHeight || card.scrollHeight) + 18 + (card.querySelector('.footer')?.offsetHeight || 0);
    const upward = below < Math.min(contentHeight, 340) && above > below;
    card.style.maxHeight = Math.max(100, Math.min(height - 24, upward ? above : below)) + 'px';
    card.style.maxWidth = Math.max(120, width - 24) + 'px';
    const bounds = card.getBoundingClientRect();
    const x = Math.max(left + 12, Math.min(anchor.left - 16, left + width - bounds.width - 12));
    const y = Math.max(top + 12, Math.min(upward ? anchor.top - bounds.height - 9 : anchor.bottom + 9, top + height - bounds.height - 12));
    host.style.setProperty('left', x + 'px', 'important'); host.style.setProperty('top', y + 'px', 'important');
  }
  function render(data) {
    currentData = data;
    if (!host) {
      host = document.createElement('folio-dictionary');
      for (const [key, value] of Object.entries({all:'initial', position:'fixed', display:'block', margin:'0', padding:'0', border:'0', width:'max-content', height:'auto', 'z-index':'2147483647', 'color-scheme':'normal', 'text-align':'left'})) host.style.setProperty(key, value, 'important');
      root = host.attachShadow({mode:'open'}); document.documentElement.append(host);
      root.addEventListener('keydown', event => {if (event.key === 'Escape') {event.preventDefault(); close();}});
    }
    resizeObserver?.disconnect();
    card = FolioCard.mount(root, data, {theme:theme(), onClose:close, onLookup:lookup, onOptions:openOptions, onSearch:openGoogle, searchKey:settings.searchKey});
    position();
    if (!card) return; // Positioning may dismiss a selection that has moved out of view.
    resizeObserver = new ResizeObserver(position); resizeObserver.observe(card);
  }
  async function openGoogle(query) {
    try {
      if (!connected()) {showConnectionError(query); return;}
      await chrome.runtime.sendMessage({type:'google', query});
    } catch {if (host) showConnectionError(query);}
  }
  async function lookup(query) {
    const request = ++sequence;
    try {
      if (!connected()) {showConnectionError(query); return;}
      render({status:'loading', query});
      const data = await chrome.runtime.sendMessage({type:'lookup', query});
      if (request !== sequence || !host) return;
      render(data || {status:'error', query});
    } catch {if (request === sequence && host) showConnectionError(query);}
  }
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && host) {event.preventDefault(); close(); return;}
    if (!event.isTrusted || event.repeat || event.isComposing) return;
    if (host && currentData?.status === 'not-found' && !currentData.extensionUnavailable && matchesShortcut(event, settings.searchKey) && !editable(event)) {
      event.preventDefault(); void openGoogle(currentData.query); return;
    }
    if (event.defaultPrevented || !settings.enabled || editable(event) || event.composedPath().includes(host) || !matchesShortcut(event, settings.trigger)) return;
    const selection = getSelection(), text = selection?.toString().trim();
    if (!text || !selection.rangeCount || !valid(text)) return;
    const selectedRange = selection.getRangeAt(0).cloneRange();
    const element = selectedRange.commonAncestorContainer.nodeType === 1 ? selectedRange.commonAncestorContainer : selectedRange.commonAncestorContainer.parentElement;
    if (element?.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"])')) return;
    const rect = selectedRange.getBoundingClientRect(); if (!rect.width && !rect.height) return;
    event.preventDefault(); close(); range = selectedRange; void lookup(text);
  }, true);
  document.addEventListener('pointerdown', event => {if (host && !event.composedPath().includes(host)) close();}, true);
  window.addEventListener('scroll', event => {if (host && !event.composedPath().includes(host)) position();}, true);
  window.addEventListener('resize', position);
  window.visualViewport?.addEventListener('resize', position);
  window.visualViewport?.addEventListener('scroll', position);
  window.addEventListener('pagehide', close);
})();
