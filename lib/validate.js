function fail(message) { throw new Error('词典格式错误：' + message); }
function object(v, name) {if (!v || typeof v !== 'object' || Array.isArray(v)) fail(name); return v;}
function string(v, name, required = false) {if (v == null && !required) return; if (typeof v !== 'string' || v.length > 100000 || (required && !v.trim())) fail(name);}
function array(v, name) {if (v === undefined) return []; if (!Array.isArray(v) || v.length > 20000) fail(name); return v;}
function strings(v, name) {for (const x of array(v, name)) string(x, name, true);}
function definition(v) {object(v, 'definition'); string(v.en, '英文释义'); string(v.zh, '中文释义');}
function labels(v) {for (const x of array(v, 'labels')) {object(x, 'label'); string(x.value, 'label.value', true);}}
function refs(v) {for (const x of array(v, 'cross_refs')) {object(x, 'cross_ref'); string(x.text, 'cross_ref.text', true); string(x.href, 'cross_ref.href');}}
function phrases(v) {for (const x of array(v, 'phrases')) {object(x, 'phrase'); string(x.text, 'phrase.text', true); definition(x.definition); labels(x.labels); strings(x.patterns, 'patterns');}}
export function validateEntry(entry) {
  object(entry, 'entry'); string(entry.id, 'entry.id', true); string(entry.headword, 'headword', true); string(entry.display, 'display');
  if (!['word', 'derived', 'phrasal_verb', 'see_also'].includes(entry.kind)) fail('kind');
  if (!Array.isArray(entry.pos_groups)) fail('pos_groups');
  const ids = new Set();
  function sense(s, depth = 0) {
    if (depth > 12) fail('义项嵌套过深'); object(s, 'sense'); string(s.id, 'sense.id', true);
    if (ids.has(s.id)) fail('重复义项 ' + s.id); ids.add(s.id);
    definition(s.definition); if (s.signpost != null) definition(s.signpost);
    string(s.number, 'sense.number'); labels(s.labels); strings(s.grammar, 'grammar'); strings(s.lexunits, 'lexunits'); strings(s.patterns, 'patterns'); refs(s.cross_refs); phrases(s.phrases);
    for (const child of array(s.senses, 'senses')) sense(child, depth + 1);
  }
  for (const group of entry.pos_groups) {object(group, 'pos_group'); strings(group.pos, 'pos'); strings(group.grammar, 'grammar'); labels(group.labels); for (const s of array(group.senses, 'senses')) sense(s);}
  for (const p of array(entry.pronunciations, 'pronunciations')) {object(p, 'pronunciation'); string(p.ipa, 'ipa', true); string(p.accent, 'accent');}
  for (const inflection of array(entry.inflections, 'inflections')) {object(inflection, 'inflection'); string(inflection.form, 'inflection.form', true);}
  phrases(entry.phrases); refs(entry.cross_refs);
  if (entry.parent != null) {object(entry.parent, 'parent'); string(entry.parent.id, 'parent.id', true); string(entry.parent.headword, 'parent.headword', true);}
  return ids;
}
export function validateManifest(m) {
  object(m, 'manifest');
  if (m.format !== 'folio-dict-pack' || m.format_version !== '1.0') fail('仅支持 Folio 词典包 v1.0');
  string(m.pack_id, 'pack_id', true); string(m.source?.name, 'source.name', true);
  for (const key of ['entries', 'lookup_keys']) if (!Number.isSafeInteger(m.counts?.[key]) || m.counts[key] < 1 || m.counts[key] > 2000000) fail('counts.' + key);
  object(m.checksums, 'checksums');
}
export function validateLookup(row, entryIds) {
  object(row, 'lookup'); string(row.norm, 'norm', true);
  if (!Array.isArray(row.matches) || !row.matches.length || row.matches.length > 20000) fail('matches');
  for (const m of row.matches) {
    object(m, 'match'); string(m.entry_id, 'entry_id', true); string(m.match, 'match', true); string(m.headword, 'headword');
    const senses = entryIds.get(m.entry_id);
    if (!senses || (m.sense_id && !senses.has(m.sense_id))) fail('失效的词条或义项引用：' + m.entry_id);
  }
}
