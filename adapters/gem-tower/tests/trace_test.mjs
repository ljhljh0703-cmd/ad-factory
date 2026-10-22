import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import * as D from '../driver.mjs';
const b = await chromium.launch();
async function open(seed){ const ctx = await b.newContext({ viewport:{width:390,height:844} }); const page = await ctx.newPage();
  const T = { page, seed, opt:{}, recording:false, frame:0, async idle(ms){await page.waitForTimeout(ms);}, async frames(){}, async tapEl(sel){await page.locator(sel).first().click();} };
  await page.goto(D.url(seed), { waitUntil:'networkidle', timeout:120000 }); return T; }
const A = await open(1); await D.boot(A.page ? A : A);
for (let i=0;i<20;i++){ const s=await D.step(A,i,{}); if(!s||s.wave>=3) break; }
await A.page.click('#play'); // 일시정지
await A.page.waitForTimeout(500);
const s1 = await D.state(A.page);
await A.page.click('#researchToggle'); await A.page.evaluate(()=>{replayDetails.open=true;}); await A.page.waitForTimeout(1500); const trace = await A.page.$eval('#replayInput', t=>t.value);
console.log('state A', s1.wave, s1.tick, s1.hash, 'trace len', trace.length, trace.slice(0,300));
const B = await open(1);
await B.page.waitForFunction(()=>document.documentElement.dataset.gameReady==='true',null,{timeout:120000});
await B.page.click('#researchToggle'); await B.page.waitForTimeout(400); await B.page.evaluate(()=>{document.getElementById('replayDetails').open=true;});
await B.page.evaluate((t)=>{restoreInput.value=t; importRun.click();}, trace);
await B.page.waitForTimeout(8000);
const s2 = await D.state(B.page); console.log('state B', s2.wave, s2.tick, s2.hash, s2.run, await B.page.$eval('#actionFeedback',e=>e.textContent));
await b.close();
