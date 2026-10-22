// 보석타워 드라이버: 공개 플레이 테스트(레이스·이지)를 화면 조작(탭)으로만 진행한다.
// 한 수 = 건설 탭 하나, 남길 보석 고르기(또는 같은 보석 조합) 하나, 웨이브 끝까지 기다리기 하나.
// 그림자 판이 없어 화면 대조 대신 게임이 내는 결정론 해시(stateHash)를 수마다 남긴다. 같은 판 번호·같은 수면 같은 해시여야 한다.
export const url = (seed) => `https://ljhljh0703-cmd.github.io/uzmap-forge/web/?seed=${seed}`;
const HUD = () => ({ gold: +hudGold.textContent || 0, life: +hudLife.textContent || 0, wave: +hudWaveNum.textContent || 0, phase: hudPhase.textContent,
  run: runState.dataset.state, toast: actionFeedback.hidden ? '' : actionFeedback.textContent, eng: engineTag.textContent,
  cells: buildCells.hidden ? 0 : buildCells.children.length, built: [...document.querySelectorAll('.round-slot[data-unit-id]:not([data-unit-id=""])')].map(b => b.title),
  roster: [...gemRoster.querySelectorAll('button')].map(b => b.textContent), creeps: combatCount.textContent,
  over: getComputedStyle(gameOver).display !== 'none' && gameOver.offsetParent !== null, goTitle: goTitle.textContent, goSummary: goSummary.innerText.slice(0, 200),
  hash: mHash.textContent, tick: +mTick.textContent || 0, dlg: sourceDialog.hidden ? '' : sourceDialogTitle.textContent,
  combine: !findCombination.hidden });
