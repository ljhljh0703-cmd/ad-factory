// 앱 스모크: 실제 Electron 창을 열어 탭마다 화면을 찍고, 엔진과 이어지는지 본다.
import { _electron as electron } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import path from 'path'; import fs from 'fs';
const here = path.dirname(new URL(import.meta.url).pathname), out = process.argv[2] || path.join(here, 'shots');
fs.mkdirSync(out, { recursive: true });
const app = await electron.launch({ args: [path.join(here, '..'), '--no-sandbox'], executablePath: path.join(here, '..', 'node_modules', 'electron', 'dist', 'electron') });
const win = await app.firstWindow(); const errs = []; win.on('pageerror', (e) => errs.push(String(e)));
await win.setViewportSize({ width: 1280, height: 860 });
await win.waitForSelector('.card', { timeout: 60000 });
for (const tab of ['home', 'plan', 'jobs', 'review', 'regress', 'facts', 'publish', 'perf']) {
  await win.click(`#nav button[data-tab="${tab}"]`); await win.waitForTimeout(700);
  await win.screenshot({ path: path.join(out, `${tab}.png`) });
}
// 승인 관문: 체크 없이 승인하면 막히는지
await win.click('#nav button[data-tab="publish"]');
await win.click('[data-approve]'); await win.waitForTimeout(300);
const t1 = await win.textContent('#toast');
const cards = await win.$$eval('.card .k', (e) => e.map((x) => x.textContent));
console.log(JSON.stringify({ cards, approveWithoutCheck: t1, errors: errs }));
await app.close();
