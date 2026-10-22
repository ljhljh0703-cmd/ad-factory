// 하루치 기록을 JSONL 하나로 돌려준다. 열쇠(EXPORT_KEY)가 맞을 때만. 엔진의 성과 보고가 이걸 받아 쓴다.
import { list } from '@vercel/blob';
export default async function handler(req, res) {
  if (!process.env.EXPORT_KEY || req.headers['x-export-key'] !== process.env.EXPORT_KEY) return res.status(401).end();
  const day = String(req.query.day || '');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return res.status(400).end();
  let cursor, out = '';
  do {
    const r = await list({ prefix: `events/${day}/`, cursor, limit: 1000 });
    for (const b of r.blobs) out += await (await fetch(b.url)).text();
    cursor = r.hasMore ? r.cursor : undefined;
  } while (cursor);
  res.setHeader('content-type', 'application/x-ndjson'); return res.status(200).send(out);
}
