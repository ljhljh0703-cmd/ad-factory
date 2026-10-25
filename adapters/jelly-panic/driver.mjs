// 젤리 패닉 드라이버: 공개판 화면에서 조각을 끌어 놓는다.
// 수는 페이지 안 그림자 판(게임 코어 window.CORE + 봇 정책)에서 고르고, 둔 뒤 화면 점수와 그림자 점수를 맞춰 본다.
import fs from 'fs';
const policy = fs.readFileSync(new URL('../../ua/policy.js', import.meta.url), 'utf8').replace(/if \(typeof module[^\n]*\n/, '');
export const url = (seed) => `https://ljhljh0703-cmd.github.io/jelly-panic/?seed=${seed}&notrack`;
export async function boot(T) {
  const p = T.page; await p.waitForTimeout(800);
  await p.evaluate(({ seed, mode, policy }) => {
    eval(policy + ';window.botPlan=botPlan;window.summarize=summarize;');
    const C = window.CORE; window.__S = C.newGame(seed, { mode });
    window.__plan = () => window.botPlan(C, window.__S);
    window.__mv = (slot, r, c) => { const m = C.SHAPES[window.__S.tray[slot]].m; const cells = []; m.forEach((row, dr) => row.forEach((v, dc) => { if (v) cells.push([r + dr, c + dc]); })); return { slot, r, c, rows: m.length, cols: m[0].length, cells, forced: true }; };
    window.__apply = (mv) => { const S = window.__S; const ev = mv.discard ? C.discard(S, mv.slot) : C.place(S, mv.slot, mv.r, mv.c); return window.summarize(C, S, ev); };
  }, { seed: T.seed, mode: T.opt.mode || 'classic', policy });
}
async function geom(p, mv) {
  const sb = await p.locator(`.slot[data-slot="${mv.slot}"]`).boundingBox();
  const sx = sb.x + sb.width / 2, sy = sb.y + sb.height / 2; let tx, ty;
  if (mv.discard) { const bb = await p.locator('#bin').boundingBox(); tx = bb.x + bb.width / 2; ty = bb.y + bb.height / 2; }
  else { const rb = await p.locator('#board').boundingBox(); const PAD = 10, CS = (rb.width - 2 * PAD) / 8, LIFT = 8; tx = rb.x + PAD + (mv.c + mv.cols / 2) * CS; ty = rb.y + LIFT + PAD + (mv.r + mv.rows / 2) * CS; }
  return { sx, sy, tx, ty };
}
export async function step(T, i, OV) {
  const p = T.page;
  let mv = await p.evaluate(() => window.__plan()); if (!mv) return null;
  const extra = {};
  if (OV[i]) { const o = OV[i]; mv = await p.evaluate(({ s, r, c }) => window.__mv(s, r, c), { s: o.slot, r: o.r, c: o.c }); }
  if (OV[`good${i}`]) { const g = OV[`good${i}`]; extra.good_cells = (await p.evaluate(({ s, r, c }) => window.__mv(s, r, c), { s: g.slot, r: g.r, c: g.c })).cells; }
  const g = await geom(p, mv);
  if (T.recording) {
    await T.frames(10); await T.drag(g.sx, g.sy, g.tx, g.ty); extra.frameUp = T.frame; await T.frames(42);
  } else {
    await p.mouse.move(g.sx, g.sy); await p.mouse.down(); await p.mouse.move(g.tx, g.ty, { steps: 6 }); await p.mouse.up(); await p.waitForTimeout(160);
  }
  const st = await p.evaluate((m) => window.__apply(m), mv);
  const ui = +(await p.locator('#score').innerText());
  return { forced: !!mv.forced, move: mv.discard ? 'discard' : `slot${mv.slot}@${mv.r},${mv.c}`, cells: mv.cells, ...extra, ...st, ui, sync: ui === st.score };
}
export async function geometry(T) { return { board: await T.page.locator('#board').boundingBox() }; }
