// 광고 공장 화면. 데이터는 전부 엔진의 dashboard 응답 하나에서 읽고, 버튼은 엔진 명령을 부른다.
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const TITLES = { home: '한눈에', plan: '기획', jobs: '작업', review: '사람 검토', regress: '회귀 감시', facts: '사실표 대조', publish: '게시 승인', perf: '성과' };
let D = null;

function toast(msg, err) { const t = $('#toast'); t.textContent = msg; t.className = 'toast' + (err ? ' err' : ''); t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 4200); }
async function call(args, quiet) {
  $('#busy').hidden = false;
  try {
    const r = await window.adf.call(args);
    if (!r.ok) { toast(r.error || '실패', true); return null; }
    if (!quiet) toast('완료');
    return r.data;
  } finally { $('#busy').hidden = true; }
}
const badge = (s) => {
  const cls = { 완료: 'b-ok', 통과: 'b-ok', 승인: 'b-ok', 연습완료: 'b-ok', 게시됨: 'b-ok', 처리: 'b-ok', 실패: 'b-bad', 막음: 'b-bad', 점검실패: 'b-bad', '승인무효(바뀜)': 'b-bad', 외부응답대기: 'b-wait', 사람확인대기: 'b-wait', 승인대기: 'b-wait', 대기: 'b-wait', 진행: 'b-run', 실행: 'b-run' }[s] || '';
  return `<span class="badge ${cls}">${esc(s)}</span>`;
};
const pct = (v) => (v == null ? '–' : (v * 100).toFixed(1) + '%');
const short = (o) => {
  if (o == null) return '';
  if (typeof o !== 'object') return esc(String(o)).slice(0, 220);
  return '<div class="kv">' + Object.entries(o).slice(0, 6).map(([k, v]) => `<span><b>${esc(k)}</b>${esc(typeof v === 'object' ? JSON.stringify(v) : v).slice(0, 90)}</span>`).join('') + '</div>';
};
let ROOT = '';

async function load() {
  const d = await call(['dashboard'], true); if (!d) return; D = d;
  $('#cReview').textContent = d.검토.통계.대기 || '';
  $('#cPending').textContent = d.최근_작업.reduce((n, j) => n + (j.응답_대기 || []).length, 0) || '';
  $('#cPublish').textContent = d.게시.filter((p) => p.상태 === '승인대기').length || '';
  renderHome(); renderJobs(); renderReview(); renderRegress(); renderFacts(); renderPublish(); renderPlan(); renderPerf();
}

function renderHome() {
  const d = D, lastG = [...d.회귀].reverse().find((r) => r.묶음.length) || d.회귀.at(-1);
  const gate = lastG?.결과?.관문 || '없음', dev = lastG?.결과?.묶음별?.dev || {};
  const factsBad = Object.values(d.사실표).filter((f) => f.결론 !== '통과').length;
  const wait = d.최근_작업.filter((j) => j.상태 === '외부응답대기' || j.상태 === '사람확인대기').length;
  const cards = [
    ['회귀 관문', gate, lastG ? `${lastG.id} · 판정 일치 ${pct(dev.판정_일치)} · 비싼 오류 ${(dev['비싼_오류(반려를_통과시킴)'] || []).length}건` : '', 'regress'],
    ['사실표 대조', factsBad ? `어긋남 ${factsBad}개 게임` : '모두 통과', Object.values(d.사실표).map((f) => f.이름).join(' · '), 'facts'],
    ['사람 검토 대기', `${d.검토.통계.대기}건`, `처리 ${d.검토.통계.처리} · 뒤집음 ${d.검토.통계.뒤집음} · 평가셋 후보 ${d.검토.통계.평가셋_후보}`, 'review'],
    ['게시 승인 대기', `${d.게시.filter((p) => p.상태 === '승인대기').length}편`, `감사 기록 ${d.감사.줄}줄 · ${d.감사.온전함 ? '온전함' : '깨짐'}`, 'publish'],
    ['응답 기다리는 작업', `${wait}개`, Object.entries(d.작업).map(([k, v]) => `${k} ${v}`).join(' · '), 'jobs'],
    ['모델 사용량', `${((d.비용.입력_토큰 + d.비용.출력_토큰) / 1000).toFixed(1)}k 토큰`, (d.비용.구독_환산_달러 ? `Claude Code 구독 · API 값으로 치면 $${d.비용.구독_환산_달러.toFixed(2)}` : '') + (d.비용.추정_포함 ? ' · 일부는 글자 수로 어림' : ''), 'jobs'],
  ];
  $('#homeCards').innerHTML = cards.map(([k, v, s, tab]) => `<div class="card click" data-go="${tab}"><div class="k">${k}</div><div class="v">${esc(v)}</div><div class="s">${esc(s)}</div></div>`).join('');
  $('#homeJobs').innerHTML = jobsTable(d.최근_작업.slice(0, 8));
}

