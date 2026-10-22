// 보석타워 장면 찾기: 판 번호마다 공개판을 6배속으로 끝까지(또는 웨이브 상한까지) 두고 수마다 화면 상태를 남긴다.
//   node mine.mjs <from_seed> <to_seed> [max_wave] > scenes.json
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import * as D from './driver.mjs';
const [A, B, MAXW] = [+process.argv[2] || 1, +process.argv[3] || 3, +process.argv[4] || 12];
const b = await chromium.launch(); const out = [];
for (let seed = A; seed <= B; seed++) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 }); const page = await ctx.newPage();
  const T = { page, seed, opt: {}, recording: false, frame: 0, async idle(ms) { await page.waitForTimeout(ms); }, async frames() {},
    async tapEl(sel) { await page.locator(sel).first().click(); } };
  await page.goto(D.url(seed), { waitUntil: 'networkidle', timeout: 120000 }); await D.boot(T);
  const steps = [];
  for (let i = 0; i < 400; i++) { const s = await D.step(T, i, {}); if (!s) break; steps.push({ i, ...s }); if (s.over || s.wave > MAXW) break; }
  for (const s of steps) {
    if (s.act.종류 === '웨이브' && s.lifeLost >= 2) out.push({ kind: 'life-loss', seed, i: s.i, wave: s.wave, lifeLost: s.lifeLost, life: s.life });
    if (s.act.종류 === '조합') out.push({ kind: 'combine', seed, i: s.i, wave: s.wave, gem: s.act.보석, toast: s.toast });
    if (s.combine) out.push({ kind: 'special-ready', seed, i: s.i, wave: s.wave, roster: s.roster });
  }
  let trace = null; try { trace = await D.exportTrace(page); } catch (e) { console.error('trace 실패', String(e).slice(0, 120)); }
  const L = steps.at(-1); if (L?.over) out.push({ kind: 'game-over', seed, i: L.i, wave: L.wave, end: L.end });
  out.push({ kind: 'summary', seed, steps: steps.length, lastWave: L?.wave, life: L?.life, over: L?.over, hashes: steps.map(s => s.hash), ticks: steps.map(s => s.tick), acts: steps.map(s => s.act), trace });
  console.error(seed, steps.length, 'wave', L?.wave, 'life', L?.life, 'over', L?.over);
  await ctx.close();
}
await b.close(); console.log(JSON.stringify(out, null, 1));