export const state = (p) => p.evaluate(HUD);
export async function boot(T) {
  const p = T.page;
  await p.waitForFunction(() => document.documentElement.dataset.gameReady === 'true', null, { timeout: 120000 });
  if (T.opt.trace) {
    // 장면 바로 앞 순간으로 되돌린 뒤(게임 자체 복원, 결정론 해시까지 맞아야 성공) 이어서 둔다
    const st = await restore(p, T.opt.trace, T.opt.tick, T.opt.hash);
    if (st.hash !== T.opt.hash) throw Error(`복원 해시 다름 ${st.hash} != ${T.opt.hash}`);
    await p.click('#play');
    await p.evaluate((v) => { const s = document.getElementById('speed'); s.value = String(v); s.dispatchEvent(new Event('input', { bubbles: true })); }, T.opt.speed || 6);
    return;
  }
  await p.click('#modeRace');
  await p.waitForSelector('#sourceDialogButtons button', { timeout: 30000 });
  await p.click(`#sourceDialogButtons button >> nth=${T.opt.difficulty ?? 0}`);   // 0 = 이지
  await p.waitForFunction(() => !buildCells.hidden && buildCells.children.length > 0, null, { timeout: 30000 });
  if (!T.opt.realSpeed) await p.evaluate(() => { const s = document.getElementById('speed'); s.value = '6'; s.dispatchEvent(new Event('input', { bubbles: true })); });
}
// 건설 칸 고르기: 판 가운데 세로줄에 가까운 칸부터(모든 길에 사거리가 닿게). 미리 정한 칸이 있으면 그것.
async function pickCell(p, OV, i) {
  const cells = await p.$$eval('#buildCells .build-cell', bs => bs.map(b => ({ id: b.dataset.cell, label: b.getAttribute('aria-label') })));
  const rc = c => { const m = c.label.match(/(\d+)행 (\d+)열/); return m ? [+m[1], +m[2]] : [0, 0]; };
  if (OV[i]?.cell) return cells.find(c => c.id === OV[i].cell);
  const rows = cells.map(c => rc(c)[0]), cols = cells.map(c => rc(c)[1]);
  const cr = (Math.min(...rows) + Math.max(...rows)) / 2, cc = (Math.min(...cols) + Math.max(...cols)) / 2;
  cells.sort((a, b) => { const [ra, ca] = rc(a), [rb, cb] = rc(b); return (Math.abs(ca - cc) * 2 + Math.abs(ra - cr)) - (Math.abs(cb - cc) * 2 + Math.abs(rb - cr)) || a.id.localeCompare(b.id); });
  return cells[0];
}
const RANK = ['최하급', '하급', '중급', '상급', '최상급', '완벽한'];
const rank = n => Math.max(0, ...RANK.map((r, k) => n.startsWith(r + ' ') ? k : -1));
export async function step(T, i, OV) {
  const p = T.page; let s = await state(p); const before = s;
  if (s.over) return null;
  let act;
  if (s.dlg) { await T.tapEl('#sourceDialogButtons button'); act = { 종류: '창 닫기', 창: s.dlg }; }
  else if (s.cells > 0 && s.built.length < 5) {
    const c = await pickCell(p, OV, i); await T.tapEl(`#buildCells [data-cell="${c.id}"]`); act = { 종류: '건설', 칸: c.id, 위치: c.label };
  } else if (s.built.length >= 5 || /선택하거나/.test(s.eng)) {
    // 같은 이름 둘 이상이면 조합, 아니면 등급 높은 것(같으면 앞쪽)을 남긴다
    const names = s.built; const dup = names.findIndex((n, k) => names.indexOf(n) !== k);
    const want = OV[i]?.slot ?? (dup >= 0 ? names.indexOf(names[dup]) + 1 : names.map((n, k) => [rank(n), -k]).sort((a, b) => b[0] - a[0] || b[1] - a[1]).map(x => -x[1])[0] + 1);
    const how = OV[i]?.how ?? (dup >= 0 ? 'castA007' : 'castA009');
    await T.tapEl(`.round-slot[data-slot="${want}"]`); await T.idle(300);
    const ok = await p.$(`#${how}:not([disabled])`);
    await T.tapEl(`#${ok ? how : 'castA009'}`); act = { 종류: ok && how === 'castA007' ? '조합' : '선택', 칸: want, 보석: names[want - 1] };
  } else {
    // 웨이브 진행: 건설 칸이 다시 나오거나 판이 끝날 때까지 기다린다(최대 90초 게임 시간)
    const t0 = Date.now(); let lifeMin = s.life;
    for (let k = 0; k < (T.recording ? 300 : 900); k++) {
      await T.idle(T.recording ? 300 : 100); const q = await state(p); lifeMin = Math.min(lifeMin, q.life);
      if (q.over || q.cells > 0 || q.dlg || /선택하거나/.test(q.eng)) break;
    }
    act = { 종류: '웨이브', 기다린_ms: Date.now() - t0 };
  }
  await T.idle(T.recording ? 400 : 250);
  s = await state(p);
  return { act, wave: s.wave, gold: s.gold, life: s.life, lifeLost: before.life - s.life, toast: s.toast, built: s.built, roster: s.roster, combine: s.combine,
           over: s.over, end: s.over ? { 제목: s.goTitle, 요약: s.goSummary } : null, hash: s.hash, tick: s.tick, sync: null };
}
export async function geometry(T) { return { board: await T.page.locator('#cv').boundingBox() }; }

// 게임 자체 조작 기록(uzmap-ui-input-v1)을 꺼낸다. 멈춘 상태에서 메뉴의 재생 기록 칸을 연다.
export async function exportTrace(p) {
  const playing = await p.evaluate(() => runState.dataset.state === 'playing');
  if (playing) await p.click('#play');
  await p.evaluate(() => { if (gameDrawer.hidden) researchToggle.click(); replayDetails.open = true; });
  await p.waitForFunction(() => replayInput.value.length > 0, null, { timeout: 15000 });
  const t = JSON.parse(await p.$eval('#replayInput', e => e.value));
  await p.evaluate(() => { replayDetails.open = false; if (!gameDrawer.hidden) drawerClose.click(); });
  return t;
}
// 조작 기록을 tick 시점까지 잘라 그 순간 상태로 정확히 되돌린다(게임의 「조작 기록으로 이어하기」).
export async function restore(p, trace, tick, hash) {
  const t = { ...trace };
  if (tick != null) { t.actions = (trace.actions || []).filter(a => (a.tick ?? a.t ?? 0) < tick); t.tick = tick; t.stateHash = hash; delete t.sourceState; }
  await p.evaluate((x) => { restoreInput.value = x; importRun.click(); }, JSON.stringify(t));
  await p.waitForFunction(() => /정확히 복원/.test(actionFeedback.textContent) || runState.dataset.state === 'paused', null, { timeout: 120000 });
  return state(p);
}