function jobsTable(rows) {
  if (!rows.length) return '<div class="empty">작업이 없습니다</div>';
  return `<table><tr><th>작업</th><th>단계</th><th>상태</th><th>결과</th><th>모델·비용</th><th></th></tr>${rows.map((j) => `
    <tr><td>${j.id}<div class="meta">${esc(j.묶음 || '')}</div></td><td>${esc(j.단계)}</td><td>${badge(j.상태)}</td>
    <td>${j.오류 ? `<span class="b-bad badge">오류</span> ${esc(j.오류)}` : short(j.결과)}</td>
    <td class="num">${esc(j.모델 || '')}${j.토큰 && j.토큰[0] != null ? `<div class="meta">${j.토큰[0]}/${j.토큰[1]} 토큰${j.추정 ? ' (추정)' : ''}${j.달러 != null ? ` · $${j.달러}` : ''}</div>` : ''}</td>
    <td>${(j.응답_대기 || []).map((r) => `<button data-respond="${j.id}" data-key="${esc(r.replace(/^request-|\.md$/g, ''))}">${esc(r)} 응답 넣기</button>`).join(' ')}${j.상태 === '실패' || j.상태 === '막음' ? `<button data-retry="${j.id}">다시</button>` : ''}</td></tr>`).join('')}</table>`;
}
function renderJobs() { $('#jobsTable').innerHTML = jobsTable(D.최근_작업); }

function reviewCard(it, done) {
  const c = it.내용 || {};
  const body = [c.제목 && `제목: ${c.제목}`, c.첫컷 && `첫 컷: ${c.첫컷}`, ...(c.컷 || []).map((k, i) => `컷 ${i + 1}: ${k.장면 || k}`), c.자막 && `자막: ${c.자막.join(' / ')}`, c.끝 && `끝: ${c.끝}`].filter(Boolean).join('\n');
  return `<div class="item"><h3>${it.id} · ${esc(it.소재)} ${badge(done ? it.결정 : it.상태)}${it.뒤집음 ? '<span class="badge b-bad">AI 판정 뒤집음</span>' : ''}</h3>
    <div class="meta">${esc(it.출처)} · AI: ${esc(it.AI_판정)} · ${esc(it.AI_이유)}</div><pre>${esc(body || JSON.stringify(c, null, 1))}</pre>
    ${done ? `<div><b>${esc(it.결정)}</b> ${esc((it.조건 || []).join(','))} — ${esc(it.이유)} <span class="meta">(${esc(it.처리자)}, ${esc(it.처리한_때)})</span></div>` :
    `<div class="row"><select data-dec="${it.id}"><option>통과</option><option>반려</option></select><input data-rules="${it.id}" placeholder="반려면 조건(R1,R2…)"><input data-why="${it.id}" style="flex:1" placeholder="이유(필수, 평가셋 꼬리표로 남음)"><input data-who="${it.id}" placeholder="이름"><button class="primary" data-decide="${it.id}">결정</button></div>`}</div>`;
}
function renderReview() {
  $('#reviewQueue').innerHTML = D.검토.대기.length ? D.검토.대기.map((i) => reviewCard(i)).join('') : '<div class="empty">기다리는 검토가 없습니다</div>';
  $('#reviewDone').innerHTML = D.검토.처리.slice().reverse().map((i) => reviewCard(i, true)).join('');
}

