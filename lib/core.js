export const DEFAULT_SETTINGS = Object.freeze({trigger: 'Alt', searchKey: 'Enter', theme: 'auto', enabled: true});
const NAMED_KEYS = new Set(['Alt', 'Ctrl', 'Shift', 'Meta', 'Enter', 'Space', 'Backspace', ...Array.from({length: 12}, (_, i) => 'F' + (i + 1))]);
export function normalizeShortcut(value) {
  if (typeof value !== 'string') return '';
  if (/^\s+$/.test(value) || /^space$/i.test(value.trim())) return 'Space';
  const text = value.trim();
  if (/^[a-zA-Z0-9]$/.test(text)) return text.toLowerCase();
  if (/^(ctrl|control)$/i.test(text)) return 'Ctrl';
  if (/^F([1-9]|1[0-2])$/i.test(text)) return text.toUpperCase();
  const named = text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
  return NAMED_KEYS.has(named) ? named : '';
}
export function shortcutFromEvent(event) {
  if (!event || event.isComposing || event.key === 'Escape' || event.key === 'Tab' || event.key === 'Dead') return '';
  if (event.key === ' ') return 'Space';
  if (event.key === 'Control') return 'Ctrl';
  if (event.key.length === 1 && /^[a-zA-Z0-9]$/.test(event.key)) return event.key.toLowerCase();
  if (/^F([1-9]|1[0-2])$/.test(event.key)) return event.key;
  return NAMED_KEYS.has(event.key) ? event.key : '';
}
export function fold(text) {
  return text.normalize('NFKC').replace(/[‘’]/g, "'").replace(/[‐‑]/g, '-').replace(/↔/g, ' ')
    .replace(/[\s\u200b]+/g, ' ').trim().toLowerCase().replace(/ß/g, 'ss').replace(/ς/g, 'σ');
}
export function loose(text) { return fold(text).replace(/^[.,;:!?·•]+|[.,;:!?·•]+$/g, '').trim(); }
export function lookupKeys(text) { return [...new Set([fold(text), loose(text)])].filter(Boolean); }
export const RANK = {headword: 0, display: 1, mdx_key: 1, derived_locator: 2, alias: 3, phrasal_verb: 4, inflection: 5, phrase: 6, phrase_pattern: 6, lexical_unit: 6, collocation: 9};
export function rankMatches(text, matches) {
  const exact = fold(text), normalized = loose(text);
  const score = m => [fold(m.headword || '') === exact ? 0 : loose(m.headword || '') === normalized ? 1 : 2, RANK[m.match] ?? 8];
  return [...matches].sort((a, b) => { const x = score(a), y = score(b); return x[0] - y[0] || x[1] - y[1] || (a.headword || '').localeCompare(b.headword || ''); });
}
export function validQuery(text) {
  return typeof text === 'string' && text.length <= 160 && /[a-zA-Z]/.test(text) && text.trim().split(/\s+/).length <= 12 && !/[\r\n<>]/.test(text);
}
export function cleanSettings(value = {}) {
  return {
    enabled: value.enabled !== false,
    trigger: normalizeShortcut(value.trigger) || DEFAULT_SETTINGS.trigger,
    searchKey: normalizeShortcut(value.searchKey) || DEFAULT_SETTINGS.searchKey,
    theme: ['auto', 'light', 'dark'].includes(value.theme) ? value.theme : 'auto'
  };
}
// Read only explicitly recorded forms; do not infer roots by stripping suffixes.
export function explicitInflections(entry) {
  const forms = [];
  for (const item of entry.inflections || []) {
    const value = fold(item.form || '').replace(/^,\s*/, '').replace(/^(past tense and past participle|past tense|past participle|present participle|third person singular|plural|comparative|superlative)\s+/, '');
    if (/^[a-z]+(?:['-][a-z]+)*$/.test(value) && value !== fold(entry.headword)) forms.push(value);
  }
  return [...new Set(forms)];
}
