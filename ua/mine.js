// 여러 판 번호를 시뮬레이션해 광고 유형별 실제 장면 후보를 찾는다.
const C = require('./core.js'); const { botPlan, summarize } = require('./policy.js'); const fs = require('fs');
const [A, B, MODE] = [+process.argv[2] || 1, +process.argv[3] || 200, process.argv[4] || 'classic'];
const adj = (a, b) => a && b && Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1])) === 1;
const out = [];
for (let seed = A; seed <= B; seed++) {
  const S = C.newGame(seed, { mode: MODE }); const log = [];
  for (let i = 0; i < 140 && !S.over; i++) {
    const pre = summarize(C, S, null); const mv = botPlan(C, S); if (!mv) break;
    const ev = mv.discard ? C.discard(S, mv.slot) : C.place(S, mv.slot, mv.r, mv.c);
    log.push({ i, mv, pre, post: summarize(C, S, ev) });
  }
  const L = log.at(-1);
  // 뒤집기: 마지막 칸 위협(카운트다운 1)이 있는 몰린 판에서 한 수로 막고 연쇄
  for (const m of log) {
    const urgent = m.pre.threats.filter(t => t.cd <= 1);
    if (urgent.length && m.post.defused >= 1 && m.post.chain >= 2 && !m.post.over && m.pre.fill >= 26) {
      const crowNearBaby = urgent.some(t => t.type === 'crow' && adj([t.r, t.c], m.pre.baby));
      out.push({ kind: 'flip', seed, mode: MODE, i: m.i, fill: m.pre.fill, chain: m.post.chain, lines: m.post.lines, crowNearBaby, types: urgent.map(t => t.type), baby: !!m.pre.baby });
    }
    if (m.post.rescued && m.pre.threats.some(t => t.type === 'crow' && adj([t.r, t.c], m.pre.baby)))
      out.push({ kind: 'rescue', seed, mode: MODE, i: m.i, chain: m.post.chain, fill: m.pre.fill, granted: m.post.granted });
  }
  if (L && L.post.over) out.push({ kind: 'loss', seed, mode: MODE, i: L.i, cause: L.post.cause, fill: L.pre.fill, moves: log.length, score: L.post.score,
    crowAdj: L.pre.threats.some(t => t.type === 'crow' && t.cd <= 1 && adj([t.r, t.c], L.pre.baby)) });
}
fs.writeFileSync(`mined_${MODE}_${A}_${B}.json`, JSON.stringify(out));
const c = {}; out.forEach(o => c[o.kind] = (c[o.kind] || 0) + 1); console.log(MODE, c);
