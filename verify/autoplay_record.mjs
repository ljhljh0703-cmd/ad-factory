// 실제 공개판을 브라우저에서 사람처럼 끌어 놓아 플레이하고 녹화한다.
// 수 계산은 같은 seed로 만든 그림자 판(window.CORE)으로 하고, 실제 입력은 마우스 드래그로만 한다.
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'fs';
const SEED = +(process.argv[2] || 7), MOVES = +(process.argv[3] || 60), OUT = process.argv[4] || 'out';
fs.mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, recordVideo: { dir: OUT, size: { width: 390, height: 844 } } });
const p = await ctx.newPage();
const t0 = Date.now();
await p.goto(`https://ljhljh0703-cmd.github.io/jelly-panic/?seed=${SEED}`, { waitUntil: 'networkidle' });
await p.waitForTimeout(800);
await p.evaluate((seed) => {
  const C = window.CORE;
  window.__S = C.newGame(seed, { mode: 'classic' });
  const clone = (s) => JSON.parse(JSON.stringify(s));
  window.__plan = () => {
    const S = window.__S; if (S.over) return null;
    let best = null;
    for (let slot = 0; slot < 3; slot++) {
      const sh = S.tray[slot]; if (sh == null) continue;
      for (let r = -3; r < C.N; r++) for (let c = -3; c < C.N; c++) {
        if (!C.canPlace(S, sh, r, c)) continue;
        const T = clone(S); const ev = C.place(T, slot, r, c); if (!ev) continue;
        let v = ev.gained + (ev.rescued || 0) * 300 + (ev.chain ? ev.chain.length * 40 : 0);
        if (T.over) v -= 100000;
        // 위협 예고 칸을 덮으면 가산, 빈 칸이 많을수록 가산
        v -= T.threats.filter(t => t.countdown <= 1).length * 60;
        v += C.countCells(T, C.EMPTY) * 2;
        if (!best || v > best.v) best = { slot, r, c, v };
      }
    }
    if (!best) return { discard: true, slot: S.tray.findIndex(x => x != null) };
    const m = C.SHAPES[S.tray[best.slot]] ? C.SHAPES[S.tray[best.slot]].m : [[1]];
    best.rows = m.length; best.cols = m[0].length; return best;
  };
  window.__apply = (mv) => {
    const S = window.__S;
    const ev = mv.discard ? C.discard(S, mv.slot) : C.place(S, mv.slot, mv.r, mv.c);
    const baby = (() => { for (let r = 0; r < C.N; r++) for (let c = 0; c < C.N; c++) if (S.grid[r][c] === C.BABY) return [r, c]; return null; })();
    return { score: S.score, over: S.over, cause: S.overCause, placements: S.placements, tier: C.difficulty(S.placements).tier,
      chain: ev && ev.chain ? ev.chain.length : 0, rescued: ev ? ev.rescued || 0 : 0, babySpawn: ev ? ev.babySpawn || null : null, baby,
      threats: S.threats.map(t => ({ type: t.type, r: t.r, c: t.c, cd: t.countdown })) };
  };
}, SEED);
const log = [];
for (let i = 0; i < MOVES; i++) {
  const mv = await p.evaluate(() => window.__plan());
  if (!mv) break;
  const slotBox = await p.locator(`.slot[data-slot="${mv.slot}"]`).boundingBox();
  const sx = slotBox.x + slotBox.width / 2, sy = slotBox.y + slotBox.height / 2;
  let tx, ty;
  if (mv.discard) { const bb = await p.locator('#bin').boundingBox(); tx = bb.x + bb.width / 2; ty = bb.y + bb.height / 2; }
  else {
    const rb = await p.locator('#board').boundingBox(); const PAD = 10; const CS = (rb.width - 2 * PAD) / 8; const LIFT = 8;
    tx = rb.x + PAD + (mv.c + mv.cols / 2) * CS; ty = rb.y + LIFT + PAD + (mv.r + mv.rows / 2) * CS;
  }
  const tStart = Date.now() - t0;
  await p.mouse.move(sx, sy); await p.mouse.down(); await p.mouse.move(tx, ty, { steps: 12 }); await p.mouse.up();
  await p.waitForTimeout(650);
  const st = await p.evaluate((m) => window.__apply(m), mv);
  const uiScore = +(await p.locator('#score').innerText());
  log.push({ i, t_ms: tStart, move: mv.discard ? 'discard' : `slot${mv.slot}@${mv.r},${mv.c}`, ...st, uiScore, sync: uiScore === st.score });
  if (uiScore !== st.score) { console.log('DESYNC at', i, uiScore, st.score); break; }
  if (st.over) { await p.waitForTimeout(1500); break; }
}
await p.waitForTimeout(800);
await p.close(); const vid = await p.video().path(); await ctx.close(); await b.close();
fs.writeFileSync(`${OUT}/log.json`, JSON.stringify({ seed: SEED, video: vid, moves: log }, null, 1));
const L = log.at(-1); console.log('moves', log.length, 'score', L && L.score, 'over', L && L.over, L && L.cause, 'rescued', log.reduce((a, x) => a + x.rescued, 0), 'maxchain', Math.max(...log.map(x => x.chain)), 'desync', log.filter(x => !x.sync).length, vid);
