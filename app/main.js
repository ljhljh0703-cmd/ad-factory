// 광고 공장 앱: 화면만 맡는다. 모든 일은 엔진 명령(python3 -m adf … --json)으로 넘긴다.
// 엔진이 쓰는 파일(runs/…)이 곧 기록이라, 앱을 꺼도 작업·검토·승인 기록은 그대로 남는다.
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { execFile } = require('child_process');
const path = require('path'); const fs = require('fs');

const ROOT = process.env.ADF_ROOT || path.resolve(__dirname, '..');
const ENGINE = path.join(ROOT, 'engine');
const PY = process.env.ADF_PYTHON || 'python3';
// 화면에서 부를 수 있는 엔진 명령만 연다
const ALLOWED = new Set(['dashboard', 'plan', 'sync', 'run', 'pipeline', 'pipelines', 'add', 'stages', 'review', 'publish', 'regress', 'respond', 'retry', 'show']);

function adf(args) {
  return new Promise((resolve) => {
    if (!Array.isArray(args) || !ALLOWED.has(args[0])) return resolve({ ok: false, error: '허용하지 않은 명령' });
    execFile(PY, ['-m', 'adf', ...args.map(String), '--json'], { cwd: ENGINE, env: { ...process.env, ADF_ROOT: ROOT }, maxBuffer: 64 << 20, timeout: 30 * 60 * 1000 },
      (err, stdout, stderr) => {
        if (err) return resolve({ ok: false, error: (stderr || err.message).trim().split('\n').slice(-1)[0] });
        try { resolve({ ok: true, data: JSON.parse(stdout) }); } catch { resolve({ ok: false, error: '엔진 응답을 읽지 못함' }); }
      });
  });
}

ipcMain.handle('adf', (_e, args) => adf(args));
ipcMain.handle('read', (_e, rel) => {
  const p = path.resolve(ROOT, rel);
  if (!p.startsWith(path.join(ROOT, 'runs') + path.sep) && !p.startsWith(path.join(ROOT, 'judge', 'runs') + path.sep)) return null;
  return fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : null;
});
ipcMain.handle('pick', async () => {
  const r = await dialog.showOpenDialog({ properties: ['openFile'], filters: [{ name: '응답', extensions: ['txt', 'jsonl', 'json', 'md'] }] });
  return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle('info', () => ({ root: ROOT, python: PY, version: app.getVersion() }));

function createWindow() {
  const win = new BrowserWindow({
    width: 1280, height: 860, minWidth: 980, minHeight: 640, title: '광고 공장', backgroundColor: '#f4f6f8',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  return win;
}
app.whenReady().then(() => { createWindow(); app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); }); });
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
module.exports = { adf };
