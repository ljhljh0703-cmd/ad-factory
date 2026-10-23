// 익명 기록 수집기. 게임이 sendBeacon 으로 보낸 묶음을 받아 하루 파일(JSONL)에 붙인다.
// 받는 항목은 약속한 열쇠만 남기고 나머지는 버린다. IP·User-Agent·쿠키는 저장하지 않는다.
//   node server.mjs [port] [data_dir]
import http from 'http'; import fs from 'fs'; import path from 'path';
const PORT = +process.argv[2] || 8787, DIR = process.argv[3] || path.join(path.dirname(new URL(import.meta.url).pathname), 'data');
const KEYS = { v: 'n', sid: 's', did: 's', ab: 's', ver: 's', n: 'n', sec: 'n', type: 's', src: 's', ad: 's', mode: 's', stage: 'n', day: 'n', seed: 'n', after: 'n', cause: 's', score: 'n', placements: 'n', rescued: 'n', prev: 's' };
const TYPES = new Set(['start', 'first_move', 'end', 'restart', 'leave']);
const ORIGINS = (process.env.ALLOW_ORIGIN || 'https://ljhljh0703-cmd.github.io,null').split(',');
export function clean(e) {
  if (!e || typeof e !== 'object' || !TYPES.has(e.type)) return null;
  const o = {};
  for (const [k, t] of Object.entries(KEYS)) {
    const v = e[k]; if (v === undefined || v === null) continue;
    if (t === 'n' && Number.isFinite(v) && Math.abs(v) < 1e9) o[k] = Math.round(v);
    if (t === 's' && typeof v === 'string' && /^[A-Za-z0-9_-]{0,32}$/.test(v)) o[k] = v;
  }
  return o.sid && o.type ? o : null;
}
fs.mkdirSync(DIR, { recursive: true });
const srv = http.createServer((req, res) => {
  const origin = req.headers.origin || 'null';
  res.setHeader('Access-Control-Allow-Origin', ORIGINS.includes(origin) ? origin : ORIGINS[0]);
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
  if (req.method !== 'POST' || !req.url.startsWith('/collect')) { res.writeHead(404); return res.end(); }
  let body = ''; req.on('data', c => { body += c; if (body.length > 20000) req.destroy(); });
  req.on('end', () => {
    let rows = []; try { rows = JSON.parse(body); } catch { res.writeHead(400); return res.end(); }
    if (!Array.isArray(rows)) rows = [rows];
    const day = new Date().toISOString().slice(0, 10), at = Date.now();
    const keep = rows.slice(0, 50).map(clean).filter(Boolean).map(e => JSON.stringify({ ...e, at }));
    if (keep.length) fs.appendFileSync(path.join(DIR, `${day}.jsonl`), keep.join('\n') + '\n');
    res.writeHead(204); res.end();
  });
});
if (process.argv[1] && process.argv[1].endsWith('server.mjs')) srv.listen(PORT, () => console.log('수집기', PORT, DIR));
