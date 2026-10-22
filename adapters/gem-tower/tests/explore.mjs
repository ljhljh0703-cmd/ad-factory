import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 })).newPage();
const errs=[]; p.on('pageerror', e=>errs.push(String(e)));
await p.goto('https://ljhljh0703-cmd.github.io/uzmap-forge/?seed=7', { waitUntil: 'networkidle', timeout: 120000 });
await p.waitForFunction(()=>document.documentElement.dataset.gameReady==='true',null,{timeout:120000});
const st = () => p.evaluate(()=>({gold:hudGold.textContent,life:hudLife.textContent,wave:hudWaveNum.textContent,phase:hudPhase.textContent,run:runState.textContent,
  fb:actionFeedback.hidden?'':actionFeedback.textContent,dlg:sourceDialog.hidden?'':sourceDialogTitle.textContent+' :: '+[...sourceDialogButtons.querySelectorAll('button')].map(b=>b.textContent).join('/'),
  cells:buildCells.hidden?0:buildCells.children.length, roster:[...gemRoster.querySelectorAll('button')].map(b=>b.textContent).join(','), eng:engineTag.textContent, msg:msg.style.display==='none'?'':msg.innerText.slice(0,80)}));
let n=0; const shot=async(t)=>{await p.screenshot({path:`e${String(++n).padStart(2,'0')}.png`}); console.log(n,t,JSON.stringify(await st()));};
await shot('start');
await p.click('#modeRace'); await p.waitForTimeout(800); await shot('race');
await p.waitForSelector('#sourceDialogButtons button',{timeout:20000}).catch(()=>console.log('no dialog')); await shot('dialog');
const dl = await p.$$('#sourceDialogButtons button'); if (dl.length) { await dl[0].click(); await p.waitForTimeout(1500); await shot('dialog0'); }
for (let k=0;k<5;k++){ const c = await p.$$('#buildCells .build-cell'); if(!c.length){console.log('no cells');break;}
  await c[Math.floor(c.length*(k+1)/7)].click(); await p.waitForTimeout(700); await shot('build'+k); }
await p.waitForTimeout(3000); await shot('built');
const slots = (await p.$$('button')); let slot=null; for(const h of slots){ if((await h.isVisible()) && (await h.textContent()).trim()==='1'){slot=h;break;} }
console.log('slot html', slot && await slot.evaluate(b=>b.outerHTML.slice(0,200)));
if(slot){await slot.click(); await p.waitForTimeout(600); await shot('slot1');}
console.log(await p.$$eval('#gemPanel button', bs=>bs.filter(b=>b.offsetParent).map(b=>b.id+'|'+b.textContent.trim()+'|'+b.disabled).join(' ; ')));
if (await p.$('#castA009:not([disabled])')) { await p.click('#castA009'); await p.waitForTimeout(1500); await shot('chosen'); }
for (let s=0;s<6;s++){ await p.waitForTimeout(5000); await shot('wait'+s); }
console.log(await p.$$eval('button:not([hidden])', bs=>bs.filter(b=>b.offsetParent&&!b.classList.contains('build-cell')).map(b=>b.id+'|'+b.textContent.trim().slice(0,24)).join(' ; ')));
console.log('errs',errs); await b.close();
