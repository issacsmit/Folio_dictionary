import {readFile, readdir, mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {deflateRawSync} from 'node:zlib';

const root = path.resolve('.');
const RUNTIME_FILES = [
  'manifest.json', 'background.js', 'card.js', 'content.js', 'import-worker.js',
  'options.html', 'options.js', 'pages.css', 'popup.html', 'popup.js',
];
const manifest = JSON.parse(await readFile(path.join(root, 'manifest.json'), 'utf8'));
const table = Array.from({length: 256}, (_, n) => {for (let i = 0; i < 8; i++) n = n & 1 ? 0xedb88320 ^ (n >>> 1) : n >>> 1; return n >>> 0;});
function crc32(bytes) {let crc = 0xffffffff; for (const b of bytes) crc = table[(crc ^ b) & 255] ^ (crc >>> 8); return (crc ^ 0xffffffff) >>> 0;}
async function files() {
  const out = RUNTIME_FILES.map(name => path.join(root, name));
  for (const dir of ['lib', 'icons']) {
    for (const entry of await readdir(path.join(root, dir), {withFileTypes: true})) {
      if (entry.isFile()) out.push(path.join(root, dir, entry.name));
    }
  }
  return out.sort();
}
const local = [], central = []; let offset = 0, count = 0;
for (const file of await files()) {
  const name = path.relative(root, file).replaceAll('\\', '/');
  if (!/^(?:lib\/|icons\/)?[a-z0-9.-]+\.(?:js|css|html|json|png)$/i.test(name)) throw new Error('Unexpected extension file: ' + name);
  const bytes = await readFile(file), compressed = deflateRawSync(bytes), n = Buffer.from(name), crc = crc32(bytes), h = Buffer.alloc(30), c = Buffer.alloc(46);
  h.writeUInt32LE(0x04034b50); h.writeUInt16LE(20, 4); h.writeUInt16LE(0x800, 6); h.writeUInt16LE(8, 8); h.writeUInt16LE(33, 12); h.writeUInt32LE(crc, 14); h.writeUInt32LE(compressed.length, 18); h.writeUInt32LE(bytes.length, 22); h.writeUInt16LE(n.length, 26); local.push(h, n, compressed);
  c.writeUInt32LE(0x02014b50); c.writeUInt16LE(20, 4); c.writeUInt16LE(20, 6); c.writeUInt16LE(0x800, 8); c.writeUInt16LE(8, 10); c.writeUInt16LE(33, 14); c.writeUInt32LE(crc, 16); c.writeUInt32LE(compressed.length, 20); c.writeUInt32LE(bytes.length, 24); c.writeUInt16LE(n.length, 28); c.writeUInt32LE(offset, 42); central.push(c, n); offset += h.length + n.length + compressed.length; count++;
}
const directory = Buffer.concat(central), end = Buffer.alloc(22); end.writeUInt32LE(0x06054b50); end.writeUInt16LE(count, 8); end.writeUInt16LE(count, 10); end.writeUInt32LE(directory.length, 12); end.writeUInt32LE(offset, 16);
await mkdir('dist', {recursive: true}); const file = `dist/folio-${manifest.version}.zip`; await writeFile(file, Buffer.concat([...local, directory, end])); console.log(`${file} · ${count} files · code only, no dictionary data`);
