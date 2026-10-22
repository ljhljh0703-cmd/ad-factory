// 게임 어댑터 공통 녹화기. 실제 공개판을 브라우저로 열고, 어댑터의 봇이 한 수씩 둔다.
// from 번째 수부터 to 번째 수까지만 가상 시각(1/30초씩)으로 멈춰 가며 화면을 찍는다. 그 밖은 빨리 둔다.
// 산출: <out>/frames/00000.jpg …, <out>/log.json (render.py 와 녹화본 대조가 읽는 형식)
//
//   node recorder.mjs <어댑터 폴더> <seed> <from> <to> <out> [override.json] [options.json]
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'fs'; import path from 'path'; import { pathToFileURL } from 'url';

const [AD, SEED, FROM, TO, OUT, OVF, OPTF] = [process.argv[2], +process.argv[3], +process.argv[4], +process.argv[5], process.argv[6], process.argv[7], process.argv[8]];
const manifest = JSON.parse(fs.readFileSync(path.join(AD, 'adapter.json'), 'utf8'));
const driver = await import(pathToFileURL(path.resolve(AD, manifest.입력.드라이버)).href);
const OV = OVF && OVF !== '-' ? JSON.parse(fs.readFileSync(OVF, 'utf8')) : {};
const OPT = OPTF ? JSON.parse(fs.readFileSync(OPTF, 'utf8')) : {};
const S = manifest.화면; const FPS = S.녹화_fps || 30;
fs.mkdirSync(`${OUT}/frames`, { recursive: true });

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: S.뷰포트[0], height: S.뷰포트[1] }, deviceScaleFactor: S.기기배율 || 3 });
if (driver.initScript) await ctx.addInitScript(driver.initScript);
await ctx.addInitScript(AUDIO_HOOK);
const p = await ctx.newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e)));
const cdp = await ctx.newCDPSession(p);
const frames = []; let vt = false;
async function advance(ms) { await new Promise(res => { cdp.once('Emulation.virtualTimeBudgetExpired', res); cdp.send('Emulation.setVirtualTimePolicy', { policy: 'advance', budget: ms }); }); }
async function frame() {
  await advance(1000 / FPS);
  const n = frames.length; const t = await p.evaluate(() => performance.timeOrigin + performance.now());
  const s = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 90, clip: { x: 0, y: 0, width: S.뷰포트[0], height: S.뷰포트[1], scale: S.찍는_배율 } });
  fs.writeFileSync(`${OUT}/frames/${String(n).padStart(5, '0')}.jpg`, Buffer.from(s.data, 'base64')); frames.push({ n, wall: t });
}
async function wait(k) { for (let j = 0; j < k; j++) await frame(); }
// 드라이버에 넘기는 도구: 지금 녹화 중이면 프레임을 찍으며, 아니면 실제 시간으로 기다린다.
const T = {
  page: p, cdp, seed: SEED, opt: OPT, get recording() { return vt; }, get frame() { return frames.length; },
  async frames(k) { if (vt) await wait(k); },
  async idle(ms) { if (vt) await wait(Math.round(ms * FPS / 1000)); else await p.waitForTimeout(ms); },
  async tap(x, y) {
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none', pointerType: 'mouse' });
    await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1, pointerType: 'mouse' });
    if (vt) await wait(3); else await p.waitForTimeout(40);
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', buttons: 0, clickCount: 1, pointerType: 'mouse' });
  },
  async tapEl(sel) { const bb = await p.locator(sel).first().boundingBox(); if (!bb) throw Error('안 보임: ' + sel); await T.tap(bb.x + bb.width / 2, bb.y + bb.height / 2); },
  async drag(sx, sy, tx, ty, steps = 18) {
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: sx, y: sy, button: 'none', pointerType: 'mouse' });
    await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: sx, y: sy, button: 'left', buttons: 1, clickCount: 1, pointerType: 'mouse' });
    if (vt) await wait(3);
    for (let k = 1; k <= steps; k++) { const e = k / steps, q = e < .5 ? 2 * e * e : 1 - Math.pow(-2 * e + 2, 2) / 2;
      await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: sx + (tx - sx) * q, y: sy + (ty - sy) * q, button: 'left', buttons: 1, pointerType: 'mouse' });
      if (vt) await frame(); }
    if (vt) await wait(6);
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: tx, y: ty, button: 'left', buttons: 0, clickCount: 1, pointerType: 'mouse' });
  },
};

