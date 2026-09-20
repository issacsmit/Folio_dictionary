import {lookupKeys, rankMatches, validQuery, RANK} from './core.js';
let connection;
export function openDB() {
  if (!connection) connection = new Promise((resolve, reject) => {
    const request = indexedDB.open('folio-dictionary', 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      db.createObjectStore('meta');
      const entries = db.createObjectStore('entries', {keyPath: ['generation', 'id']});
      entries.createIndex('parent', ['generation', 'parent.id']);
      entries.createIndex('forms', 'formKeys', {multiEntry:true});
      db.createObjectStore('lookup', {keyPath: ['generation', 'norm']});
    };
    request.onsuccess = () => { request.result.onversionchange = () => {request.result.close(); connection = null;}; resolve(request.result); };
    request.onerror = () => {connection = null; reject(request.error);};
  });
  return connection;
}
export const result = request => new Promise((resolve, reject) => {request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);});
export const complete = tx => new Promise((resolve, reject) => {tx.oncomplete = resolve; tx.onabort = () => reject(tx.error || new Error('写入已中断')); tx.onerror = () => {};});
export async function activePack() {const db = await openDB(); return result(db.transaction('meta').objectStore('meta').get('active'));}
// The existing active record is adopted on first access, without copying dictionary data.
async function changeLibrary(change) {
  const db = await openDB(), tx = db.transaction('meta', 'readwrite'), done = complete(tx);
  const meta = tx.objectStore('meta');
  const [saved, active] = await Promise.all([result(meta.get('library')), result(meta.get('active'))]);
  const state = {packs: saved || (active ? [active] : []), activeId: active?.id};
  try {change?.(state);} catch (error) {tx.abort(); await done.catch(() => {}); throw error;}
  meta.put(state.packs, 'library');
  const selected = state.packs.find(pack => pack.id === state.activeId);
  if (selected) meta.put(selected, 'active');
  await done; return state;
}
export const libraryState = () => changeLibrary();
// Metadata is already committed; a missed UI notification must not report a failed import.
export async function announceChange() {await chrome.storage.local.set({dictionaryRevision:crypto.randomUUID()}).catch(() => {});}
export async function registerPack(pack) {
  const state = await changeLibrary(state => {
    const index = state.packs.findIndex(item => item.id === pack.id);
    if (index >= 0) {pack.name = state.packs[index].name; state.packs[index] = pack;}
    else state.packs.push(pack);
    state.activeId = pack.id;
  });
  return state;
}
export async function selectPack(id) {
  const state = await changeLibrary(state => {
    if (!state.packs.some(pack => pack.id === id)) throw new Error('找不到这部词典。');
    state.activeId = id;
  });
  await announceChange(); return state;
}
export async function renamePack(id, name) {
  name = name.trim();
  if (!name || name.length > 80) throw new Error('词典名称需为 1–80 个字符。');
  const state = await changeLibrary(state => {
    const pack = state.packs.find(pack => pack.id === id);
    if (!pack) throw new Error('找不到这部词典。');
    pack.name = name;
  });
  await announceChange(); return state;
}
export async function writeBatch(store, rows) {
  const db = await openDB(), tx = db.transaction(store, 'readwrite'), done = complete(tx);
  for (const row of rows) tx.objectStore(store).add(row);
  await done;
}
export async function cleanupUnused() {
  const retained = new Set((await libraryState()).packs.map(pack => pack.generation));
  const db = await openDB();
  for (const name of ['entries', 'lookup']) {
    // Delete whole generation ranges, avoiding hundreds of thousands of cursor deletes.
    const read = db.transaction(name), cursor = read.objectStore(name).openKeyCursor();
    const generations = await new Promise((resolve, reject) => {
      const found = new Set();
      cursor.onsuccess = () => { const c = cursor.result; if (!c) return resolve([...found]); found.add(c.key[0]); c.continue([c.key[0] + '\u0000', '']); };
      cursor.onerror = () => reject(cursor.error);
    });
    for (const old of generations) if (!retained.has(old)) {
      const tx = db.transaction(name, 'readwrite'), done = complete(tx);
      tx.objectStore(name).delete(IDBKeyRange.bound([old, ''], [old, []])); await done;
    }
  }
}
export async function lookup(text) {
  if (!validQuery(text)) return {status: 'invalid', query: text};
  const db = await openDB();
  // One read transaction pins the active generation while replacement/cleanup runs.
  const tx = db.transaction(['meta', 'entries', 'lookup']);
  const pack = await result(tx.objectStore('meta').get('active'));
  if (!pack) return {status: 'no-dictionary', query: text};
  const index = tx.objectStore('lookup'), entries = tx.objectStore('entries');
  const keys = lookupKeys(text);
  const [rows, forms] = await Promise.all([
    Promise.all(keys.map(key => result(index.get([pack.generation, key])))),
    Promise.all(keys.map(key => result(entries.index('forms').getAll(IDBKeyRange.only([pack.generation, key])))))
  ]);
  const ranked = rankMatches(text, [...rows.flatMap(row => row?.matches || []), ...forms.flat().map(entry => ({entry_id:entry.id,headword:entry.headword,match:'inflection'}))]);
  const groups = new Map();
  for (const m of ranked) {
    if (!groups.has(m.entry_id)) groups.set(m.entry_id, {match: m.match, ids: new Set(), whole: false});
    const group = groups.get(m.entry_id);
    if ((RANK[m.match] ?? 8) < 6 || !m.sense_id) group.whole = true;
    else group.ids.add(m.sense_id);
  }
  const all = [...groups], selected = all.slice(0, 24);
  const found = await Promise.all(selected.map(async ([id, group]) => {
    const entry = await result(entries.get([pack.generation, id]));
    if (!entry) return null;
    const children = await result(entries.index('parent').getAll(IDBKeyRange.only([pack.generation, id])));
    return {entry, match: group.match, senseIds: group.whole ? [] : [...group.ids], related: children.filter(e => e.kind === 'phrasal_verb')};
  }));
  return {status: found.some(Boolean) ? 'ok' : 'not-found', query: text, source: pack.name, generation:pack.generation, results: found.filter(Boolean), omitted: Math.max(0, all.length - selected.length)};
}
