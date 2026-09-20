import {readZip, verifyHash, jsonLines} from './zip.js';
import {validateEntry, validateManifest, validateLookup} from './validate.js';
import {registerPack, writeBatch, cleanupUnused} from './db.js';
import {explicitInflections} from './core.js';

export async function importPack(file, progress = () => {}) {
  return navigator.locks.request('folio-import', {ifAvailable: true}, async lock => {
    if (!lock) throw new Error('另一页正在导入词典，请稍后再试。');
    const generation = crypto.randomUUID();
    await cleanupUnused();
    let activated = false;
    try {
      progress({percent: 1, message: '正在读取词典包…'});
      const zip = await readZip(file);
      const manifest = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(await zip.read('manifest.json')));
      validateManifest(manifest);
      const entryIds = new Map(), parents = []; let count = 0, batch = [];
      let bytes = await zip.read('entries.jsonl');
      await verifyHash(bytes, manifest.checksums['entries.jsonl'], 'entries.jsonl');
      for await (const entry of jsonLines(bytes)) {
        if (entryIds.has(entry.id)) throw new Error('发现重复词条编号：' + entry.id);
        entryIds.set(entry.id, validateEntry(entry));
        if (entry.parent) parents.push(entry.parent.id);
        batch.push({...entry, generation, formKeys:explicitInflections(entry).map(key => [generation, key])}); count++;
        if (count > manifest.counts.entries) throw new Error('词条数量超过声明值。');
        if (batch.length >= 400) {await writeBatch('entries', batch); batch = []; progress({percent: 5 + Math.round(35 * count / manifest.counts.entries), message: `正在整理词条 ${count.toLocaleString()} / ${manifest.counts.entries.toLocaleString()}`});}
      }
      if (count !== manifest.counts.entries) throw new Error('词条数量与清单不符。');
      if (batch.length) await writeBatch('entries', batch);
      for (const id of parents) if (!entryIds.has(id)) throw new Error('词典含失效的关联词条。');
      bytes = null; batch = []; count = 0;
      bytes = await zip.read('lookup.jsonl');
      await verifyHash(bytes, manifest.checksums['lookup.jsonl'], 'lookup.jsonl');
      for await (const row of jsonLines(bytes)) {
        validateLookup(row, entryIds); batch.push({...row, generation}); count++;
        if (count > manifest.counts.lookup_keys) throw new Error('查询键数量超过声明值。');
        if (batch.length >= 800) {await writeBatch('lookup', batch); batch = []; progress({percent: 40 + Math.round(55 * count / manifest.counts.lookup_keys), message: `正在建立索引 ${count.toLocaleString()} / ${manifest.counts.lookup_keys.toLocaleString()}`});}
      }
      if (count !== manifest.counts.lookup_keys) throw new Error('查询键数量与清单不符。');
      if (batch.length) await writeBatch('lookup', batch);
      const pack = {generation, id: manifest.pack_id, name: manifest.source.name, entries: manifest.counts.entries, keys: count, importedAt: new Date().toISOString(), bytes: file.size};
      await registerPack(pack); activated = true;
      // A cleanup failure cannot turn an already successful activation into a failed import.
      await cleanupUnused().catch(() => {});
      progress({percent: 100, message: '词典已就绪。回到文章，选词即可查询。'}); return pack;
    } catch (error) {
      if (!activated) await cleanupUnused().catch(() => {});
      if (error.name === 'QuotaExceededError') throw new Error('磁盘空间不足。原来的词典仍然可用。');
      throw error;
    }
  });
}