function renderRegress() {
  const rows = D.회귀.map((r) => {
    const b = r.결과?.묶음별 || {}; const dev = b.dev || {};
    const sets = Object.entries(b).map(([k, v]) => `${k}: ${v.상태 === '완료' ? `${pct(v.판정_일치)} · κ ${v.카파}` : esc(v.상태)}${v['비싼_오류(반려를_통과시킴)']?.length ? ` · <b class="b-bad badge">비싼 오류 ${v['비싼_오류(반려를_통과시킴)'].join(',')}</b>` : ''}${v.이유 ? ` · ${esc(v.이유)}` : ''}`).join('<br>');
    return `<tr><td>${r.id}<div class="meta">${esc(r.때 || '')}</div></td><td>${esc((r.바뀐_것 || []).join(', ') || r.메모 || '기준점')}</td><td>${sets}</td><td class="num">${dev.앞_회차_대비 != null ? (dev.앞_회차_대비 > 0 ? '+' : '') + (dev.앞_회차_대비 * 100).toFixed(1) + '%p' : ''}</td><td>${badge(r.결과?.관문 || '진행')}${r.숨긴_묶음_포함 ? '<div class="meta">숨긴 묶음 포함</div>' : ''}</td></tr>`;
  }).reverse().join('');
  $('#regTable').innerHTML = `<table><tr><th>회차</th><th>바뀐 것</th><th>묶음별 결과</th><th>dev 변화</th><th>관문</th></tr>${rows}</table>`;
}

function renderFacts() {
  $('#factsList').innerHTML = Object.entries(D.사실표).map(([id, f]) => `<div class="item"><h3>${esc(f.이름)} ${badge(f.결론)}</h3>
    <div class="meta">사실표 ${esc(f.사실표_판)} · 게시 ${f.게시?.가능 === false ? '불가: ' + esc(f.게시.메모) : '가능'}</div>
    ${f.어긋남.length ? `<ul class="plain">${f.어긋남.map((i) => `<li><b>${esc(i.종류)}</b> ${esc(i.글자 || i.요소 || i.말 || '')} ${i.위치 ? `<span class="meta">${esc(i.위치)}</span>` : ''}</li>`).join('')}</ul>` : '<div class="note">어긋남 없음</div>'}</div>`).join('');
}

function renderPublish() {
  $('#audit').innerHTML = `감사 기록 ${D.감사.줄}줄 · ${D.감사.온전함 ? '앞뒤 해시가 이어져 온전함' : `<b class="badge b-bad">${D.감사.깨진_줄}번째 줄부터 깨짐</b>`}`;
  $('#pubList').innerHTML = D.게시.map((p) => `<div class="item"><video class="prev" controls preload="metadata" src="file://${encodeURI(ROOT + '/' + p.영상)}"></video><h3>${esc(p.광고)} → ${esc(p.채널)} ${badge(p.상태)}</h3>
    <div class="meta">소재 ${esc(p.소재)} · 심사 ${esc(p.심사_회차)} · 영상 ${esc(p.영상)} · 해시 ${esc((p.영상_해시 || '').slice(0, 12))}</div>
    <div class="checks">${Object.entries(p.점검).map(([k, v]) => `<span class="badge ${v ? 'b-ok' : 'b-bad'}">${v ? '✓' : '✕'} ${esc(k)}</span>`).join('')}</div>
    <pre>${esc(p.글.제목 ? p.글.제목 + '\n' : '')}${esc(p.글.글)}\n${esc((p.글.태그 || []).map((t) => '#' + t).join(' '))}\n${esc(p.글.링크)}</pre>
    ${p.상태 === '승인대기' ? `<div class="row"><label><input type="checkbox" data-seen="${p.id}"> 영상과 글을 직접 봤음</label><input data-approver="${p.id}" placeholder="승인하는 사람 이름"><button class="primary" data-approve="${p.id}">승인</button></div>` : ''}
    ${p.상태 === '승인' ? `<div class="row"><button class="primary" data-pubrun="${p.id}">게시 실행</button><span class="hint">채널 계정이 없으면 연습으로만 기록</span></div>` : ''}
    ${p.승인 ? `<div class="meta">승인: ${esc(p.승인.누가)} · ${esc(p.승인.때)}</div>` : ''}</div>`).join('') || '<div class="empty">게시 요청이 없습니다</div>';
}

