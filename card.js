(() => {
  'use strict';
  // Resolve once while the extension context is alive; rendering an update notice
  // must remain possible after Chrome invalidates APIs in an already-open page.
  let artworkUrl = '';
  try {artworkUrl = chrome.runtime.getURL('icons/256.png');} catch {}
  const css = `
  :host{color-scheme:light;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}
  *{box-sizing:border-box} [hidden]{display:none!important}
  .card{--paper:#fcf9f2;--ink:#39362f;--muted:#7d7260;--line:#e8e0d2;--accent:#8d6d39;--control:#f1ebdf;--scroll-thumb:#978b7666;--scroll-hover:#978b76a6;color:var(--ink);background:var(--paper);border:1px solid #e7ddcb;border-radius:18px;width:386px;max-width:calc(100vw - 24px);max-height:calc(100dvh - 24px);display:flex;flex-direction:column;overflow:hidden;box-shadow:0 14px 44px #49371c1c,0 3px 10px #49371c0a;font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;position:relative;text-align:left;direction:ltr;letter-spacing:normal;animation:folio-in .16s ease-out}
  .card.dark{color-scheme:dark;--paper:#302e27;--ink:#f0eadd;--muted:#bcb09a;--line:#494438;--accent:#d4bd91;--control:#423d31;--scroll-thumb:#c4b79c66;--scroll-hover:#c4b79ca6;border-color:#494438;box-shadow:0 16px 42px #0005}
  .scrollport{--scroll-visibility:0;min-height:0;margin:8px 1px;overflow-x:hidden;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:auto;scrollbar-color:auto;outline:none}
  .scrollport:focus-visible{outline:1px solid var(--accent);outline-offset:-2px;border-radius:10px}
  .scrollport::-webkit-scrollbar{width:3px}
  .scrollport::-webkit-scrollbar-track{background:transparent}
  .scrollport::-webkit-scrollbar-thumb{background:rgb(151 139 118 / calc(.45 * var(--scroll-visibility)));border:0;border-radius:999px;min-height:28px}
  .dark .scrollport::-webkit-scrollbar-thumb{background:rgb(196 183 156 / calc(.45 * var(--scroll-visibility)))}
  .scrollport::-webkit-scrollbar-button{display:none;width:0;height:0}
  .scrollport::-webkit-scrollbar-corner{background:transparent}
  .scrollport>.main{padding:17px 26px 21px}.scrollport>.footer{padding:11px 26px 3px}
  .card>.footer{flex-shrink:0}.footer .source{flex:1;min-width:0}.footer-actions{display:flex;align-items:center;gap:10px;flex-shrink:0;white-space:nowrap}.settings-link{display:grid;place-items:center;width:28px;height:28px;padding:5px;border-radius:6px;color:var(--muted)}.settings-link:hover{background:var(--line);color:var(--ink)}
  @keyframes folio-in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
  button{font:inherit;cursor:pointer;color:inherit}button:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}button{border:0;background:transparent;border-radius:6px}button:hover{background:var(--control)}
  .close{position:absolute;right:14px;top:14px;width:28px;height:28px;padding:0;color:var(--muted);font-size:22px;line-height:1}
  .main{padding:25px 27px 21px}.eyebrow{font-size:10px;letter-spacing:.14em;color:var(--muted);margin:0 30px 13px 0}.word{font:400 32px/1.2 Georgia,"Times New Roman",serif;letter-spacing:-.9px;margin:0;padding:0 20px 0 0;overflow-wrap:anywhere}.word sup{font:12px/1 sans-serif;vertical-align:super;letter-spacing:0;margin-left:3px}
  .eyebrow{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:28px;margin-bottom:9px}.eyebrow>span:last-child{text-align:right;letter-spacing:normal}.brand-mark{display:block;position:relative;width:28px;height:28px;overflow:hidden;flex-shrink:0;mix-blend-mode:multiply;opacity:.78;pointer-events:none}.brand-mark img{display:block;position:absolute;width:65.88px;height:65.88px;max-width:none;left:-18.53px;top:-17.29px;filter:brightness(1.08)}.dark .brand-mark{mix-blend-mode:screen;opacity:.8}.dark .brand-mark img{filter:brightness(1.08) grayscale(1) invert(1)}
  .phonetic{font:12px/1.8 "Segoe UI",Arial,sans-serif;color:var(--muted);margin:9px 0 0;display:flex;gap:12px;flex-wrap:wrap}.phonetic b{font-weight:400;font-size:10px;margin-right:4px}.query-note,.hint{font-size:12px;line-height:1.8;color:var(--muted);margin:12px 0 0}
  .entry+.entry{margin-top:23px;border-top:1px solid var(--line);padding-top:22px}.definitions{margin:21px 0 0}.definition{display:grid;grid-template-columns:22px minmax(0,1fr);gap:8px;margin:14px 0}.number{font:italic 13px/1.8 Georgia,serif;color:var(--muted);padding-top:3px}.pos{font:italic 12px/1.6 Georgia,serif;color:var(--muted);margin-bottom:3px}.meaning{font-size:15px;line-height:1.8;overflow-wrap:anywhere}.labels{font-size:11px;line-height:1.8;color:var(--muted);margin-bottom:4px}.signpost{font-size:12px;font-weight:600;margin-bottom:4px}.patterns{font:13px/1.7 Georgia,serif;color:var(--muted);margin-top:5px}.english-only{display:block;font-size:10px;color:var(--muted);margin:0 0 3px}
  details{margin-top:8px}summary{color:var(--accent);font-size:12px;cursor:pointer;list-style:none;width:fit-content;border-radius:4px}summary::-webkit-details-marker{display:none}summary:after{content:' ＋'}details[open]>summary:after{content:' −'}.english{font:13px/1.7 Georgia,serif;color:var(--muted);margin-top:5px}.nested{border-left:1px solid var(--line);margin:10px 0;padding-left:12px}.nested .definition{grid-template-columns:16px minmax(0,1fr);gap:5px}.more{margin-top:12px}
  .phrases{border-top:1px solid var(--line);padding-top:17px;margin-top:22px}.section-label{font-size:10px;letter-spacing:.07em;color:var(--muted);margin-bottom:9px}.phrase{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:14px;padding:10px 0;align-items:baseline}.phrase+.phrase{border-top:1px solid var(--line)}.phrase-word{font:15px/1.6 Georgia,serif;text-align:left;padding:0;color:var(--ink);overflow-wrap:anywhere}.phrase-definition{font-size:12px;line-height:1.8;color:var(--muted);overflow-wrap:anywhere}.text-button{color:var(--accent);padding:2px 0;font-size:12px;text-align:left}.notice{font-size:14px;line-height:1.9;margin:18px 0 12px}.footer{border-top:1px solid var(--line);padding:11px 27px;display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:10px;color:var(--muted)}.source{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:230px}kbd{font:10px/1.4 inherit;border:1px solid var(--line);padding:1px 4px;border-radius:4px}
  @media(prefers-reduced-motion:reduce){.card{animation:none}}
  `;
  function el(tag, cls, text) {const node = document.createElement(tag); if (cls) node.className = cls; if (text != null) node.textContent = text; return node;}
  function transientScrollbar(scrollport) {
    let timer, frame;
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    function hide() {
      if (!scrollport.isConnected) return;
      // Keep a native thumb visible while it is being held, including a pause in dragging.
      if (scrollport.matches(':active')) {timer = setTimeout(hide, 100); return;}
      const start = performance.now();
      function fade(now) {
        if (!scrollport.isConnected) return;
        const alpha = reducedMotion.matches ? 0 : Math.max(0, 1 - (now - start) / 180);
        scrollport.style.setProperty('--scroll-visibility', String(alpha));
        if (alpha > 0) frame = requestAnimationFrame(fade);
        else delete scrollport.dataset.scrolling;
      }
      frame = requestAnimationFrame(fade);
    }
    function show() {
      clearTimeout(timer); cancelAnimationFrame(frame);
      if (scrollport.scrollHeight <= scrollport.clientHeight) return;
      scrollport.dataset.scrolling = 'true';
      scrollport.style.setProperty('--scroll-visibility', '1');
      timer = setTimeout(hide, 650);
    }
    scrollport.addEventListener('scroll', show, {passive:true});
    return () => {clearTimeout(timer); cancelAnimationFrame(frame); scrollport.removeEventListener('scroll', show);};
  }
  function button(text, cls, action) {const node = el('button', cls, text); node.type = 'button'; node.addEventListener('click', action); return node;}
  function details(label, content, cls = '') {const box = el('details', cls); box.append(el('summary', '', label), content); return box;}
  const definition = d => d?.zh || d?.en || '';
  const posNames = {noun:'n.', verb:'v.', adjective:'adj.', adverb:'adv.', preposition:'prep.', pronoun:'pron.', conjunction:'conj.', determiner:'determiner', interjection:'interj.', 'auxiliary verb':'aux.'};
  const grammarNames = {intransitive:'不及物',transitive:'及物',countable:'可数',uncountable:'不可数',singular:'单数',plural:'复数','only before noun':'仅用于名词前','not before noun':'不用于名词前'};
  function labels(...sets) {return [...new Set(sets.flatMap(s => s || []).map(x => typeof x === 'string' ? x : x.value).filter(Boolean))].map(x=>grammarNames[x] || x).join(' · ');}
  function contains(s, ids) {return ids.includes(s.id) || (s.senses || []).some(child => contains(child, ids));}
  function referenceNode(refs, onLookup) {
    const node = el('div', 'hint'); node.append(document.createTextNode('参见 · '));
    for (const [i, ref] of refs.entries()) {
      if (i) node.append(document.createTextNode('；'));
      if (/^[a-zA-Z][a-zA-Z\s.'’\-]{0,100}$/.test(ref.text)) node.append(button(ref.text, 'text-button', () => onLookup(ref.text)));
      else node.append(document.createTextNode(ref.text));
    }
    return node;
  }
  function senseNode(s, group, ids, index, onLookup, force = false) {
    const whole = force || !ids.length || ids.includes(s.id);
    if (!whole && !contains(s, ids)) return null;
    const row = el('div', 'definition'), body = el('div');
    row.append(el('span', 'number', s.number || String(index + 1).padStart(2, '0')), body);
    const pos = (group.pos || []).map(x => posNames[x] || x).join(' / ');
    const grammar = labels(group.grammar, s.grammar);
    body.append(el('div', 'pos', pos + (grammar ? '  ·  ' + grammar : '')));
    const restrictions = labels(group.labels, s.labels);
    if (restrictions) body.append(el('div', 'labels', restrictions));
    if (definition(s.signpost)) body.append(el('div', 'signpost', definition(s.signpost)));
    if (whole) {
      if (definition(s.definition)) {
        if (!s.definition.zh) body.append(el('span', 'english-only', '英文释义'));
        body.append(el('div', 'meaning', definition(s.definition)));
        if (s.definition.zh && s.definition.en) body.append(details('英文原释义', el('div', 'english', s.definition.en)));
      }
      const patterns = [...new Set([...(s.lexunits || []), ...(s.patterns || [])])];
      if (patterns.length) body.append(el('div', 'patterns', patterns.join(' / ')));
      if (s.cross_refs?.length) body.append(referenceNode(s.cross_refs, onLookup));
    }
    const children = el('div', 'nested');
    for (const [i, child] of (s.senses || []).entries()) {const node = senseNode(child, group, ids, i, onLookup, whole); if (node) children.append(node);}
    if (children.childElementCount) body.append(children);
    return row;
  }
  function firstDefinition(entry) {
    function find(senses) {for (const s of senses) {if (definition(s.definition)) return s.definition; const nested = find(s.senses || []); if (nested) return nested;}}
    for (const g of entry.pos_groups || []) {const found = find(g.senses || []); if (found) return found;} return null;
  }
  function phraseRows(result) {
    const phrases = [...(result.entry.phrases || [])];
    function collect(s) {
      phrases.push(...(s.phrases || []));
      for (const text of [...(s.lexunits || []), ...(s.patterns || [])]) if (definition(s.definition)) phrases.push({text, definition:s.definition});
      for (const child of s.senses || []) collect(child);
    }
    for (const group of result.entry.pos_groups || []) for (const s of group.senses || []) collect(s);
    for (const child of result.related || []) phrases.push({text: child.headword, definition: firstDefinition(child)});
    const seen = new Set();
    return phrases.filter(p => {const key = p.text?.toLowerCase(); if (!key || seen.has(key) || !definition(p.definition)) return false; seen.add(key); return true;});
  }
  function entryNode(result, query, onLookup) {
    const {entry, senseIds = []} = result, box = el('section', 'entry');
    const title = el('h2', 'word', entry.display || entry.headword);
    if (entry.homograph) title.append(el('sup', '', entry.homograph)); box.append(title);
    const pronunciations = el('div', 'phonetic');
    for (const p of entry.pronunciations || []) {const item = el('span'); item.append(el('b', '', {br:'英', us:'美'}[p.accent] || ''), document.createTextNode('/' + p.ipa.replace(/^\/|\/$/g, '') + '/')); pronunciations.append(item);}
    if (pronunciations.childElementCount) box.append(pronunciations);
    if (query.toLowerCase() !== entry.headword.toLowerCase()) box.append(el('div', 'query-note', query + ' → ' + entry.headword));
    const senses = el('div', 'definitions'), extra = el('div'); let count = 0;
    for (const group of entry.pos_groups || []) for (const [index, s] of (group.senses || []).entries()) {
      const node = senseNode(s, group, senseIds, index, onLookup); if (!node) continue;
      (count++ < 2 ? senses : extra).append(node);
    }
    if (extra.childElementCount) senses.append(details(`更多释义（${extra.childElementCount}）`, extra, 'more'));
    if (count) box.append(senses);
    else {
      box.append(el('div', 'pos query-note', (entry.pos_groups || []).flatMap(g => g.pos || []).map(p => posNames[p] || p).join(' / ')));
      box.append(el('p', 'hint', entry.parent ? '本词在词典中作为派生词收录，没有独立释义。' : '此条目未列出独立释义，请参考词典中的参见信息。'));
    }
    if (entry.parent) box.append(button('关联词条 · ' + entry.parent.headword, 'text-button', () => onLookup(entry.parent.headword)));
    if (entry.cross_refs?.length) box.append(referenceNode(entry.cross_refs, onLookup));
    const phrases = senseIds.length ? [] : phraseRows(result);
    if (phrases.length) {
      const section = el('div', 'phrases'); section.append(el('div', 'section-label', '词组与搭配 / PHRASES'));
      const more = el('div');
      for (const [i, p] of phrases.entries()) {const row = el('div', 'phrase'); row.append(button(p.text, 'phrase-word', () => onLookup(p.text)), el('span', 'phrase-definition', definition(p.definition))); (i < 3 ? section : more).append(row);}
      if (more.childElementCount) section.append(details(`更多词组（${more.childElementCount}）`, more)); box.append(section);
    }
    return box;
  }
  globalThis.FolioCard = {
    mount(root, data, {theme = 'light', onClose = () => {}, onLookup = () => {}, onOptions = () => {}, onImport = onOptions, onSearch, searchKey = 'Enter'} = {}) {
      root.querySelector('.card')?.dispose?.();
      root.replaceChildren(); const style = el('style', '', css); root.append(style);
      const card = el('section', 'card' + (theme === 'dark' ? ' dark' : '')); card.setAttribute('role', 'dialog'); card.setAttribute('aria-label', 'Folio 词典 · ' + (data.query || '')); card.tabIndex = -1;
      const close = button('×', 'close', onClose); close.setAttribute('aria-label', '关闭词典'); card.append(close);
      const main = el('div', 'main'), eyebrow = el('div', 'eyebrow');
      const mark = el('span', 'brand-mark'); mark.setAttribute('aria-hidden', 'true');
      if (artworkUrl && !data.extensionUnavailable) {
        const artwork = el('img'); artwork.src = artworkUrl; artwork.alt = ''; artwork.width = 80; artwork.height = 80; artwork.draggable = false;
        mark.append(artwork);
      }
      eyebrow.append(mark, el('span', '', 'Folio · 英汉词典')); main.append(eyebrow);
      if (data.status === 'ok') {
        const primary = data.results[0]?.entry.headword, related = el('div'), relatedNames = new Set();
        for (const r of data.results) {
          if (r.entry.headword === primary) main.append(entryNode(r, data.query, onLookup));
          else {related.append(entryNode(r, data.query, onLookup)); relatedNames.add(r.entry.headword);}
        }
        if (related.childElementCount) main.append(details('相关词条 · ' + [...relatedNames].slice(0, 3).join(' / ') + (relatedNames.size > 3 ? ' …' : ''), related, 'phrases'));
        if (data.omitted) main.append(el('p', 'hint', `还有 ${data.omitted} 个匹配，请选择更具体的词组查询。`));
      } else {
        main.append(el('h2', 'word', data.query || 'Folio'));
        const messages = {loading:'正在翻阅词典…', 'no-dictionary':'先导入一本词典，让 Folio 陪你阅读。', 'not-found':'词典未收录这个词。可以检查拼写，或选中完整词组再试。', invalid:'请选择一个英文单词或简短词组。', error:data.error || '查询暂时不可用，请刷新网页后再试。'};
        const notice = el('p', 'notice', messages[data.status] || messages.error); notice.setAttribute('role', 'status'); main.append(notice);
        if (data.status === 'no-dictionary') main.append(button('导入本地词典 →', 'text-button', onImport));
        if (data.status === 'not-found' && typeof onSearch === 'function') {
          main.append(button('用 Google 搜索 →', 'text-button', () => onSearch(data.query)));
          const hint = el('p', 'hint');
          hint.append(document.createTextNode('按 '), el('kbd', '', searchKey), document.createTextNode(' 也可搜索'));
          main.append(hint);
        }
      }
      const footer = el('footer', 'footer'), source = el('span', 'source', data.source || '本地词典 · 离线查询'); source.title = data.source || '';
      const settings = button('', 'settings-link', onOptions); settings.setAttribute('aria-label', '打开 Folio 设置'); settings.title = '词典与设置';
      if (data.extensionUnavailable) {settings.disabled = true; settings.title = '刷新网页后可打开设置';}
      const gear = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      gear.setAttribute('viewBox', '0 0 24 24'); gear.setAttribute('width', '16'); gear.setAttribute('height', '16'); gear.setAttribute('fill', 'none'); gear.setAttribute('stroke', 'currentColor'); gear.setAttribute('stroke-width', '1.5'); gear.setAttribute('stroke-linejoin', 'round'); gear.setAttribute('aria-hidden', 'true');
      const outline = document.createElementNS(gear.namespaceURI, 'path');
      outline.setAttribute('d', 'M9.5 3h5l.6 2.5 1.4.8 2.5-.7 2.5 4.3-1.9 1.8v1.6l1.9 1.8-2.5 4.3-2.5-.7-1.4.8-.6 2.5h-5l-.6-2.5-1.4-.8-2.5.7L2.5 15l1.9-1.8v-1.6L2.5 9.8 5 5.5l2.5.7 1.4-.8Z');
      const center = document.createElementNS(gear.namespaceURI, 'circle'); center.setAttribute('cx', '12'); center.setAttribute('cy', '12'); center.setAttribute('r', '3');
      gear.append(outline, center); settings.append(gear);
      const dismiss = el('span'); dismiss.append(el('kbd', '', 'esc'), document.createTextNode(' 收起'));
      const actions = el('span', 'footer-actions'); actions.append(settings, dismiss); footer.append(source, actions);
      const scrollport = el('div', 'scrollport'); scrollport.tabIndex = 0; scrollport.setAttribute('role', 'region'); scrollport.setAttribute('aria-label', '词条内容');
      scrollport.append(main); card.append(scrollport, footer); root.append(card);
      card.dispose = transientScrollbar(scrollport); return card;
    }
  };
})();
