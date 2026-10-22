// 답답한 플레이 장면 찾기: 막을 수 있는 까마귀를 두고 엉뚱한 칸에 놓아 지는 순간, 또는 줄 여러 개를 지울 수 있는데 안 지우고 막히는 순간.
const C = require('./core.js'); const { botPlan, summarize, babyPos } = require('./policy.js'); const fs = require('fs');
const [A, B] = [+process.argv[2] || 1, +process.argv[3] || 400];
const clone = s => JSON.parse(JSON.stringify(s));
const adj = (a, b) => a && b && Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1])) === 1;
function moves(S) { const out = []; for (let slot = 0; slot < 3; slot++) { const sh = S.tray[slot]; if (sh == null) continue;
  for (let r = -3; r < C.N; r++) for (let c = -3; c < C.N; c++) { if (!C.canPlace(S, sh, r, c)) continue; const T = clone(S); const ev = C.place(T, slot, r, c); if (ev) out.push({ slot, r, c, ev, T, sh }); } } return out; }
const found = [];
for (let seed = A; seed <= B; seed++) {
  const S = C.newGame(seed, { mode: 'classic' });
  for (let i = 0; i < 140 && !S.over; i++) {
    const baby = babyPos(C, S);
    const crow = S.threats.find(t => t.type === 'crow' && t.countdown <= 1 && adj([t.r, t.c], baby));
    const full = C.N * C.N - C.countCells(S, C.EMPTY);
    if (crow || full >= 48) {
      const ms = moves(S);
      if (crow) {
        const good = ms.filter(m => m.ev.defused.some(d => d[0] === crow.r && d[1] === crow.c) && !m.T.over);
        const bad = ms.filter(m => m.T.over && m.T.overCause === 'baby' && !m.ev.chain.length).sort((x, y) => (Math.abs(y.r - crow.r) + Math.abs(y.c - crow.c)) - (Math.abs(x.r - crow.r) + Math.abs(x.c - crow.c)));
        if (good.length && bad.length) { const g = good.sort((x, y) => y.ev.chain.length - x.ev.chain.length)[0];
          found.push({ kind: 'crow', seed, i, crow: [crow.r, crow.c], baby, good: { slot: g.slot, r: g.r, c: g.c, chain: g.ev.chain.length }, bad: { slot: bad[0].slot, r: bad[0].r, c: bad[0].c }, fill: full }); }
      } else {
        const good = ms.filter(m => m.ev.chain.reduce((a, s) => a + (s.clearedLines || 0), 0) >= 2 && !m.T.over);
        const bad = ms.filter(m => !m.ev.chain.length && !m.T.over && !C.anyMoveExists(m.T)).concat(ms.filter(m => m.T.over && !m.ev.chain.length));
        if (good.length && bad.length) { const g = good.sort((x, y) => y.ev.chain.length - x.ev.chain.length)[0];
          found.push({ kind: 'lines', seed, i, good: { slot: g.slot, r: g.r, c: g.c, chain: g.ev.chain.length }, bad: { slot: bad[0].slot, r: bad[0].r, c: bad[0].c, over: bad[0].T.over }, fill: full, baby: !!baby }); }
      }
    }
    const mv = botPlan(C, S); if (!mv) break; mv.discard ? C.discard(S, mv.slot) : C.place(S, mv.slot, mv.r, mv.c);
  }
}
fs.writeFileSync('mined_fail.json', JSON.stringify(found));
const k = {}; found.forEach(f => k[f.kind] = (k[f.kind] || 0) + 1); console.log(k);
console.log(found.filter(f => f.kind === 'crow').sort((a, b) => b.good.chain - a.good.chain || a.i - b.i).slice(0, 5));
console.log(found.filter(f => f.kind === 'lines' && f.baby).sort((a, b) => b.good.chain - a.good.chain || b.fill - a.fill).slice(0, 5));
