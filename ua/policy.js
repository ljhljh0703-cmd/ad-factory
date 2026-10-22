// 자동 플레이 수 고르기. 브라우저(그림자 판)와 node 시뮬레이션이 같은 함수를 쓴다.
function botPlan(C, S) {
  if (S.over) return null;
  const clone = (s) => JSON.parse(JSON.stringify(s));
  let best = null;
  for (let slot = 0; slot < 3; slot++) {
    const sh = S.tray[slot]; if (sh == null) continue;
    for (let r = -3; r < C.N; r++) for (let c = -3; c < C.N; c++) {
      if (!C.canPlace(S, sh, r, c)) continue;
      const T = clone(S); const ev = C.place(T, slot, r, c); if (!ev) continue;
      let v = ev.gained + (ev.rescued || 0) * 300 + (ev.chain ? ev.chain.length * 40 : 0) + (ev.defused ? ev.defused.length * 80 : 0);
      if (T.over) v -= 100000;
      v -= T.threats.filter(t => t.countdown <= 1).length * 60;
      v += C.countCells(T, C.EMPTY) * 2;
      if (!best || v > best.v) best = { slot, r, c, v };
    }
  }
  if (!best) return { discard: true, slot: S.tray.findIndex(x => x != null) };
  const sh = S.tray[best.slot]; const m = C.SHAPES[sh] ? C.SHAPES[sh].m : [[1]];
  best.rows = m.length; best.cols = m[0].length; return best;
}
function babyPos(C, S) { for (let r = 0; r < C.N; r++) for (let c = 0; c < C.N; c++) if (S.grid[r][c] === C.BABY) return [r, c]; return null; }
function summarize(C, S, ev) {
  return { score: S.score, over: S.over, cause: S.overCause, placements: S.placements, tier: C.difficulty(S.placements).tier,
    fill: C.N * C.N - C.countCells(S, C.EMPTY), baby: babyPos(C, S),
    chain: ev && ev.chain ? ev.chain.length : 0, lines: ev && ev.chain ? ev.chain.reduce((a, s) => a + (s.clearedLines || 0), 0) : 0,
    rescued: ev ? ev.rescued || 0 : 0, defused: ev ? (ev.defused || []).length : 0, fired: ev ? (ev.fired || []).map(f => f[2]) : [],
    granted: ev ? ev.granted : null, babySpawn: ev ? ev.babySpawn || null : null,
    threats: S.threats.map(t => ({ type: t.type, r: t.r, c: t.c, cd: t.countdown })) };
}
if (typeof module !== 'undefined') module.exports = { botPlan, babyPos, summarize };
