// 약속한 항목만 남긴다(게임 쪽 index.html 의 익명 기록과 같은 목록). IP·User-Agent·쿠키는 저장하지 않는다.
// v2 (2026-10-24): did(기기 안 무작위 번호, 다시 오는 비율), ab(반반 비교 그룹), ver(공개판 번호), stage, day(오늘의 판 날짜), leave(판 도중 나감)
const KEYS = { v: 'n', sid: 's', did: 's', ab: 's', ver: 's', n: 'n', sec: 'n', type: 's', src: 's', ad: 's', mode: 's', stage: 'n', day: 'n', seed: 'n', after: 'n', cause: 's', score: 'n', placements: 'n', rescued: 'n', prev: 's' };
const TYPES = new Set(['start', 'first_move', 'end', 'restart', 'leave']);
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
export function parse(body) {
  let rows = body;
  if (typeof body === 'string') { try { rows = JSON.parse(body); } catch { return []; } }
  if (Buffer.isBuffer(body)) { try { rows = JSON.parse(body.toString('utf8')); } catch { return []; } }
  if (!Array.isArray(rows)) rows = [rows];
  return rows.slice(0, 50).map(clean).filter(Boolean);
}
