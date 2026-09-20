const MAX_FILE = 300 * 1024 * 1024;
const names = ['manifest.json', 'entries.jsonl', 'lookup.jsonl'];
export async function readZip(file) {
  if (file.size > 120 * 1024 * 1024) throw new Error('词典包超过 120 MB 上限。');
  const bytes = new Uint8Array(await file.arrayBuffer()), view = new DataView(bytes.buffer);
  const u16 = n => view.getUint16(n, true), u32 = n => view.getUint32(n, true);
  let end = bytes.length - 22;
  for (; end >= Math.max(0, bytes.length - 65557); end--) if (u32(end) === 0x06054b50 && end + 22 + u16(end + 20) === bytes.length) break;
  if (end < 0 || u32(end) !== 0x06054b50) throw new Error('无法读取 ZIP 目录。');
  if (u16(end + 4) || u16(end + 6) || u16(end + 8) !== u16(end + 10)) throw new Error('不支持分卷 ZIP。');
  const count = u16(end + 10), offset = u32(end + 16);
  if (count !== 3 || offset + u32(end + 12) !== end) throw new Error('词典包应仅包含 manifest.json、entries.jsonl、lookup.jsonl。');
  const members = new Map(); let position = offset, total = 0;
  for (let i = 0; i < count; i++) {
    if (u32(position) !== 0x02014b50) throw new Error('ZIP 目录损坏。');
    const flags = u16(position + 8), method = u16(position + 10), size = u32(position + 24), compressed = u32(position + 20);
    const length = u16(position + 28), extra = u16(position + 30), comment = u16(position + 32), local = u32(position + 42);
    const name = new TextDecoder('utf-8', {fatal: true}).decode(bytes.subarray(position + 46, position + 46 + length));
    if (!names.includes(name) || members.has(name) || flags & 1 || ![0, 8].includes(method)) throw new Error('ZIP 含重复、加密或不支持的文件。');
    total += size;
    if (size > MAX_FILE || total > 450 * 1024 * 1024 || (name === 'manifest.json' && size > 1024 * 1024)) throw new Error('解压后的词典超过大小上限。');
    if (u32(local) !== 0x04034b50 || u16(local + 8) !== method) throw new Error('ZIP 文件头损坏。');
    const start = local + 30 + u16(local + 26) + u16(local + 28);
    if (start + compressed > offset) throw new Error('ZIP 文件范围无效。');
    members.set(name, {start, compressed, size, method});
    position += 46 + length + extra + comment;
  }
  if (position !== end) throw new Error('ZIP 目录长度不符。');
  return {async read(name) {
    const m = members.get(name); if (!m) throw new Error('缺少文件：' + name);
    const data = bytes.subarray(m.start, m.start + m.compressed);
    if (m.method === 0) {if (data.length !== m.size) throw new Error('文件长度不符'); return data;}
    const reader = new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader();
    const output = new Uint8Array(m.size); let written = 0;
    try {while (true) {const {value, done} = await reader.read(); if (done) break; if (written + value.length > m.size) throw new Error('解压数据超过声明长度。'); output.set(value, written); written += value.length;}}
    catch (error) {await reader.cancel().catch(() => {}); throw error;}
    if (written !== m.size) throw new Error('解压文件长度不符。'); return output;
  }};
}
export async function verifyHash(bytes, hash, name) {
  if (!/^[a-f\d]{64}$/i.test(hash || '')) throw new Error(name + ' 缺少 SHA-256 校验值。');
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  const actual = Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
  if (actual !== hash.toLowerCase()) throw new Error(name + ' 校验失败，请重新生成词典包。');
}
export async function* jsonLines(bytes) {
  const decoder = new TextDecoder('utf-8', {fatal: true}); let pending = '', number = 0;
  for (let pos = 0; pos < bytes.length; pos += 65536) {
    pending += decoder.decode(bytes.subarray(pos, pos + 65536), {stream: true});
    let newline;
    while ((newline = pending.indexOf('\n')) >= 0) {
      const line = pending.slice(0, newline); pending = pending.slice(newline + 1); number++;
      if (line.trim()) {try {yield JSON.parse(line);} catch {throw new Error('JSONL 第 ' + number + ' 行损坏。');}}
    }
    if (pending.length > 4 * 1024 * 1024) throw new Error('单条词典记录过大。');
  }
  pending += decoder.decode();
  if (pending.trim()) yield JSON.parse(pending);
}
