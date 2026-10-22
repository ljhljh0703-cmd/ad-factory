import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import * as D from '../driver.mjs';
const b = await chromium.launch();
for (const seed of [1,1,2]) {
  const ctx = await b.newContext({ viewport:{width:390,height:844} }); const page = await ctx.newPage();
  const T = { page, seed, opt:{}, recording:false, frame:0, async idle(ms){await page.waitForTimeout(ms);}, async frames(){}, async tapEl(sel){await page.locator(sel).first().click();} };
  await page.goto(D.url(seed), { waitUntil:'networkidle', timeout:120000 });
  await page.waitForFunction(()=>document.documentElement.dataset.gameReady==='true',null,{timeout:120000});
  const u0 = page.url();
  await D.boot(T);
  const built=[]; for(let i=0;i<5;i++){ const s=await D.step(T,i,{}); built.push(s.toast); }
  console.log(seed, u0, page.url(), built.join(' | '));
  await ctx.close();
}
await b.close();
