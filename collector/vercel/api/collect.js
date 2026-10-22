// 게임이 sendBeacon 으로 보낸 묶음 하나를 Blob 파일 하나로 남긴다: events/YYYY-MM-DD/<시각>-<무작위>.jsonl
import { put } from '@vercel/blob';
import { parse } from './_clean.js';
const ORIGINS = ['https://ljhljh0703-cmd.github.io'];
export default async function handler(req, res) {
  const origin = req.headers.origin;
  res.setHeader('Access-Control-Allow-Origin', ORIGINS.includes(origin) ? origin : ORIGINS[0]);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).end();
  const raw = typeof req.body === 'string' || Buffer.isBuffer(req.body) ? req.body : JSON.stringify(req.body ?? '');
  if (String(raw).length > 20000) return res.status(413).end();
  const at = Date.now(), day = new Date(at).toISOString().slice(0, 10);
  const rows = parse(req.body).map((e) => JSON.stringify({ ...e, at }));
  if (rows.length) await put(`events/${day}/${at}.jsonl`, rows.join('\n') + '\n', { access: 'public', addRandomSuffix: true, contentType: 'application/x-ndjson' });
  return res.status(204).end();
}
