import test from 'node:test';
import assert from 'node:assert/strict';
import {fold, lookupKeys, rankMatches, validQuery, cleanSettings, explicitInflections, normalizeShortcut, shortcutFromEvent} from '../lib/core.js';
import {validateEntry, validateLookup} from '../lib/validate.js';
import {readZip, verifyHash, jsonLines} from '../lib/zip.js';
import {deflateRawSync} from 'node:zlib';

test('lookup keeps abbreviation periods, folds punctuation and inflection keys without stemming', () => {
  assert.deepEqual(lookupKeys('U.'), ['u.', 'u']); assert.deepEqual(lookupKeys('run.'), ['run.', 'run']);
  assert.equal(fold('  Someone’s\u00a0well‑being  '), "someone's well-being");
  assert.equal(fold('ＳＴＵＤＩＥＳ'), 'studies'); assert.equal(fold('Straße'), 'strasse');
});
test('exact abbreviation outranks a bare-letter match', () => {
  const matches = [{headword:'U',match:'headword'},{headword:'U.',match:'headword'}];
  assert.equal(rankMatches('U.', matches)[0].headword, 'U.'); assert.equal(rankMatches('U', matches)[0].headword, 'U');
});
test('source-recorded inflections are indexed without guessing suffixes', () => {
  assert.deepEqual(explicitInflections({headword:'run',inflections:[{form:'past tense ran'},{form:', past participle run'},{form:', present participle running'}]}),['ran','running']);
  assert.deepEqual(explicitInflections({headword:'make',inflections:[{form:'past tense and past participle made'},{form:'unsupported text (with notes)'}]}),['made']);
});
test('queries stay bounded; invalid settings use safe defaults', () => {
  assert.ok(validQuery('run out of')); assert.ok(!validQuery('a'.repeat(161))); assert.ok(!validQuery('<script>'));
  assert.ok(!validQuery('line\nbreak')); assert.ok(!validQuery('中文'));
  assert.deepEqual(cleanSettings({trigger:'Escape',theme:'other',enabled:false}), {trigger:'Alt',searchKey:'Enter',theme:'auto',enabled:false});
  assert.deepEqual(cleanSettings({}), {trigger:'Alt',searchKey:'Enter',theme:'auto',enabled:true});
  assert.equal(cleanSettings({trigger:'Enter'}).trigger, 'Enter');
  assert.equal(cleanSettings({trigger:'Control',searchKey:'g'}).trigger, 'Ctrl');
  assert.equal(cleanSettings({searchKey:'???'}).searchKey, 'Enter');
});
test('shortcuts accept Alt, named keys and single characters, and ignore Tab/Escape', () => {
  assert.equal(normalizeShortcut('alt'), 'Alt');
  assert.equal(normalizeShortcut('Control'), 'Ctrl');
  assert.equal(normalizeShortcut(' '), 'Space');
  assert.equal(normalizeShortcut('F12'), 'F12');
  assert.equal(shortcutFromEvent({key:'Alt'}), 'Alt');
  assert.equal(shortcutFromEvent({key:'Enter'}), 'Enter');
  assert.equal(shortcutFromEvent({key:'d'}), 'd');
  assert.equal(shortcutFromEvent({key:'Escape'}), '');
  assert.equal(shortcutFromEvent({key:'Tab'}), '');
});
test('validator retains nested English-only senses and rejects dangling references', () => {
  const entry = {id:'e',kind:'word',headword:'test',pos_groups:[{pos:['noun'],senses:[{id:'s',definition:{en:null,zh:null},senses:[{id:'child',definition:{en:'An original definition',zh:null}}]}]}]};
  const ids = new Map([['e',validateEntry(entry)]]);
  validateLookup({norm:'test',matches:[{entry_id:'e',sense_id:'child',match:'phrase'}]}, ids);
  assert.throws(() => validateLookup({norm:'x',matches:[{entry_id:'e',sense_id:'missing',match:'phrase'}]},ids), /失效/);
  entry.pos_groups[0].senses[0].senses.push({id:'child',definition:{en:'duplicate',zh:null}});
  assert.throws(() => validateEntry(entry), /重复/);
});
test('JSONL streaming preserves Unicode crossing byte boundaries', async () => {
  const expected = [{text:'x'.repeat(65520)+'音标ˈ英文'},{text:'最后一行'}];
  const bytes = new TextEncoder().encode(expected.map(x=>JSON.stringify(x)).join('\r\n'));
  const actual=[];for await(const row of jsonLines(bytes)) actual.push(row); assert.deepEqual(actual,expected);
});
test('SHA-256 rejects corrupted bytes', async () => {
  const bytes=new TextEncoder().encode('abc'); await verifyHash(bytes,'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad','test');
  await assert.rejects(verifyHash(new Uint8Array([1]),'0'.repeat(64),'test'),/校验失败/);
});
export function makeZip(files, {compress = true} = {}) {
  const local=[],central=[]; let offset=0;
  for(const [name,value] of Object.entries(files)) {
    const raw=Buffer.from(value), data=compress?deflateRawSync(raw):raw, n=Buffer.from(name);
    const h=Buffer.alloc(30);h.writeUInt32LE(0x04034b50);h.writeUInt16LE(20,4);h.writeUInt16LE(compress?8:0,8);h.writeUInt32LE(data.length,18);h.writeUInt32LE(raw.length,22);h.writeUInt16LE(n.length,26);
    local.push(h,n,data);const c=Buffer.alloc(46);c.writeUInt32LE(0x02014b50);c.writeUInt16LE(20,6);c.writeUInt16LE(compress?8:0,10);c.writeUInt32LE(data.length,20);c.writeUInt32LE(raw.length,24);c.writeUInt16LE(n.length,28);c.writeUInt32LE(offset,42);central.push(c,n);offset+=h.length+n.length+data.length;
  }
  const directory=Buffer.concat(central),end=Buffer.alloc(22);end.writeUInt32LE(0x06054b50);end.writeUInt16LE(3,8);end.writeUInt16LE(3,10);end.writeUInt32LE(directory.length,12);end.writeUInt32LE(offset,16);return Buffer.concat([...local,directory,end]);
}
test('ZIP reads stored/deflated content and rejects unexpected paths/truncation', async () => {
  const files={'manifest.json':'{}','entries.jsonl':'中文释义','lookup.jsonl':'lookup'};
  for(const compress of [true,false]) {const zip=await readZip(new Blob([makeZip(files,{compress})]));assert.equal(new TextDecoder().decode(await zip.read('entries.jsonl')),'中文释义');}
  await assert.rejects(readZip(new Blob([makeZip({'../manifest.json':'{}','entries.jsonl':'','lookup.jsonl':''})])),/不支持/);
  await assert.rejects(readZip(new Blob([makeZip(files).subarray(0,50)])));
});