function renderPlan() {
  const plans = D.최근_작업.filter((j) => j.단계 === '기획.명세');
  $('#planList').innerHTML = plans.map((j) => {
    const r = j.결과 || {}, s = r.명세 || {}, c = r.검사 || {};
    return `<div class="item"><h3>${j.id} ${badge(j.상태)} ${c.진행 ? '<span class="badge b-ok">넣을 수 있음</span>' : c.문제 ? '<span class="badge b-bad">막힘</span>' : ''}</h3>
      ${j.상태 === '완료' ? `<pre>${esc(JSON.stringify({ 게임: s.게임, 목표: s.목표, 채널: s.채널, 유형: s.유형, 총_개수: s.총_개수, 유료_집행: s.유료_집행, 예산: s.예산, 기간: s.기간 }, null, 1))}</pre>
      ${(c.문제 || []).length ? `<b>문제</b><ul class="plain">${c.문제.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
      ${(c.물어볼_것 || []).length ? `<b>꼭 정할 것</b><ul class="plain">${c.물어볼_것.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
      ${(c.확인하면_좋은_것 || []).length ? `<b>확인하면 좋은 것</b><ul class="plain">${c.확인하면_좋은_것.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
      ${(c.승인_필요 || []).length ? `<b>사람 승인</b><ul class="plain">${c.승인_필요.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
      ${c.진행 ? `<div class="row"><input data-planrun="${j.id}" placeholder="생성 회차 이름(예: R05)"><button class="primary" data-plango="${j.id}">대본 만들기·심사 넣기</button></div>` : ''}` : '<div class="note">AI 응답을 기다리는 중</div>'}</div>`;
  }).join('') || '<div class="empty">아직 기획 요청이 없습니다</div>';
}

async function renderPerf() {
  const reps = D.최근_작업.filter((j) => j.단계 === '성과.주간보고' || j.단계 === '성과.받기');
  const parts = [];
  for (const j of reps) {
    const md = j.상태 === '완료' ? await window.adf.read(`runs/jobs/${j.id}/report.md`) : null;
    parts.push(j.단계 === '성과.받기' ? `<div class="item"><h3>${j.id} 수집기에서 받기 ${badge(j.상태)}</h3><div class="meta">${j.오류 ? esc(j.오류) : '날짜별 줄 ' + esc(JSON.stringify(j.결과?.날짜별_줄 || {}))}</div></div>` : `<div class="item"><h3>${j.id} 주간 보고 ${badge(j.상태)}</h3><div class="meta">기록 ${esc(j.결과?.기록_수)}줄 · 광고 ${esc((j.결과?.광고 || []).join(', '))} · 피로 의심 ${esc((j.결과?.피로_의심 || []).join(', ') || '없음')}</div>${md ? `<pre>${esc(md)}</pre>` : ''}</div>`);
  }
  $('#perfList').innerHTML = parts.join('') || '<div class="empty">보고가 없습니다</div>';
}

// ── 이벤트 ──
document.addEventListener('click', async (e) => {
  const t = e.target.closest('button,[data-go]'); if (!t) return;
  if (t.dataset.tab || t.dataset.go) return go(t.dataset.tab || t.dataset.go);
  if (t.id === 'refresh') return load();
  if (t.id === 'runQueue') { await call(['run']); return load(); }
  if (t.id === 'cloudPush') { const r = await call(['sync', 'push'], true); if (r) toast(r.올림 ? `올림 ${r.커밋} · 기다리는 요청 ${r.기다리는_요청}건 → Code 탭에서 「대기 중인 거 처리해」` : '올릴 것이 없습니다'); return load(); }
  if (t.id === 'cloudPull') { const r = await call(['sync', 'pull'], true); if (r) toast(r.전 === r.후 ? '아직 새 답이 없습니다' : `받음 ${r.전}→${r.후} · 이어서 ${r.대기열}개 작업을 돌렸습니다`); return load(); }
  if (t.id === 'planSend') { const text = $('#planText').value.trim(); if (!text) return toast('요청을 적어 주세요', true); await call(['add', '기획.명세', `text=${JSON.stringify(text)}`]); await call(['run'], true); $('#planText').value = ''; return load(); }
  if (t.dataset.plango) { const run = document.querySelector(`[data-planrun="${t.dataset.plango}"]`).value.trim(); if (!/^R\d+$/.test(run)) return toast('회차 이름은 R과 숫자(예: R05)', true); await call(['plan', `job=${t.dataset.plango}`, `run=${run}`]); return load(); }
  if (t.id === 'pipeAdd') { await call(['pipeline', $('#pipeSel').value, ...$('#pipeArgs').value.trim().split(/\s+/).filter(Boolean)]); return load(); }
  if (t.dataset.respond) { const f = await window.adf.pick(); if (!f) return; await call(['respond', t.dataset.respond, t.dataset.key, f]); await call(['run'], true); return load(); }
  if (t.dataset.retry) { await call(['retry', t.dataset.retry]); await call(['run'], true); return load(); }
  if (t.dataset.decide) {
    const id = t.dataset.decide, q = (k) => document.querySelector(`[data-${k}="${id}"]`).value.trim();
    const args = ['review', 'decide', id, `decision=${q('dec')}`, `reason=${JSON.stringify(q('why'))}`, `who=${JSON.stringify(q('who') || '이름 없음')}`];
    if (q('rules')) args.push(`rules=${q('rules')}`);
    if (await call(args)) load(); return;
  }
  if (t.dataset.approve) {
    const id = t.dataset.approve; if (!document.querySelector(`[data-seen="${id}"]`).checked) return toast('영상과 글을 직접 본 뒤 체크하세요', true);
    const who = document.querySelector(`[data-approver="${id}"]`).value.trim(); if (!who) return toast('승인하는 사람 이름을 적어 주세요', true);
    if (await call(['publish', 'approve', `id=${id}`, `who=${JSON.stringify(who)}`])) load(); return;
  }
  if (t.dataset.pubrun) { if (await call(['publish', 'run', `id=${t.dataset.pubrun}`])) load(); return; }
  if (t.id === 'regCheck') { const r = await call(['regress', 'check']); if (r && !r.바뀐_것.length) toast('바뀐 것이 없어 다시 돌리지 않았습니다'); await call(['run'], true); return load(); }
  if (t.id === 'regRelease') { await call(['regress', 'check', 'release=true']); await call(['run'], true); return load(); }
  if (t.id === 'perfPull') { await call(['pipeline', '주간성과', 'out=runs/events', 'days=7', 'events_dir=runs/events', `note=${JSON.stringify('수집기 실제 기록(시험 기록 src=test 제외)')}`]); await call(['run'], true); return load(); }
  if (t.id === 'perfAdd') { const a = ['add', '성과.주간보고', `events_dir=${$('#perfDir').value.trim()}`, `note=${JSON.stringify($('#perfNote').value.trim())}`]; if ($('#perfCsv').value.trim()) a.push(`platform_csv=${$('#perfCsv').value.trim()}`); await call(a); await call(['run'], true); return load(); }
});
function go(tab) {
  document.querySelectorAll('#nav button').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
  document.querySelectorAll('.panel').forEach((p) => p.classList.toggle('on', p.dataset.panel === tab));
  $('#title').textContent = TITLES[tab];
}
(async () => {
  const info = await window.adf.info(); ROOT = info.root; $('#info').textContent = `엔진 ${info.root}`;
  const ps = await call(['pipelines'], true); if (ps) $('#pipeSel').innerHTML = Object.entries(ps).map(([k, v]) => `<option value="${esc(k)}" title="${esc(v)}">${esc(k)}</option>`).join('');
  load();
  setInterval(() => { if (!document.hidden) load(); }, 15000);
})();