await p.goto(driver.url(SEED, OPT), { waitUntil: 'networkidle', timeout: 120000 });
await driver.boot(T);
const steps = [];
for (let i = 0; i <= TO + (S.끝_뒤_수 ?? 2); i++) {
  if (i === FROM && !vt) { vt = true; await p.waitForTimeout(1500); await cdp.send('Emulation.setVirtualTimePolicy', { policy: 'pause' }); await wait(15); }
  const f0 = frames.length;
  const st = await driver.step(T, i, OV);   // 한 수 두고 그 결과(그림자 상태와 화면 대조 포함)를 돌려준다
  if (!st) break;
  steps.push({ i, frameStart: vt ? f0 : null, frameEnd: vt ? frames.length : null, ...st });
  if (st.sync === false) { console.log('DESYNC', i); break; }
  if (st.over) { if (vt) await wait(S.끝_프레임 ?? 90); break; }
  if (i >= TO && !vt) break;
}
if (vt) await wait(15);
const audio = await p.evaluate(() => window.__audio || []);
const extra = driver.geometry ? await driver.geometry(T) : {};
await b.close();
fs.writeFileSync(`${OUT}/log.json`, JSON.stringify({ adapter: manifest.id, seed: SEED, from: FROM, to: TO, fps: FPS, scale: S.찍는_배율, crop: S.자르기, ...extra, frames, audio, moves: steps, errors: errs }, null, 1));
const L = steps.at(-1) || {};
console.log(JSON.stringify({ steps: steps.length, frames: frames.length, audio: audio.length, last: L, desync: steps.filter(x => x.sync === false).length, errors: errs.length }));

// 소리 기록: 게임이 WebAudio로 만드는 음(주파수·파형·길이·크기)을 시각과 함께 남긴다. 나중에 같은 값으로 합성.
function AUDIO_HOOK() {
  window.__audio = [];
  class P { constructor(o, k) { this.o = o; this.k = k; this.value = 1; }
    setValueAtTime(v, t) { this.o[this.k] = v; this.o[this.k + 'T'] = t; } exponentialRampToValueAtTime(v, t) { this.o[this.k + 'To'] = v; this.o[this.k + 'End'] = t; }
    linearRampToValueAtTime(v, t) { this.exponentialRampToValueAtTime(v, t); } cancelScheduledValues() {} }
  class FakeAC { constructor() { this.t0 = performance.now(); this.state = 'running'; this.destination = {}; this.sampleRate = 44100; }
    get currentTime() { return (performance.now() - this.t0) / 1000; }
    resume() { return Promise.resolve(); } suspend() { return Promise.resolve(); } close() { return Promise.resolve(); }
    createGain() { const g = { connect() { return g; }, disconnect() {} }; g.gain = new P(g, 'vol'); return g; }
    createOscillator() { const ac = this, o = { type: 'sine', connect(g) { this.g = g; return g; }, disconnect() {} };
      o.frequency = new P(o, 'freq'); o.detune = new P(o, 'det');
      o.start = (t) => { o.t = t ?? ac.currentTime; };
      o.stop = (t) => { window.__audio.push({ wall: performance.timeOrigin + ac.t0 + o.t * 1000, type: o.type, freq: o.freq, slide: o.freqTo || null, dur: (o.freqEnd || (o.g && o.g.volEnd) || t) - o.t, vol: o.g ? o.g.vol : 0.14 }); };
      return o; } }
  window.AudioContext = FakeAC; window.webkitAudioContext = FakeAC;
}
