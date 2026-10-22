// 익명 기록 시험: 로컬 index.html 을 열어 봇으로 한 판 끝까지 두고, 남는 기록이 약속한 항목만인지 본다.
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import * as D from '../driver.mjs';
const FILE = process.argv[2] || '/home/claude/jelly-panic/index.html';
const b = await chromium.launch();
async function run(q) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 } }); const page = await ctx.newPage();
  const net = []; page.on('request', r => { if (!r.url().startsWith('file:')) net.push(r.url()); });
  await page.goto('file://' + FILE + q);
  const T = { page, seed: 71, opt: {}, recording: false, frame: 0, async frames() {}, async drag() {} };
  await D.boot(T);
  for (let i = 0; i < 300; i++) { const s = await D.step(T, i, {}); if (!s || s.over) break; }
  await page.waitForTimeout(800);
  await page.click('#replay'); await page.waitForTimeout(300);
  const ev = await page.evaluate(() => window.__track);
  await ctx.close(); return { ev, net };
}
const A = await run('?seed=71&src=tiktok&ad=A1-flip');
const types = A.ev.events.map(e => e.type);
const keys = [...new Set(A.ev.events.flatMap(e => Object.keys(e)))].sort();
console.log('types', types.join(','));
console.log('keys', keys.join(','));
console.log('end', JSON.stringify(A.ev.events.find(e => e.type === 'end')));
console.log('second start seed', A.ev.events.filter(e => e.type === 'start')[1]?.seed, 'network', A.net.length);
const B = await run('?seed=71&notrack');
console.log('notrack off', B.ev.off, 'events', B.ev.events.length);
const ok = types.join(',') === 'start,first_move,end,restart,start' && A.ev.events[0].src === 'tiktok' && A.ev.events[0].ad === 'A1-flip' && A.ev.events[0].seed === 71
  && A.ev.events[4].seed === null && A.net.length === 0 && B.ev.off === true && B.ev.events.length === 0
  && keys.every(k => ['v','sid','n','sec','type','src','ad','mode','seed','after','cause','score','placements','rescued','prev'].includes(k));
console.log(ok ? '통과' : '실패'); await b.close(); process.exit(ok ? 0 : 1);
