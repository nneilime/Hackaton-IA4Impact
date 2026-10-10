// Serveur statique d'essai avec lecture par plages (Range).
import { createServer } from 'node:http'; import { statSync, createReadStream, existsSync } from 'node:fs'; import { join, extname } from 'node:path';
const R = process.argv[2], PORT = Number(process.argv[3]);
const T = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.txt': 'text/plain', '.csv': 'text/csv', '.woff2': 'font/woff2' };
createServer((q, s) => {
  const f = join(R, decodeURIComponent(new URL(q.url, 'http://x').pathname));
  if (!existsSync(f) || statSync(f).isDirectory()) { s.writeHead(404); return s.end(); }
  const n = statSync(f).size, m = /^bytes=(\d+)-(\d+)$/.exec(q.headers.range || ''), t = T[extname(f)] || 'application/octet-stream';
  if (m) { const a = +m[1], b = Math.min(+m[2], n - 1); s.writeHead(206, { 'Content-Type': t, 'Content-Range': `bytes ${a}-${b}/${n}`, 'Content-Length': b - a + 1 }); return createReadStream(f, { start: a, end: b }).pipe(s); }
  s.writeHead(200, { 'Content-Type': t, 'Content-Length': n }); createReadStream(f).pipe(s);
}).listen(PORT, '127.0.0.1');
