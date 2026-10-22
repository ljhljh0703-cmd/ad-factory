// 끝에서 끝 시험(봇): 게임 → 수집기 → 파일. 사람 데이터가 아니라 봇 판이다.
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import * as D from '../adapters/jelly-panic/driver.mjs';
const FILE = process.argv[2]; const plan = JSON.parse(process.argv[3]);
const b = await chromium.launch();
for (const [k, s] of plan.entries()) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 } }); const page = await ctx.newPage();
  await page.goto(`file://${FILE}?seed=${s.seed}&src=${s.src}&ad=${s.ad}`);
  const T = { page, seed: s.seed, opt: {}, recording: false, frame: 0, async frames() {}, async drag() {} };
  await D.boot(T);
  for (let i = 0; i < (s.moves ?? 300); i++) { const st = await D.step(T, i, {}); if (!st || st.over) break; }
  await page.waitForTimeout(600);
  if (s.restart) { await page.click('#replay'); await page.waitForTimeout(300); }
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange'))); // 숨김 전 묶음 보내기는 실제 탭 닫기로만 됨: 여기선 end 에서 이미 보냄
  await page.waitForTimeout(300); await page.close({ runBeforeUnload: true }); await new Promise(r => setTimeout(r, 300)); await ctx.close();
  console.log(k, s.src, s.ad);
}
await b.close();
