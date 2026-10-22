// 실제 수집기까지 시험: 로컬 index.html(수집 주소 들어간 판)로 한 판 두고 탭을 닫은 뒤, 내려받기로 기록이 들어왔는지 본다.
// 시험 기록은 src=test 로 남겨 성과 보고에서 뺀다.
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import * as D from '../driver.mjs';
const [FILE, KEY] = [process.argv[2], process.argv[3]];
const ad = 'live' + Date.now().toString(36);
const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 390, height: 844 } }); const page = await ctx.newPage();
await page.goto(`file://${FILE}?seed=71&src=test&ad=${ad}`);
const T = { page, seed: 71, opt: {}, recording: false, frame: 0, async frames() {}, async drag() {} };
await D.boot(T);
for (let i = 0; i < 300; i++) { const s = await D.step(T, i, {}); if (!s || s.over) break; }
await page.waitForTimeout(800); await page.click('#replay'); await page.waitForTimeout(300);
await page.close({ runBeforeUnload: true }); await new Promise(r => setTimeout(r, 2500)); await b.close();
const day = new Date().toISOString().slice(0, 10);
const txt = await (await fetch(`https://jelly-panic-collector.vercel.app/api/export?day=${day}`, { headers: { 'x-export-key': KEY } })).text();
const rows = txt.split('\n').filter(Boolean).map(JSON.parse).filter(e => e.ad === ad);
console.log(ad, rows.map(e => e.type).join(','));
process.exit(rows.map(e => e.type).join(',') === 'start,first_move,end,restart,start' ? 0 : 1);
