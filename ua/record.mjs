// 실제 공개판을 자동 플레이하며 정해진 구간만 정확한 시각과 함께 화면·소리를 기록한다.
// 화면: CDP 스크린캐스트(프레임마다 시각), 소리: 게임 WebAudio 호출을 시각과 함께 기록(나중에 같은 값으로 합성).
// 사용: node record.mjs <seed> <from_move> <to_move> <out> [mode]
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'fs';
const [SEED, FROM, TO, OUT, MODE] = [+process.argv[2], +process.argv[3], +process.argv[4], process.argv[5], process.argv[6] || 'classic'];
fs.mkdirSync(`${OUT}/frames`, { recursive: true });
const policy = fs.readFileSync(new URL('./policy.js', import.meta.url), 'utf8').replace(/if \(typeof module[^\n]*\n/, '');
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3 });
await ctx.addInitScript(() => {
  // 소리 기록용 AudioContext: 게임이 만드는 음(주파수·파형·길이·크기)을 페이지 시각과 함께 남긴다.
  window.__audio = [];
  class P { constructor(o, k) { this.o = o; this.k = k; this.value = 1; }
    setValueAtTime(v, t) { this.o[this.k] = v; this.o[this.k + 'T'] = t; } exponentialRampToValueAtTime(v, t) { this.o[this.k + 'To'] = v; this.o[this.k + 'End'] = t; } }
  class FakeAC { constructor() { this.t0 = performance.now(); this.state = 'running'; this.destination = {}; }
    get currentTime() { return (performance.now() - this.t0) / 1000; }
    resume() { return Promise.resolve(); } suspend() { return Promise.resolve(); }
    createGain() { const g = { connect() {} }; g.gain = new P(g, 'vol'); return g; }
    createOscillator() { const ac = this, o = { type: 'sine', connect(g) { this.g = g; } };
      o.frequency = new P(o, 'freq');
      o.start = (t) => { o.t = t; };
      o.stop = (t) => { window.__audio.push({ wall: performance.timeOrigin + ac.t0 + o.t * 1000, type: o.type, freq: o.freq, slide: o.freqTo || null, dur: (o.freqEnd || (o.g && o.g.volEnd) || t) - o.t, vol: o.g ? o.g.vol : 0.14 }); };
      return o; } }
  window.AudioContext = FakeAC; window.webkitAudioContext = FakeAC;
});
const p = await ctx.newPage();
await p.goto(`https://ljhljh0703-cmd.github.io/jelly-panic/?seed=${SEED}&notrack${MODE !== 'classic' ? '' : ''}`, { waitUntil: 'networkidle' });
await p.waitForTimeout(800);
await p.evaluate(({ seed, mode, policy }) => {
  eval(policy + ';window.botPlan=botPlan;window.summarize=summarize;');
  const C = window.CORE; window.__S = C.newGame(seed, { mode });
  window.__plan = () => window.botPlan(C, window.__S);
  window.__apply = (mv) => { const S = window.__S; const ev = mv.discard ? C.discard(S, mv.slot) : C.place(S, mv.slot, mv.r, mv.c); return window.summarize(C, S, ev); };
}, { seed: SEED, mode: MODE, policy });
const cdp = await ctx.newCDPSession(p); const frames = []; const FPS = 30, SCALE = 2.769; // 390*2.769 ≈ 1080
const log = [];
let vt = false;
async function advance(ms) { await new Promise(res => { cdp.once('Emulation.virtualTimeBudgetExpired', res); cdp.send('Emulation.setVirtualTimePolicy', { policy: 'advance', budget: ms }); }); }
async function frame() {
  await advance(1000 / FPS);
  const n = frames.length; const t = await p.evaluate(() => performance.timeOrigin + performance.now());
  const s = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 90, clip: { x: 0, y: 0, width: 390, height: 844, scale: SCALE } });
  fs.writeFileSync(`${OUT}/frames/${String(n).padStart(5, '0')}.jpg`, Buffer.from(s.data, 'base64')); frames.push({ n, wall: t });
}
async function frames_(k) { for (let j = 0; j < k; j++) await frame(); }
const mouse = (type, x, y) => cdp.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1, pointerType: 'mouse' });
async function geom(mv) {
  const sb = await p.locator(`.slot[data-slot="${mv.slot}"]`).boundingBox();
  const sx = sb.x + sb.width / 2, sy = sb.y + sb.height / 2; let tx, ty;
  if (mv.discard) { const bb = await p.locator('#bin').boundingBox(); tx = bb.x + bb.width / 2; ty = bb.y + bb.height / 2; }
  else { const rb = await p.locator('#board').boundingBox(); const PAD = 10, CS = (rb.width - 2 * PAD) / 8, LIFT = 8; tx = rb.x + PAD + (mv.c + mv.cols / 2) * CS; ty = rb.y + LIFT + PAD + (mv.r + mv.rows / 2) * CS; }
  return { sx, sy, tx, ty };
}
async function fastDrag(mv) { const g = await geom(mv); await p.mouse.move(g.sx, g.sy); await p.mouse.down(); await p.mouse.move(g.tx, g.ty, { steps: 6 }); await p.mouse.up(); }
async function filmDrag(mv) {
  const g = await geom(mv); const f0 = frames.length;
  await frames_(10);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: g.sx, y: g.sy, button: 'none', pointerType: 'mouse' });
  await mouse('mousePressed', g.sx, g.sy); await frames_(3);
  const K = 18; for (let k = 1; k <= K; k++) { const e = k / K, q = e < .5 ? 2 * e * e : 1 - Math.pow(-2 * e + 2, 2) / 2;
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: g.sx + (g.tx - g.sx) * q, y: g.sy + (g.ty - g.sy) * q, button: 'left', buttons: 1, pointerType: 'mouse' }); await frame(); }
  await frames_(6); const fUp = frames.length;
  await mouse('mouseReleased', g.tx, g.ty); await frames_(42);
  return { f0, fUp };
}
for (let i = 0; i <= TO + 2; i++) {
  if (i === FROM && !vt) { vt = true; await p.waitForTimeout(1500); await cdp.send('Emulation.setVirtualTimePolicy', { policy: 'pause' }); await frames_(15); }
  const mv = await p.evaluate(() => window.__plan()); if (!mv) break;
  let fr = null;
  if (vt) fr = await filmDrag(mv); else { await fastDrag(mv); await p.waitForTimeout(160); }
  const st = await p.evaluate((m) => window.__apply(m), mv);
  const ui = +(await p.locator('#score').innerText());
  log.push({ i, frameStart: fr && fr.f0, frameUp: fr && fr.fUp, move: mv.discard ? 'discard' : `slot${mv.slot}@${mv.r},${mv.c}`, ...st, ui, sync: ui === st.score });
  if (ui !== st.score) { console.log('DESYNC', i, ui, st.score); break; }
  if (st.over) { if (vt) await frames_(90); break; }
}
if (vt) await frames_(15);
const audio = await p.evaluate(() => window.__audio);
await b.close();
fs.writeFileSync(`${OUT}/log.json`, JSON.stringify({ seed: SEED, mode: MODE, from: FROM, to: TO, fps: 30, frames, audio, moves: log }, null, 1));
const L = log.at(-1); console.log('moves', log.length, 'frames', frames.length, 'audio', audio.length, 'last', L.i, L.score, L.over, L.cause, 'desync', log.filter(x => !x.sync).length);
