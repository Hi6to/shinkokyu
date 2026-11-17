// シン呼吸 デスクトップ：作業中の画面の一番手前に、透明な窓で煙を出す（Electron）
// - 煙の窓：画面全体をおおう透明な窓。マウスの操作は下の画面に素通りする（メッセージの窓の上だけ押せる）
// - 通知領域（時計の横）のアイコン：煙のたまり具合で絵が変わる。押すと操作パネル（閉じない小窓）が出る
// - 煙がいっぱいになったら、Windows の通知で1回だけ知らせる（ページの側で出す）
// - 席を外して一服した人が戻ってきたら、晴れていく様子を早送りで見せる
// 中身の画面は web/retro.html を「?overlay=1」で開いたもの（ブラウザ版と同じものを使い回す）
const { app, BrowserWindow, Tray, Menu, nativeImage, screen, ipcMain, powerMonitor, shell, globalShortcut, Notification } = require('electron');
const { Rhythm } = require('./rhythm');
const { makeReason } = require('./reason');
const { Fire, CAMP, STRONG_PA } = require('./fire');
const { Stt } = require('./voice/stt');
const { Labeler } = require('./voice/label');
const http = require('http');
const fs = require('fs');
const path = require('path');

app.setAppUserModelId('jp.shinkokyu.desktop'); // Windows の通知に名前を出すため
const gotLock = app.requestSingleInstanceLock(); // アプリは1つだけ。2つ目は、引数を渡して終わる
if (!gotLock) app.quit();
const ROOT = path.join(__dirname, '..'); // リポジトリのいちばん上（web/ と songs/ を配る）

// web/ と songs/ を、PC の中だけで配る小さなサーバー（Web Bluetooth は localhost なら使える）
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.css': 'text/css; charset=utf-8' };
function startServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
      const file = path.normalize(path.join(ROOT, p));
      const allowed = [path.join(ROOT, 'web'), path.join(ROOT, 'songs')].some((d) => file.startsWith(d + path.sep));
      if (!allowed) { res.writeHead(404); res.end(); return; }
      fs.readFile(file, (err, data) => {
        if (err) { res.writeHead(404); res.end(); return; }
        res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
        res.end(data);
      });
    });
    server.listen(0, '127.0.0.1', () => resolve(server.address().port));
  });
}

let overlay = null, panel = null, tray = null;
// 覚えておく設定（アプリのデータの場所の settings.json）：右下の煙メーター・煙の上の言葉の見せ方
let settings = { gauge: true, labels: 'present', view: 'game' };
// 見せ方（11/08）：'game'＝右下の火の子と右の吹き出し（画面全体には煙を出さない）、'smoke'＝前の見せ方（画面全体の煙）
const gameMode = () => settings.view !== 'smoke';
const settingsFile = () => path.join(app.getPath('userData'), 'settings.json');
function loadSettings() {
  try { settings = { ...settings, ...JSON.parse(fs.readFileSync(settingsFile(), 'utf8')) }; } catch {}
  if (!Array.isArray(settings.knownDevices)) settings.knownDevices = ['Shinkokyu-CE40', 'Shinkokyu-5F98']; // 11/13：自動でつなぐ本体（最初はチームの2台。つないだ本体は足していく）
  if (!settings.pcSound) settings.pcSound = { on: true, vol: 7 }; // 11/15：PC からの音は、はじめから出す（発表で2人同時に吸っても PC から鳴るように）
  settings.view = 'game'; // 11/11：画面全体の煙はもう使わない。いつも右下の火の子にする（切り替えの道も消した）
}
function saveSettings() { try { fs.writeFileSync(settingsFile(), JSON.stringify(settings)); } catch (e) { log('settings_save_fail', { msg: String(e.message).slice(0, 120) }); } } // 11/15：保存できないときは記録に残す（前は黙っていた）

// ---------------- 右下の煙メーター（窓の枠もタスクバーのボタンもない、小さな浮いた絵。押すと操作パネル） ----------------
let gauge = null, lastIcon = null;
ipcMain.on('gauge-icon', (_e, dataUrl) => { lastIcon = dataUrl; sendGauge(); }); // 煙の画面が描く、メーター用の雲の絵
// 大きさ：ふつう（180×76）を元に、小・大・特大を選べる。中身はメーターのページの中で拡大・縮小する（CSS の zoom）
// 大きさ（右下の火の子と、右の吹き出し＝通知で同じ段）。11/11：発表で後ろの席からも見えるように「発表用」を2つ足した
const GAUGE_SIZES = [{ key: 'small', label: '小', scale: 0.75 }, { key: 'normal', label: 'ふつう', scale: 1 }, { key: 'large', label: '大', scale: 1.35 }, { key: 'xlarge', label: '特大', scale: 1.75 },
  { key: 'present', label: '発表用', scale: 2.25 }, { key: 'present2', label: '発表用・最大', scale: 3 }];
const sizeOf = (key) => GAUGE_SIZES.find((g) => g.key === key) || GAUGE_SIZES[1];
const gaugeScale = () => sizeOf(settings.gaugeSize).scale;
const noticeScale = () => sizeOf(settings.noticeSize).scale;
// ゲームの見せ方では、火の子が育つ大きさが分かるように、少し大きくする（210×104）
const gW = () => Math.round((gameMode() ? 210 : 180) * gaugeScale()), gH = () => Math.round((gameMode() ? 104 : 76) * gaugeScale());
function gaugeHome() { const { workArea } = screen.getPrimaryDisplay(); return { x: workArea.x + workArea.width - gW() - 10, y: workArea.y + workArea.height - gH() - 10 }; } // 右下
// 覚えておいた場所が、どこかの画面の中にあればそこ。なければ右下
function gaugeStartPos() {
  const p = settings.gaugePos;
  if (p && screen.getAllDisplays().some(({ workArea: a }) => p.x >= a.x && p.y >= a.y && p.x + gW() <= a.x + a.width && p.y + gH() <= a.y + a.height)) return p;
  return gaugeHome();
}
function createGauge() {
  const pos = gaugeStartPos();
  gauge = new BrowserWindow({
    x: pos.x, y: pos.y, width: gW(), height: gH(),
    transparent: true, frame: false, resizable: false, movable: true, skipTaskbar: true, focusable: false,
    alwaysOnTop: true, hasShadow: false, show: false, backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'gauge-preload.js'), backgroundThrottling: false }, // 火の子が動くように、見えていない扱いでも時計を間引かない
  });
  gauge.setAlwaysOnTop(true, 'screen-saver');
  gauge.loadFile(path.join(__dirname, 'gauge.html'));
  gauge.once('ready-to-show', () => { placeGauge(pos.x, pos.y); if (settings.gauge) { gauge.showInactive(); gauge.moveTop(); } sendGauge(); });
}
function gaugeOnTop() { if (gauge && gaugeShown() && gauge.isVisible()) gauge.moveTop(); } // 煙の窓より手前に
// 11/11：煙メーターを消していても、吹いている間（一服の間）は火の子を出す。一服が終わって少したったら（残り火が火に入るのを見せてから）また隠す
// 11/12 夜：× で消したら、その一服の間はもう出さない（前は、消しても1秒に何回も届く「一服中」で、すぐまた出てきた）。次の一服からは、また出す
let gaugeTemp = false, gaugeTempTimer = 0, gaugeDismissed = false;
// 11/13：声を録っている間・言葉にしている間（voiceBusyAt＝始めた時刻。0＝していない）は、火の子を隠さない。
//   前は、録っている途中で一服が終わる（90秒吹かないと一服を終える）と、その12秒後に火の子が消えていた。
//   録り終わり（言葉にし終わり・取りやめ）で、改めて隠す時間を数える。万一終わりが届かなくても、2分たったら隠してよい
let voiceBusyAt = 0;
const voiceBusy = () => voiceBusyAt > 0 && Date.now() - voiceBusyAt < 120000;
const gaugeShown = () => settings.gauge || gaugeTemp;
function gaugeTempShow() {
  clearTimeout(gaugeTempTimer);
  if (settings.gauge || gaugeTemp || gaugeDismissed || !gauge) return;
  gaugeTemp = true; gauge.showInactive(); gauge.moveTop(); sendGauge();
}
// 11/13 午前：一服が終わっても、録り終わっても、火の子を自動では隠さない（利用者の希望）。消すのは × だけ。
//   × で消しても、次に吸い始めたらまた出る（下の 'log' の exhale_start）。前の「少したったら隠す」に戻すときは、AUTO_HIDE を true に
const AUTO_HIDE = false;
function gaugeTempHide(ms) {
  if (!AUTO_HIDE) return;
  if (!gaugeTemp) return;
  clearTimeout(gaugeTempTimer);
  gaugeTempTimer = setTimeout(() => { if (voiceBusy()) return; gaugeTemp = false; if (gauge && !settings.gauge) gauge.hide(); }, ms);
}
function setGauge(on) {
  settings.gauge = !!on; saveSettings();
  gaugeDismissed = !on;
  gaugeTemp = false; clearTimeout(gaugeTempTimer);
  if (gauge) { if (on) { gauge.showInactive(); gauge.moveTop(); sendGauge(); } else gauge.hide(); }
  log('gauge', { on: !!on });
  sendPanelState();
}
function sendGauge() { if (gauge && gaugeShown()) gauge.webContents.send('state', { embers: fire && fire.sess ? fire.sess.embers || 0 : 0, progress: state.progress || 0, fill: state.fill, inSession: state.inSession, icon: lastIcon, visible: shownNow(), scale: gaugeScale(), game: gameMode(), fire: fire && (fireFrozen && gameMode() ? fireFrozen.view : fire.view()), pair: demoView ? demoView.pair : connectedCount() >= 2, wood: demoView ? demoView.wood : (state.moya || []).length, woodLabels: state.labelsShown === false ? null : demoView ? demoView.labels || [] : state.moya || [], strongPa: STRONG_PA }); } // 札の言葉は、煙の上の言葉と同じ決まり（席にいないときは出さない）
const connectedCount = () => (state.devices || []).filter((d) => d.connected).length;
// つかんで動かす：マウスの位置は、アプリの側で画面全体の位置を直接読む（1秒に60回）。つかんだ所からのずれを保ってついてくる
// - 窓の中で測ると、窓が動くたびに測り方がずれてガタガタするため
// - 位置と一緒に大きさも毎回決まった値で指定する（画面の拡大率が150%などのとき、位置だけ変えると端数で大きさが少しずつ広がるため）
let gaugeDrag = null;
function placeGauge(x, y) { if (gauge) gauge.setBounds({ x: Math.round(x), y: Math.round(y), width: gW(), height: gH() }); }
// 大きさを変える：右下の角を動かさずに、左上へ広がる（縮む）。画面からはみ出すときは中に収める
function setGaugeSize(key) {
  if (!GAUGE_SIZES.some((g) => g.key === key) || !gauge) return;
  const b = gauge.getBounds();
  settings.gaugeSize = key;
  const a = screen.getDisplayMatching(b).workArea;
  const x = Math.min(Math.max(a.x, b.x + b.width - gW()), a.x + a.width - gW());
  const y = Math.min(Math.max(a.y, b.y + b.height - gH()), a.y + a.height - gH());
  placeGauge(x, y);
  sendGauge();
  if (settings.gaugePos) settings.gaugePos = { x, y };
  saveSettings(); log('gauge_size', { size: key }); sendPanelState();
}
function endGaugeDrag() {
  if (!gaugeDrag) return;
  clearInterval(gaugeDrag.timer); gaugeDrag = null;
  if (!gauge) return;
  const b = gauge.getBounds();
  placeGauge(b.x, b.y);
  settings.gaugePos = { x: b.x, y: b.y }; saveSettings();
}
ipcMain.on('gauge-drag', (_e, cmd) => {
  if (!gauge) return;
  if (cmd === 'start') {
    stopGaugeShake();
    if (gaugeDrag) clearInterval(gaugeDrag.timer);
    const c = screen.getCursorScreenPoint(), b = gauge.getBounds();
    gaugeDrag = { ox: c.x - b.x, oy: c.y - b.y, until: Date.now() + 60000 };
    gaugeDrag.timer = setInterval(() => {
      if (!gaugeDrag || Date.now() > gaugeDrag.until) { endGaugeDrag(); return; } // 離したのが届かなかったときの備え（1分）
      const p = screen.getCursorScreenPoint();
      placeGauge(p.x - gaugeDrag.ox, p.y - gaugeDrag.oy);
    }, 16);
  } else if (cmd === 'end') endGaugeDrag();
});
// 11/11：残り火を吸いこむ演出で、窓ごとゆらす。rumble＝吸いこむ間の小さなふるえ（だんだん強く）、boom＝ためきって「どん」の大きなゆれ（だんだん弱く）
// ゆらしている間に、つかんで動かし始めたら、元の場所に戻してやめる（ずれた場所を覚えないように）
let gaugeShake = null;
function stopGaugeShake() { if (!gaugeShake) return; clearInterval(gaugeShake.timer); const b = gaugeShake.base; gaugeShake = null; placeGauge(b.x, b.y); }
// 11/12：もやもやの薪が燃えきったとき、火の粉が右下の火から画面のいちばん上までのぼる（透明で押せない窓。言葉は出さない。火の粉だけ）
let rise = null, riseTimer = 0;
function createRise() {
  rise = new BrowserWindow({
    transparent: true, frame: false, resizable: false, movable: false, skipTaskbar: true, focusable: false,
    alwaysOnTop: true, hasShadow: false, show: false, backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'rise-preload.js'), backgroundThrottling: false },
  });
  rise.setAlwaysOnTop(true, 'screen-saver');
  rise.setIgnoreMouseEvents(true); // クリックは下の画面に素通り
  rise.loadFile(path.join(__dirname, 'rise.html'));
}
ipcMain.on('gauge-rise', (_e, d) => {
  if (!rise || !gauge || !gauge.isVisible() || !d) return;
  const b = gauge.getBounds(), a = screen.getDisplayMatching(b).workArea;
  if (d.prep) { // 火の子の窓の上から、画面のいちばん上まで（左右は少し広め）
    const pad = Math.round(70 * gaugeScale()), x = Math.max(a.x, b.x - pad), w = Math.min(a.x + a.width, b.x + b.width + pad) - x;
    const h = b.y + Math.round(b.height * 0.3) - a.y;
    if (h < 60 || w < 60) return;
    rise.setBounds({ x, y: a.y, width: w, height: h });
    rise.showInactive(); rise.moveTop(); gauge.moveTop(); // 火の粉は、火の子の箱のうしろから出てくる
    rise.webContents.send('rise', { prep: true, ox: b.x - x, oy: b.y - a.y, gw: b.width, scale: gaugeScale() });
  } else if (Array.isArray(d.ps)) rise.webContents.send('rise', { ps: d.ps.slice(0, 200) });
  clearTimeout(riseTimer); riseTimer = setTimeout(() => { if (rise) rise.hide(); }, 4500); // 最後の火の粉が上に着いたら、窓をかくす
});
ipcMain.on('gauge-shake', (_e, kind) => {
  if (!gauge || !gauge.isVisible() || gaugeDrag) return;
  const base = gaugeShake ? gaugeShake.base : gauge.getBounds();
  if (gaugeShake) clearInterval(gaugeShake.timer);
  const boom = kind === 'boom', pop = kind === 'pop', ms = boom ? 1300 : pop ? 700 : 1000, t0 = Date.now(), s = gaugeScale();
  let i = 0;
  gaugeShake = { base };
  gaugeShake.timer = setInterval(() => {
    const k = (Date.now() - t0) / ms;
    if (k >= 1 || !gauge) { stopGaugeShake(); return; }
    const amp = (boom ? 22 * Math.pow(1 - k, 1.6) + 1 : pop ? 10 * Math.pow(1 - k, 1.4) + 1 : 1 + 4 * k) * s; // どん：22px → 0／ぼっ（薪）：10px → 0／ふるえ：1px → 5px
    i++;
    const dx = (i % 2 ? 1 : -1) * amp * (0.6 + 0.4 * Math.random()), dy = (Math.random() - 0.5) * amp * (boom || pop ? 1.2 : 0.6);
    placeGauge(base.x + dx, base.y + dy);
  }, 33);
});
function gaugeToHome() { const p = gaugeHome(); settings.gaugePos = null; saveSettings(); placeGauge(p.x, p.y); }
ipcMain.on('gauge', (_e, cmd) => { if (cmd === 'panel') togglePanel(); else if (cmd === 'hide') setGauge(false); else if (cmd === 'smoke') (shownNow() ? hideSmoke() : setVisible(true)); });
// 11/13 昼：火の子の窓・吹き出しの × を押しても消えないことがあった。窓の上でマウスを動かすのはページに届く（× は出る）のに、「押した」だけが届かない。
//   ページに頼らず、アプリの側でも PC 全体のマウスの「押した」を見て、火の子の窓の右上（× の所）なら消す。
//   PC 全体のマウスは、作業のリズムの記録（rhythm.js）が使っている uiohook と同じもの（それが動いていないときは、この備えもない）
try {
  const { uIOhook } = require('uiohook-napi');
  uIOhook.on('mousedown', (e) => {
    if (e.button !== 1) return; // 1＝左ボタン
    const c = screen.getCursorScreenPoint();
    // 吹き出し（お知らせ）の右上の × の所：その吹き出しを消すよう、窓に位置を知らせる
    if (notice && notice.isVisible() && noticeRects.length) {
      const nb = notice.getBounds(), x = c.x - nb.x, y = c.y - nb.y, ns = noticeScale();
      const r = noticeRects.find((q) => x >= q.x + q.w - 44 * ns && x <= q.x + q.w + 4 && y >= q.y - 4 && y <= q.y + 34 * ns);
      if (r) { notice.webContents.send('close-at', { x, y }); return; }
    }
    // 11/14：心拍数の窓も、押した所を窓が受けとれないことがある（押してもフォーカスを奪わない窓のため）。アプリの側で、窓の上で押したら動かし始め、離したら止める
    if (hr && hr.isVisible()) {
      const hb = hr.getBounds();
      if (c.x >= hb.x && c.x < hb.x + hb.width && c.y >= hb.y && c.y < hb.y + hb.height) {
        // 11/15：− ・＋ のボタンの上なら大きさを変える（動かし始めない）
        const x = c.x - hb.x, y = c.y - hb.y, btn = hrBtns.find((q) => x >= q.x - 3 && x <= q.x + q.w + 3 && y >= q.y - 3 && y <= q.y + q.h + 3);
        if (btn) { hrCall(`hrFlashBtn(${btn.step > 0 ? 1 : -1})`); hrStep(btn.step, 'hook'); return; }
        startHrDrag(); return;
      }
    }
    if (!gauge || !gauge.isVisible()) return;
    const b = gauge.getBounds(), s = gaugeScale();
    if (c.x >= b.x + b.width - 36 * s && c.x <= b.x + b.width && c.y >= b.y && c.y <= b.y + 30 * s) setGauge(false);
  });
  uIOhook.on('mouseup', (e) => { if (e.button === 1 && hrDrag) endHrDrag(); }); // 11/14：心拍数の窓を離した
} catch (err) { console.log('[shinkokyu] × の備えを始められなかった：' + err.message); }
let visible = true, keysMode = false; // visible：煙を表示するかの設定（演出のときだけ一時的に出すことがある）
let tempShown = false;
let state = {}; // ページから届く今の様子
// 記録（作業のリズム・通知・一服・席を離れた時間）。PC の中の %APPDATA%\shinkokyu-desktop\logs に、日付ごとのファイルで残す
let rhythm = null;
const logDir = () => path.join(app.getPath('userData'), 'logs');
const log = (type, data) => { if (rhythm) rhythm.event(type, data); };

// ---------------- 声を煙のラベルにする（V03）：話す → Whisper で文字 → AI で短い言葉 → 煙のラベル ----------------
// - 録るのは操作パネル（PC のマイク）。押している間 話すボタンか、Ctrl+Alt+M（押すと始まり、もう一度で終わり）
// - 録った声と文字は、使い終わったらすぐ消す。記録には長さと時間だけ残す（話した中身は残さない）
const VOICE_KEY = 'CommandOrControl+Alt+M', VOICE_KEY_LABEL = 'Ctrl+Alt+M';
let stt = null, labeler = null, voiceClear = null;
function voiceStatus(lines, ms = 0) { // 煙の画面の下に、小さな窓で知らせる
  clearTimeout(voiceClear);
  if (lines) showTemp();
  call(`voiceStatus(${JSON.stringify(lines)})`);
  if (lines && ms) voiceClear = setTimeout(() => voiceStatus(null), ms);
}
// 11/12：右下の火の子にも知らせる（話している間は耳をすます・言葉にしている間は「…」・声の大きさで炎がゆれる）
function gaugeLive(type, data) { if (gauge && !trialWin) gauge.webContents.send('live', type, data); }
ipcMain.on('voice-level', (_e, v) => gaugeLive('voice', { v: +v || 0 }));
ipcMain.on('voice-start', (_e, via) => {
  if (!stt) return;
  voiceBusyAt = Date.now();
  gaugeLive('listen', { on: true }); if (gameMode()) gaugeTempShow(); // 火の子を消していても、話している間と薪にするところは見せる
  voiceStatus(['聞いています', via === 'key' ? `もう一度 ${VOICE_KEY_LABEL} で おわり` : via === 'device' ? 'もう一度 本体の ＋−同時押しで おわり' : 'ボタンを はなすと おわり']);
  stt.start().catch(() => {});     // Whisper を先に読みこむ
  labeler.warm().catch(() => {});  // 短い言葉にする AI も先に読みこむ
  log('voice_start', { via });
});
// 11/15：起動したら、声を文字にする係（Whisper）→ 短い言葉にする AI の順に、1つずつ読みこんで慣らしておく（同時だと取りあって遅い）。
//   AI は 3時間読みこんだままにし、10分ごとに声をかけて下ろされないようにする
let voiceWarm = null;
async function warmVoice() {
  if (!stt || !stt.available() || voiceWarm) return;
  voiceWarm = (async () => {
    const r = {};
    try { const s = await stt.warm(app.getPath('temp')); r.sttMs = s.ms; r.threads = s.threads; } catch (e) { r.sttErr = String(e.message).slice(0, 80); }
    try { const t0 = Date.now(); const l = await labeler.label('今日は会議が長くて疲れた'); r.llmMs = Date.now() - t0; r.by = l.by; } catch (e) { r.llmErr = String(e.message).slice(0, 80); }
    log('voice_warm', r);
  })();
  setInterval(() => { if (!voiceBusy()) labeler.warm().catch(() => {}); }, 10 * 60 * 1000);
}
// 11/15：おわりを押したら、すぐ画面に出す（前は、声の基板から「おわり」が届くまで「聞いています」のままで、押したのが効いていないように見えた）
ipcMain.on('voice-stopping', () => { voiceStatus(['声を 受けとっています…']); gaugeLive('listen', { on: false }); gaugeLive('think', { on: true }); });
ipcMain.on('voice-cancel', (_e, why) => { voiceBusyAt = 0; gaugeLive('think', { on: false }); if (why === 'noend') voiceStatus(['声が 届きませんでした', 'もう一度 話してね'], 3000); else voiceStatus(null); gaugeLive('listen', { on: false }); gaugeTempHide(3000); }); // 11/13：取りやめのときも、一時的に出した火の子をあとで隠す（前は出たままだった）
ipcMain.handle('voice-wav', async (...a) => { // 言葉にしている間は、火の子が「…」と考える
  gaugeLive('listen', { on: false }); gaugeLive('think', { on: true });
  try { return await voiceWav(...a); } finally { voiceBusyAt = 0; gaugeLive('think', { on: false }); gaugeTempHide(8000); } // 薪に刻むところ（約3秒）を見せてから、また隠す
});
async function voiceWav(_e, buf, meta = {}) {
  if (!stt || !stt.available()) { voiceStatus(['声を 文字にする部品が', 'この PC に 入っていません'], 4000); return { error: 'Whisper 用の Python が見つからない（desktop/README.md）' }; }
  voiceStatus(['ことばに しています…']);
  const tmp = path.join(app.getPath('temp'), `shinkokyu-voice-${Date.now()}.wav`);
  try {
    fs.writeFileSync(tmp, Buffer.from(buf));
    const sc = stt.config();
    const t = await stt.transcribe(tmp);
    // 比べるモード（voice.json の "compare": ["small", "base+dn", "small+dn+nh"] など。dn＝雑音を消す、nh＝言葉のヒントなし）：
    // ほかのやり方でも文字にして、パネルに並べて見せる（煙にはしない。声のファイルは残さない）
    const others = [];
    for (const v of [].concat(sc.compare || [])) {
      const [model, ...flags] = String(v).split('+');
      try { const o = await stt.transcribe(tmp, { model, denoise: flags.includes('dn'), hotwords: !flags.includes('nh') }); others.push({ name: v, text: o.text, sec: o.sec, logprob: o.logprob, labels: o.text ? (await labeler.label(o.text)).labels : [] }); } catch (e) { others.push({ name: v, text: 'うまくいかなかった：' + e.message, labels: [] }); }
    }
    const pname = `${sc.model}${sc.denoise ? '+dn' : ''}${sc.hotwords ? '' : '+nh'}`;
    if (!t.text) { voiceStatus(['うまく 聞きとれませんでした'], 3000); log('voice_label', { sec: meta.sec, via: meta.via, sttSec: t.sec, empty: true }); return { error: '聞きとれなかった', others, model: pname }; }
    const l = await labeler.label(t.text);
    if (!l.labels.length) { voiceStatus(['うまく ことばに できませんでした'], 3000); return { error: '言葉にできなかった', text: t.text, others, model: pname }; }
    voiceStatus(null);
    if (!gameMode()) setVisible(true);
    for (const label of l.labels) call(`addMoya(${JSON.stringify(label)})`); // 愚痴がいくつかあれば、雲もいくつか（3つまで）
    if (fire) fire.wood(l.labels.length);
    const said = settings.labels === 'never' ? '' : l.labels.map((x) => `「${x}」`).slice(0, 2).join(''); // 煙の上の言葉と同じ決まり（出さない設定なら出さない）
    toast([said ? `${said}を` : 'もやもやを', '〔薪〕に した。吸うと 燃えるよ'], { kind: 'wood' }); // 11/15：すぐ出す（前は、PC に30秒さわっていないと「席にいない」とみなして、マウスを動かすまで待たせていた。本体に向かって話している人は席にいる）
    log('voice_label', { sec: meta.sec, via: meta.via, lost: meta.lost, dropped: meta.dropped, model: pname, sttSec: t.sec, logprob: t.logprob, llmMs: l.ms, by: l.by, textLen: [...t.text].length, labels: l.labels.length, compare: others.length ? others.map((o) => o.name).join(',') : undefined, error: l.error });
    return { labels: l.labels, label: l.label, text: t.text, by: l.by, model: pname, logprob: t.logprob, others };
  } catch (err) {
    voiceStatus(['うまく いきませんでした'], 3000);
    log('voice_error', { msg: err.message });
    return { error: err.message };
  } finally { fs.unlink(tmp, () => {}); }
}

// ---------------- 煙の窓 ----------------
function createOverlay(port) {
  const { workArea } = screen.getPrimaryDisplay(); // タスクバーはおおわない
  overlay = new BrowserWindow({
    x: workArea.x, y: workArea.y, width: workArea.width, height: workArea.height,
    transparent: true, frame: false, resizable: false, movable: false, hasShadow: false,
    skipTaskbar: true, focusable: false, alwaysOnTop: true, show: false,
    backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), backgroundThrottling: false, autoplayPolicy: 'no-user-gesture-required' }, // 11/13：PC から音を出す
  });
  overlay.setAlwaysOnTop(true, 'screen-saver');
  overlay.setIgnoreMouseEvents(true, { forward: true }); // クリックは下の画面へ。マウスの位置だけはページに届ける
  overlay.loadURL(`http://127.0.0.1:${port}/web/retro.html?overlay=1`);
  overlay.once('ready-to-show', () => overlay.showInactive());
  overlay.webContents.on('did-finish-load', () => { callReady(`setGame(${gameMode()})`); applyPcSound(true); }); // ゲームの見せ方では、煙を描かない（窓は出したまま：一曲の進みなどがこのページで動いているため）

  // メッセージの窓が押されたら、アプリの側でも閉じる（ページに押したことが届かない場合の予備）
  overlay.webContents.on('before-mouse-event', (_e, m) => {
    if (capturing && m && (m.type === 'mouseDown' || m.type === 'mouseUp')) {
      console.log('[shinkokyu] 窓が押された（アプリの側で受けとった）');
      call('dismiss()');
    }
  });
  overlay.webContents.on('console-message', (_e, _level, message) => { if (String(message).startsWith('[shinkokyu]')) console.log(message); });

  // 本体を選ぶ画面は出さず、名前が「Shinkokyu」で始まる本体を自動で選ぶ（10秒見つからなければあきらめる）
  // 11/12：見つかった本体を操作パネルに一覧で出して、人が選ぶ（前は最初に見つかった1台を自動でつないでいた）
  overlay.webContents.on('select-bluetooth-device', (event, devices, callback) => {
    event.preventDefault();
    // 本体だけ（声の基板「ShinkokyuMic-」は操作パネルがつなぐ）。もうつながっている本体は選ばない（11/07：2台目をつなごうとして、同じ本体が二重につながった）
    //   11/13：切れてつなぎ直している最中の本体も選ばない（つなぎ直しと、選んだのとが重なって、同じ本体が2つ分つながった。もう1台はつながらなかった）
    const busy = new Set((state.devices || []).map((d) => d.name));
    // 11/13：自動でつなぐ（autoPick）：一度つないだことのある本体（settings.knownDevices）が見つかったら、選ばずにつなぐ。知らない本体にはつながない
    if (autoPick && !btPick) {
      autoPick.callback = callback;
      const known = new Set(settings.knownDevices || []);
      const hit = devices.find((d) => known.has(d.deviceName) && !busy.has(d.deviceName) && !autoSkip.has(d.deviceName));
      if (hit) { log('device_auto', { name: hit.deviceName }); autoPickDone(hit.deviceId); }
      return;
    }
    if (!btPick) { btPick = { list: new Map(), timer: setTimeout(() => btPickDone(''), 30000) }; if (panel && !panel.isVisible()) togglePanel(); }
    btPick.callback = callback;
    const n0 = btPick.list.size, first = !btPick.sent;
    for (const d of devices) if ((d.deviceName || '').startsWith('Shinkokyu-') && !busy.has(d.deviceName)) btPick.list.set(d.deviceId, d.deviceName);
    if (first || btPick.list.size !== n0) { btPick.sent = true; sendBtList(); } // 新しい台が見つかったときだけ送る（11/12 夜：1秒に何回も送ると、一覧のボタンが押しにくかった）
  });
}

// 本体を選ぶ（11/12）：探している間に見つかった本体（btPick.list）を操作パネルへ。選んだら（または 30秒・やめる で）返事をする
let btPick = null;
// 11/13：本体の電源を入れたら、自動で PC につなぐ。一度つないだ本体の名前を覚えておき（settings.knownDevices）、
//   覚えている本体のうち、つながっていない台があるときだけ、15秒ごとに6秒ほど探す。見つかったらつなぐ（選ばなくてよい）。
//   手でつないでいる間（btPick）・声の基板をつないでいる間（micPick）は探さない。パネルで「切る」にした台（autoSkip）は、次に手でつなぐまで自動ではつながない
let autoPick = null;
const autoSkip = new Set();
function autoPickDone(id) { if (!autoPick) return; clearTimeout(autoPick.timer); const cb = autoPick.callback; autoPick = null; if (cb) cb(id || ''); }
setInterval(() => {
  if (!overlay || autoPick || btPick || micPick || demoRunning) return;
  const known = (settings.knownDevices || []).filter((n) => !autoSkip.has(n));
  if (!known.length) return;
  const have = new Set((state.devices || []).map((d) => d.name)); // つながっている・つなぎ直している最中の台
  if (known.every((n) => have.has(n))) return;
  autoPick = { callback: null, timer: setTimeout(() => autoPickDone(''), 6000) };
  call('autoConnect()');
}, 15000);
function btPickDone(id) { if (!btPick) return; clearTimeout(btPick.timer); const cb = btPick.callback; btPick = null; sendBtList(); if (cb) cb(id || ''); }
function sendBtList() {
  if (!panel) return;
  const nick = settings.deviceNames || {};
  panel.webContents.send('bt-list', btPick ? [...btPick.list].map(([id, name]) => ({ id, name, nick: nick[name] || '' })) : null);
}
// ページ側の関数を呼ぶ（Bluetooth は「人が操作した」扱いでないと始められないので、userGesture を付ける）
function call(fn) { if (overlay) overlay.webContents.executeJavaScript(`window.shinkokyuDesktop && window.shinkokyuDesktop.${fn}`, true).catch(() => {}); }
// 11/15：ページの準備ができるまで待ってから呼ぶ（15秒まで）。ページは曲を読みこんでから shinkokyuDesktop を作るので、
//   読みこみ終わり（did-finish-load）の時点ではまだなく、そこで送った「PC の音を出す」が毎回消えていた（11/13 から PC の音が鳴らなかった）
function callReady(fn) { if (overlay) overlay.webContents.executeJavaScript(`(async () => { for (let i = 0; i < 75 && !window.shinkokyuDesktop; i++) await new Promise((r) => setTimeout(r, 200)); if (window.shinkokyuDesktop) { window.shinkokyuDesktop.${fn}; return true; } return false; })()`, true).then((ok) => { if (!ok) log('page_call_fail', { fn: fn.slice(0, 40) }); }).catch(() => {}); }

// 今、画面に煙が出ているか（設定で表示している・演出で一時的に出している）。ボタンの表示はこちらに合わせる
function shownNow() { return visible || tempShown; }
// 「煙を隠す」を押した：演出で一時的に出していても隠す。その演出（一服の途中・知らせなど）が終わるまでは、もう出さない
// （11/07：吹きかけてやめた一服が続いている扱いになり、隠してもすぐまた出てきた）
let tempBlocked = false;
function hideSmoke() { tempBlocked = tempShown || state.inSession || state.msg || state.sign || state.voice; setVisible(false); log('smoke_hide', { blocked: tempBlocked || undefined }); }
function setVisible(v) {
  if (v) tempBlocked = false;
  visible = v; tempShown = false;
  if (overlay) { if (v || gameMode()) { overlay.showInactive(); gaugeOnTop(); } else overlay.hide(); } // ゲームの見せ方では隠さない（何も描かない透明な窓のまま動かす）
  sendGauge();
  sendPanelState();
}

// 本体なしで試すとき：煙の窓をいったん操作できるようにして、スペースキーを受け取る
function setKeys(on) {
  keysMode = on;
  if (!overlay) return;
  overlay.setIgnoreMouseEvents(!on, { forward: true });
  overlay.setFocusable(on);
  if (on) { overlay.show(); overlay.focus(); }
  sendPanelState();
}

// メッセージの窓の上にマウスが来たときだけ、押せるようにする（マウスの位置を、アプリの側で1秒に20回見る）
let msgRect = null, capturing = false;
ipcMain.on('msg-rect', (_e, r) => { msgRect = r; });
ipcMain.on('show-smoke', () => setVisible(true)); // 休憩の通知を押したら、煙を表示する
setInterval(() => {
  if (!overlay || keysMode) return;
  let inside = false;
  if (msgRect && overlay.isVisible()) {
    const c = screen.getCursorScreenPoint(), b = overlay.getBounds();
    const x = c.x - b.x, y = c.y - b.y;
    inside = x >= msgRect.x && x <= msgRect.x + msgRect.w && y >= msgRect.y && y <= msgRect.y + msgRect.h;
  }
  if (inside !== capturing) {
    capturing = inside;
    overlay.setIgnoreMouseEvents(!inside, { forward: true });
    overlay.setFocusable(inside); // 窓の上にいる間だけ、押せる（前に出られる）窓にする
    console.log(`[shinkokyu] メッセージの窓の上：${inside ? 'はい' : 'いいえ'}`);
  }
}, 50);

// 演出（早送り・吹き終わり）の間だけ、煙を隠していても一時的に出す。終わったら元の設定に戻す
function showTemp() {
  if (!overlay || visible || tempBlocked) return;
  tempShown = true;
  overlay.showInactive();
  gaugeOnTop();
  if (trialWin && trialWin.isVisible()) trialWin.moveTop(); // 休憩の実験の窓は、煙より手前のまま
}

// ---------------- 11/14：心拍数の窓（発表用）。心拍を送れる腕時計・バンド・心拍計（Bluetooth の心拍の決まり）とつなぐ ----------------
// いつも手前（パワポのスライドショーの上にも出る）。押してもフォーカスを奪わない。つかんで動かせる。場所は覚える
let hr = null, hrPick = null, hrDrag = null, hrInfo = { text: 'つないでいません', bpm: null, name: '', base: null };
const HR_SIZES = [{ key: 's', label: '小', scale: 0.75 }, { key: 'm', label: 'ふつう', scale: 1 }, { key: 'l', label: '大', scale: 1.5 }, { key: 'xl', label: '発表用', scale: 2 }, { key: 'xxl', label: '発表用・最大', scale: 3 }]; // 11/14：心拍数の窓の大きさ
const hrScaleNow = () => (HR_SIZES.find((g) => g.key === settings.hrSize) || HR_SIZES[1]).scale;
const hrW = () => Math.round(260 * hrScaleNow()), hrH = () => Math.round(96 * hrScaleNow()); // 11/14：グラフをやめて、低くした
function hrHome() { const { workArea: a } = screen.getPrimaryDisplay(); return { x: a.x + a.width - hrW() - 10, y: a.y + 10 }; } // 右上
function hrStartPos() {
  const p = settings.hrPos;
  if (p && screen.getAllDisplays().some(({ workArea: a }) => p.x >= a.x && p.y >= a.y && p.x + hrW() <= a.x + a.width && p.y + hrH() <= a.y + a.height)) return p;
  return hrHome();
}
function placeHr(x, y) { if (hr) hr.setBounds({ x: Math.round(x), y: Math.round(y), width: hrW(), height: hrH() }); }
function hrPickDone(id) { if (!hrPick) return; clearTimeout(hrPick.timer); const cb = hrPick.callback; hrPick = null; if (cb) cb(id || ''); }
function createHr() {
  const pos = hrStartPos();
  hr = new BrowserWindow({
    x: pos.x, y: pos.y, width: hrW(), height: hrH(),
    transparent: true, frame: false, resizable: false, movable: true, skipTaskbar: true, focusable: false,
    alwaysOnTop: true, hasShadow: false, show: false, backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'hr-preload.js'), backgroundThrottling: false },
  });
  hr.setAlwaysOnTop(true, 'screen-saver');
  hr.loadFile(path.join(__dirname, 'hr.html'));
  hr.webContents.on('did-finish-load', () => hr.webContents.send('hr-scale', hrScaleNow()));
  hr.once('ready-to-show', () => { if (settings.hrShow) { hr.showInactive(); hr.moveTop(); } });
  // 選ぶ画面は出さず、自動で選ぶ（心拍を送っているものだけが見つかる）。HUAWEI・Band・Watch の名前を優先。ほかの名前なら3秒待って最初のもの。15秒でやめる
  hr.webContents.on('select-bluetooth-device', (event, devices, callback) => {
    event.preventDefault();
    if (!hrPick) hrPick = { callback, first: null, timer: setTimeout(() => hrPickDone(''), 15000) };
    hrPick.callback = callback;
    const pref = devices.find((d) => /huawei|band|watch/i.test(d.deviceName || ''));
    if (pref) { log('hr_pick', { name: pref.deviceName }); hrPickDone(pref.deviceId); return; }
    if (devices.length && !hrPick.first) {
      hrPick.first = devices[0];
      setTimeout(() => { if (hrPick && hrPick.first) { log('hr_pick', { name: hrPick.first.deviceName }); hrPickDone(hrPick.first.deviceId); } }, 3000);
    }
  });
}
function hrCall(fn) { if (hr) hr.webContents.executeJavaScript(`window.${fn}`, true).catch(() => {}); }
function setHrShow(on) { settings.hrShow = !!on; saveSettings(); if (hr) { if (on) { hr.showInactive(); hr.moveTop(); } else hr.hide(); } sendPanelState(); }
// 11/15：窓の − ・＋ ボタン。押したのが窓のページとアプリの側（uiohook）の両方に届くことがあるので、続けて 2 回は数えない
let hrBtns = [], hrStepAt = 0;
function hrStep(step, via) {
  const now = Date.now(); if (now - hrStepAt < 300) return; hrStepAt = now;
  const i = Math.max(0, HR_SIZES.findIndex((g) => g.key === settings.hrSize));
  const j = Math.min(HR_SIZES.length - 1, Math.max(0, (settings.hrSize ? i : 1) + (step > 0 ? 1 : -1)));
  log('hr_size', { size: HR_SIZES[j].key, via });
  setHrSize(HR_SIZES[j].key);
}
ipcMain.on('hr-size-step', (_e, step) => hrStep(Number(step), 'page'));
ipcMain.on('hr-btns', (_e, rects) => { hrBtns = Array.isArray(rects) ? rects : []; });
function setHrSize(key) {
  if (!HR_SIZES.some((g) => g.key === key)) return;
  settings.hrSize = key;
  if (hr) {
    const b = hr.getBounds(), a = screen.getDisplayMatching(b).workArea; // 右上の角を動かさずに大きく（小さく）する
    const x = Math.min(Math.max(a.x, b.x + b.width - hrW()), a.x + a.width - hrW()), y = Math.min(Math.max(a.y, b.y), a.y + a.height - hrH());
    placeHr(x, y); hr.webContents.send('hr-scale', hrScaleNow());
    if (settings.hrPos) settings.hrPos = { x, y };
  }
  saveSettings(); sendPanelState();
}
ipcMain.on('hr-status', (_e, s) => { hrInfo = { ...hrInfo, ...(s || {}) }; sendPanelState(); });
function endHrDrag() {
  if (!hrDrag) return;
  clearInterval(hrDrag.timer); hrDrag = null;
  if (!hr) return;
  const b = hr.getBounds(); placeHr(b.x, b.y);
  settings.hrPos = { x: b.x, y: b.y }; saveSettings();
}
function startHrDrag() {
  if (!hr || hrDrag) return;
  const c = screen.getCursorScreenPoint(), b = hr.getBounds();
  hrDrag = { ox: c.x - b.x, oy: c.y - b.y, until: Date.now() + 60000 };
  hrDrag.timer = setInterval(() => {
    if (!hrDrag || Date.now() > hrDrag.until) { endHrDrag(); return; }
    const p = screen.getCursorScreenPoint(); placeHr(p.x - hrDrag.ox, p.y - hrDrag.oy);
  }, 16);
}
ipcMain.on('hr-drag', (_e, cmd) => { if (cmd === 'start') startHrDrag(); else if (cmd === 'end') endHrDrag(); });

// ---------------- 操作パネル（通知領域のアイコンを押すと出る。ボタンを押しても閉じない。外を押すと閉じる） ----------------
let micPick = null; // 声の基板を探している最中（11/13：自動で本体を探すのと重ならないように、外からも見る）
function createPanel() {
  panel = new BrowserWindow({
    width: 320, height: 800, frame: false, resizable: false, skipTaskbar: true, alwaysOnTop: true, show: false,
    backgroundColor: '#0b0d12',
    webPreferences: { preload: path.join(__dirname, 'panel-preload.js') },
  });
  panel.setAlwaysOnTop(true, 'pop-up-menu');
  panel.loadFile(path.join(__dirname, 'panel.html'));
  // 声の基板（Sense 版「ShinkokyuMic-XXXX」）を選ぶ画面は出さず、自動で選ぶ（10秒見つからなければあきらめる）
  panel.webContents.on('select-bluetooth-device', (event, devices, callback) => {
    event.preventDefault();
    const dev = devices.find((d) => (d.deviceName || '').startsWith('ShinkokyuMic'));
    if (dev) { clearTimeout(micPick); micPick = null; callback(dev.deviceId); return; }
    if (!micPick) micPick = setTimeout(() => { micPick = null; callback(''); }, 10000);
  });
  panel.on('blur', () => { if (!panel.webContents.isDevToolsOpened()) panel.hide(); });
}
function togglePanel() {
  if (!panel) return;
  if (panel.isVisible()) { panel.hide(); return; }
  // 通知領域のアイコンのすぐ上（画面の右下）に出す
  const b = tray.getBounds(), { workArea } = screen.getDisplayNearestPoint({ x: b.x, y: b.y });
  const [w, h] = panel.getSize();
  const x = Math.min(Math.max(workArea.x, Math.round(b.x + b.width / 2 - w / 2)), workArea.x + workArea.width - w);
  const y = b.y > workArea.y + workArea.height / 2 ? workArea.y + workArea.height - h - 8 : workArea.y + 8;
  panel.setPosition(x, y);
  panel.show(); panel.focus();
  sendPanelState();
}
// 休みどきの理由（口実）：つづけて作業した時間と、ふだんとのちがい（10秒ごとに計算しなおす）
let reasonCache = null, reasonAt = 0;
function reasonNow(fresh = false) {
  if (!rhythm) return null;
  if (fresh || !reasonCache || Date.now() - reasonAt > 10000) { reasonCache = makeReason(rhythm.rows, Date.now(), rhythm.lastSessionEnd); reasonAt = Date.now(); }
  return reasonCache;
}
ipcMain.handle('reason', () => reasonNow(true)); // 煙の画面が、休憩の通知を出すときに聞く

// 11/13：PC からも本体の音を出す（settings.pcSound＝{ on, vol 0〜10 }）。煙のページ（retro.html）が鳴らす
function applyPcSound(atLoad) { const p = settings.pcSound || {}; (atLoad ? callReady : call)(`setPcSound(${!!p.on}, ${Number.isFinite(p.vol) ? p.vol : 6})`); log('pc_sound_apply', { on: !!p.on, vol: p.vol }); } // 11/15：起動時に PC の音が出る設定だったかを記録に残す
function sendPanelState() {
  if (panel) panel.webContents.send('state', { ...state, fireName: fire ? fire.view().name : '', visible: shownNow(), keysMode, rhythm: rhythm && rhythm.latest, trialKey: TRIAL_KEY_LABEL, trialToday: todayCount('trial'), soloToday: todayCount('solo'), trialOpen: !!trialWin, reason: reasonNow(), voiceKey: VOICE_KEY_LABEL, settings, hr: hrInfo });
}
ipcMain.on('panel', (_e, cmd, arg) => {
  if (cmd === 'visible') (arg ? setVisible(true) : hideSmoke());
  else if (cmd === 'view') setView(arg ? 'game' : 'smoke');
  else if (cmd === 'firedemo') fireDemo();
  else if (cmd === 'firereset') fireReset();
  else if (cmd === 'pcsound') { const p = arg || {}; settings.pcSound = { on: !!p.on, vol: Math.max(0, Math.min(10, Number(p.vol) || 0)) }; saveSettings(); applyPcSound(); log('pc_sound_setting', settings.pcSound); sendPanelState(); }
  else if (cmd === 'pctest') { call('pcTest()'); log('pc_sound_test'); }
  else if (cmd === 'firerestore') fireRestore();
  else if (cmd === 'connect') { if (btPick) return; if (autoPick) { autoPickDone(''); setTimeout(() => call('connect()'), 400); } else call('connect()'); } // 11/13：自動で探している最中なら、先にやめる
  else if (cmd === 'btpick') btPickDone(String(arg || ''));   // 一覧から選んだ本体（'' はやめる）
  else if (cmd === 'devlight') call(`light(${JSON.stringify(String(arg))})`);   // その本体の LED を紫に光らせる（どれがどの台か確かめる）
  else if (cmd === 'devunplug') { autoSkip.add(String(arg)); call(`unplug(${JSON.stringify(String(arg))})`); } // 11/13：切った台は、自動ではつながない // その本体を切る（自動でつなぎ直さない）
  else if (cmd === 'devnick' && arg && arg.name) { settings.deviceNames = { ...(settings.deviceNames || {}), [arg.name]: String(arg.nick || '').slice(0, 12) }; saveSettings(); sendPanelState(); } // 呼び名
  else if (cmd === 'full') { setVisible(true); call('full()'); }
  else if (cmd === 'fill') call(`setFill(${Number(arg)})`);
  else if (cmd === 'volume') call(`setVolume(${Number(arg)})`);
  else if (cmd === 'replay') { showTemp(); call('replay()'); }
  else if (cmd === 'keys') setKeys(!!arg);
  else if (cmd === 'keyBreath') call(`keyBreath(${!!arg})`); // 操作パネルでスペースキーを押している間＝吹いている（11/11）
  else if (cmd === 'moya') { setVisible(true); call(`addMoya(${JSON.stringify(String(arg))})`); } // 言葉を書いたら、煙を見せる
  else if (cmd === 'close') panel.hide();
  else if (cmd === 'logs') shell.openPath(logDir());
  else if (cmd === 'trial') openTrial('panel');
  else if (cmd === 'trialquit') quitTrial();
  else if (cmd === 'gauge') setGauge(!!arg);
  else if (cmd === 'gaugesize') setGaugeSize(String(arg));
  else if (cmd === 'noticesize') setNoticeSize(String(arg));
  else if (cmd === 'presentsize') { setGaugeSize(arg ? 'present' : 'normal'); setNoticeSize(arg ? 'present' : 'normal'); } // 発表用（両方まとめて）／ふつうに戻す
  else if (cmd === 'labels') { if (['present', 'always', 'never'].includes(arg)) { settings.labels = arg; saveSettings(); log('labels_mode', { mode: arg }); sendPanelState(); } }
  else if (cmd === 'sign') { if (arg) showTemp(); call(`sign(${!!arg})`); } // 席の札「シン呼吸中」
  else if (cmd === 'invite') invite('panel'); // 一服のお誘いを試す
  else if (cmd === 'hrconnect') { setHrShow(true); setTimeout(() => hrCall('hrConnect()'), 300); } // 11/14：心拍数の窓
  else if (cmd === 'hrshow') setHrShow(!!arg);
  else if (cmd === 'hrbase') hrCall('hrResetBase()');
  else if (cmd === 'hrsize') setHrSize(String(arg));
  else if (cmd === 'hroff') hrCall('hrDisconnect()');
  else if (cmd === 'quit') app.quit();
});

// ---------------- 一服のお誘い（S06） ----------------
// 本体の曲送りボタンの長押し（または操作パネル・通知領域のメニューの「試し」）で届く。
// 火の子の吹き出しで知らせて、本体と Sense 版の LED を紫に点滅させる（11/11：Windows の通知はやめた）。誰からかは出さず、記録もしない
// 同じ PC の中だけで受け渡す（別の人の PC へ送る仕組みは、まだない）
const INVITE_SEC = 10;   // 点滅と画面の知らせの長さ
let lastInvite = 0;
function invite(via) {
  if (Date.now() - lastInvite < 5000) return; // 押しまちがいで何度も出さない
  lastInvite = Date.now();
  log('invite', { via });
  // 11/11：Windows の通知（横から出る窓）は出さない。火の子の吹き出しと重なって見づらかったため。知らせは火の子の吹き出しだけ
  showTemp(); // 煙を隠していても、知らせの間だけ画面に出す
  call(`invited(${INVITE_SEC})`);
  toast(['お誘いが とどいた。', '〔火を わけに〕 いこう'], { mood: 'blow' });
  if (panel) panel.webContents.executeJavaScript(`typeof mic !== 'undefined' && mic.connected && mic.send('LIGHT ${INVITE_SEC}')`, true).catch(() => {});
}
ipcMain.on('invite', (_e, via) => invite(String(via || 'device')));
// 本体の音量＋と−の同時押し：声を録る（録っていなければ始め、録っていれば終える。Ctrl+Alt+M と同じ。11/11）
// 11/15：本体の＋−同時押し（TALK）が、続けて2回届いたら1回とみなす（1秒以内）。
//   11/14 深夜：同じ本体が2つ分つながって TALK が2回届き、録り始めた直後に止まって文字にならなかった（voice_cancel noend）
let talkAt = 0;
ipcMain.on('talk', () => {
  const now = Date.now();
  if (now - talkAt < 1000) { log('talk_dup', { ms: now - talkAt }); return; }
  talkAt = now;
  if (panel) panel.webContents.send('voice', 'toggle-device');
});

// ページから届く、たまり具合のアイコンの絵と、今の様子
ipcMain.on('tray-icon', (_e, dataUrl, tooltip) => {
  if (!tray) return;
  tray.setImage(nativeImage.createFromDataURL(dataUrl));
  if (tooltip) tray.setToolTip(tooltip);
});
ipcMain.on('log', (_e, type, data) => {
  if (type === 'exhale_start' && gameMode()) { gaugeDismissed = false; gaugeTempShow(); } // 11/13：× で消していても、吸い始めたらまた火の子を出す
  if (type === 'device_connect' && data && data.name) { // 11/13：つながった本体を覚える（次からは電源を入れれば自動でつながる）
    autoSkip.delete(data.name);
    const k = settings.knownDevices || [];
    if (!k.includes(data.name)) { settings.knownDevices = [...k, data.name]; saveSettings(); }
  }
  if (type === 'device_dup' && gameMode()) toast(['その本体は もう つながっているよ', `〔${(settings.deviceNames || {})[data && data.name] || (data && data.name) || ''}〕`, 'もう1台は、ちがう名前を えらんでね'], { mood: 'think' }); // 11/13：同じ本体を二重に選んだ
  log(type, data);
  fireEvent(type, data || {});
  // 休憩の実験の「過ごし方」の間に本体に吹いた息は、その回の記録にも入れる
  if (type === 'breath' && trial && trial.phase === 'act' && data) trial.breaths.push({ t: +((Date.now() - trial.actStart) / 1000).toFixed(1), sec: data.sec, source: data.source });
}); // ページからの記録（息・通知・吹き終わり）
ipcMain.on('state', (_e, s) => {
  // 本体が2台そろった：2つの火を寄せて焚き火に（右下の小窓）。吹き出しで知らせる
  const c0 = connectedCount(), c1 = (s.devices || []).filter((d) => d.connected).length;
  if (gameMode() && fire && c0 < 2 && c1 >= 2 && !trialWin) toast(['本体が 2台 そろった。', 'ふたりの火を よせて', '〔焚き火〕を かこもう'], { mood: 'blow', kind: 'pair' });
  if (!state.inSession && s.inSession) { log('session_start'); gaugeDismissed = false; } // 新しい一服：消していても、吸っている間はまた火の子を出す
  if (state.inSession && !s.inSession) log('session_end');
  if (s.inSession && gameMode()) gaugeTempShow();   // 吹き始めたら、隠していても火の子を出す（11/11）
  if (state.inSession && !s.inSession) gaugeTempHide(12000);
  if (state.inSession && !s.inSession) { endedAt = Date.now(); if (rhythm) rhythm.lastSessionEnd = Date.now(); } // 一服が終わった（つづけて作業した時間は、ここから数えなおす）
  // 席の札：PC の前で吹き終わった（さっきまで操作していた）なら、吹き終わりでおろす
  if (state.inSession && !s.inSession && s.sign && powerMonitor.getSystemIdleTime() < 5) call("signOff('end')");
  if (tempBlocked && !s.inSession && !s.done && !s.replaying && !s.msg && !s.sign && !s.voice) tempBlocked = false; // 隠した演出が終わった：次の演出からまた見せる
  if (s.inSession || s.done || s.sign || s.voice) showTemp(); // 吹いている間・吹き終わり・席の札・声の知らせは、隠していても見せる
  // 一時的に出していた演出が全部終わったら、元の設定（隠す）に戻す
  if (tempShown && !visible && !gameMode() && !s.inSession && !s.done && !s.replaying && !s.msg && !s.sign && !s.voice) { tempShown = false; overlay.hide(); }
  state = s;
  sendPanelState();
  sendTrialState();
  sendGauge();
});

// ---------------- 休憩の実験（約10分）：反応テスト → くじで決まった過ごし方（3分）→ 反応テスト ----------------
// - やる人が合図をして始める：操作パネル・通知領域のメニュー・Ctrl+Alt+R・デスクトップのショートカット（--trial）
// - 過ごし方は3つ。「時間がたっただけで戻った」のか「深呼吸で戻った」のかを分けるため、どれも同じ3分にする
//     深呼吸（本体に吹く）／呼吸しないで休む（本体なしで、ふつうに座る）／休まない（作業を続ける）
//   本体がつながっていないときは、くじは「呼吸しないで休む」「休まない」の2つから（基板が2台しかないため）
// - 「反応テストだけ」（3分を1回）も選べる
// - 窓が開いている間は、キーボードとマウスを見る仕組みを止める（テストのキーの届き方に影響しないように。「休まない」の3分だけ動かす）
const TRIAL_KEY = 'CommandOrControl+Alt+R', TRIAL_KEY_LABEL = 'Ctrl+Alt+R';
const ARMS = {
  breath: { label: '深呼吸（本体）', how: '本体から、ゆっくり長く吸ってください（吐くのは鼻から）。3分つづけます' },
  rest: { label: '呼吸しないで休む', how: '本体は使わずに、ふつうに座って待ってください。深呼吸はしないで、スマホも見ないで。3分です' },
  work: { label: '休まない', how: '作業にもどってください。この窓はかくれて、3分たったら知らせます' },
};
const expFile = () => path.join(app.getPath('userData'), 'experiment.json');
// block：本体ありのくじの残り（3回で3つが1回ずつ）。block2：本体なしのくじの残り（2回で2つが1回ずつ）。count：日ごとの回数
let exp = { block: [], block2: [], count: {} };
const NO_DEVICE_ARMS = ['rest', 'work'];
let trialWin = null, trial = null, lastNotice = null;
const today = () => new Date().toLocaleDateString('sv-SE');
function loadExp() {
  try { exp = { ...exp, ...JSON.parse(fs.readFileSync(expFile(), 'utf8')) }; } catch {}
  exp.block = (exp.block || []).filter((a) => ARMS[a]); delete exp.pending; delete exp.days; // 前の版の名前は使わない
  exp.block2 = (exp.block2 || []).filter((a) => NO_DEVICE_ARMS.includes(a));
  exp.count = exp.count || {};
}
function saveExp() { try { fs.writeFileSync(expFile(), JSON.stringify(exp)); } catch {} }
const todayCount = (mode) => exp.count[`${today()}:${mode}`] || 0;
function drawArm(device) {
  const key = device ? 'block' : 'block2';
  if (!exp[key] || !exp[key].length) {
    const b = device ? Object.keys(ARMS) : [...NO_DEVICE_ARMS];
    for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [b[i], b[j]] = [b[j], b[i]]; }
    exp[key] = b;
  }
  const a = exp[key].shift();
  saveExp();
  return a;
}
function breathSummary(b, sec) {
  if (!b.length) return { count: 0 };
  const xs = b.map((x) => x.sec), mean = xs.reduce((s, x) => s + x, 0) / xs.length;
  const sd = xs.length > 1 ? Math.sqrt(xs.reduce((s, x) => s + (x - mean) ** 2, 0) / (xs.length - 1)) : 0;
  return { count: xs.length, perMin: +(xs.length / (sec / 60)).toFixed(1), exhaleMean: +mean.toFixed(1), exhaleCv: +(sd / mean).toFixed(3), exhaleTotal: +xs.reduce((s, x) => s + x, 0).toFixed(1) };
}
function openTrial(via, quick = false) {
  if (trialWin) { trialWin.show(); trialWin.moveTop(); trialWin.focus(); return; }
  if (panel) panel.hide();
  const { workArea } = screen.getPrimaryDisplay(); // 画面いっぱい（タスクバーは残す）。外を押して入力が外れないように
  trialWin = new BrowserWindow({
    ...workArea, frame: false, resizable: false, movable: false, alwaysOnTop: true, show: false,
    backgroundColor: '#0b0d12', title: 'シン呼吸 休憩の実験',
    webPreferences: { preload: path.join(__dirname, 'trial-preload.js'), backgroundThrottling: false },
  });
  trialWin.setAlwaysOnTop(true, 'screen-saver'); // 煙の窓より手前
  trialWin.loadFile(path.join(__dirname, 'trial.html'), quick ? { query: { quick: '1' } } : undefined);
  trialWin.once('ready-to-show', () => { trialWin.show(); trialWin.moveTop(); trialWin.focus(); sendTrialState(); });
  trialWin.on('closed', () => {
    if (trial && trial.pair && !trial.finished) log('trial_cancel', { pair: trial.pair, phase: trial.phase, arm: trial.arm });
    trialWin = null; trial = null;
    call('testMode(false)');
    if (rhythm) rhythm.resume();
    away = false; endedAt = 0;
    sendPanelState();
  });
  trial = { via, quick, phase: 'intro' };
  if (rhythm) rhythm.pause();
  call('testMode(true)'); // 煙の画面：休憩の通知や「一服おわり」の演出を出さない
  log('trial_open', { via, quick: quick || undefined });
}
function sendTrialState() {
  if (!trialWin) return;
  const live = (state.devices || []).filter((d) => d.connected);
  trialWin.webContents.send('app-state', { connected: live.length > 0, names: live.map((d) => d.name) });
}
ipcMain.on('trial-connect', () => call('connect()'));
ipcMain.handle('trial-begin', (_e, mode) => {
  if (!trial) return {};
  trial.mode = mode === 'solo' ? 'solo' : 'trial';
  trial.device = (state.devices || []).some((d) => d.connected); // 本体がつながっているか（くじに「深呼吸」を入れるか）
  trial.pair = Date.now().toString(36); trial.phase = trial.mode === 'solo' ? 'solo' : 'pre';
  log('trial_start', { pair: trial.pair, mode: trial.mode, device: trial.device, via: trial.via, quick: trial.quick || undefined, nToday: todayCount(trial.mode) + 1 });
  return { pair: trial.pair };
});
function countDone() { if (!trial.quick) { const k = `${today()}:${trial.mode}`; exp.count[k] = (exp.count[k] || 0) + 1; saveExp(); } }
ipcMain.on('trial-pvt-start', (_e, kind) => {
  if (!trial) return;
  trial.phase = kind;
  if (kind === 'post') trial.postDelaySec = +((Date.now() - trial.actEnd) / 1000).toFixed(1); // 過ごし方が終わってから、テストを始めるまで
});
ipcMain.handle('trial-pvt-done', (_e, kind, r) => {
  if (!trial) return {};
  const row = {
    pair: trial.pair, kind, quick: trial.quick || undefined, ...r.stats, durationSec: Math.round(r.durationMs / 1000),
    rts: r.trials.map((x) => x.rt), at: r.trials.map((x) => x.t), lost: r.trials.map((x) => x.f),
  };
  if (kind === 'solo') { // 反応テストだけ
    log('pvt', row);
    trial.finished = true; trial.phase = 'result';
    countDone();
    log('trial_end', { pair: trial.pair, mode: 'solo' });
    sendPanelState();
    return {};
  }
  if (kind === 'pre') {
    log('pvt', row);
    const arm = drawArm(trial.device);
    trial.arm = arm; trial.pre = r.stats; trial.preEnd = Date.now(); trial.phase = 'lot';
    log('lottery', { pair: trial.pair, arm, device: trial.device });
    return { arm, ...ARMS[arm] };
  }
  log('pvt', { ...row, arm: trial.arm, postDelaySec: trial.postDelaySec });
  trial.finished = true; trial.phase = 'result';
  countDone();
  log('trial_end', { pair: trial.pair, mode: 'trial', arm: trial.arm });
  sendPanelState();
  return { before: trial.pre, breath: trial.breath };
});
ipcMain.on('trial-act-start', () => {
  if (!trial) return;
  trial.phase = 'act'; trial.actStart = Date.now(); trial.breaths = [];
  log('activity_start', { pair: trial.pair, arm: trial.arm, device: trial.device, volume: state.volume, delaySec: +((Date.now() - trial.preEnd) / 1000).toFixed(1) }); // 音量0（音なし）で吹いた回も分かるように
  if (trial.arm === 'breath') call('testBreath()'); // 曲を最初から
  if (trial.arm === 'work') { trialWin.hide(); if (rhythm) rhythm.resume(); }
});
ipcMain.handle('trial-act-end', () => {
  if (!trial) return {};
  const sec = (Date.now() - trial.actStart) / 1000;
  // どの過ごし方でも、本体に吹いた息は数える（「呼吸しないで休む」なのに吹いていないかも分かる）
  trial.breath = breathSummary(trial.breaths, sec);
  log('activity', { pair: trial.pair, arm: trial.arm, sec: Math.round(sec), ...trial.breath, breaths: trial.breaths });
  trial.phase = 'mid'; trial.actEnd = Date.now();
  if (trial.arm === 'work') {
    if (rhythm) rhythm.pause();
    trialWin.show(); trialWin.moveTop(); trialWin.focus();
    lastNotice = new Notification({ title: '3分たちました', body: '休憩の実験：もう一度、反応テストをしてください' });
    lastNotice.on('click', () => { if (trialWin) { trialWin.show(); trialWin.focus(); } });
    lastNotice.show();
  }
  return trial.breath;
});
// 強制的に終わる：窓の中の「やめる」が効かないときのために、通知領域のメニューと操作パネルからも閉じられる
function quitTrial() { if (trialWin) trialWin.destroy(); }
ipcMain.on('trial-cancel', quitTrial);
ipcMain.on('trial-close', () => { if (trialWin) trialWin.close(); });
ipcMain.on('live', (_e, type, data) => { if (trialWin) trialWin.webContents.send('live', type, data); if (gauge && !trialWin) gauge.webContents.send('live', type, data); }); // 煙の画面から：吹き始め・吹き終わり（右下の火の子も明るくなる）

// ---------------- 火の子（11/08）：一服で育つアバター。右下の小窓にいて、結果は右の吹き出しで知らせる ----------------
let fire = null;
// 右の吹き出しの窓（LINE の通知のように、右下の小窓の上に下から積む。マウスは素通り）
let notice = null;
const NOTICE_W0 = 320, NOTICE_H0 = 380;
// 吹き出しの窓の大きさ（大きさの段に合わせる。画面からはみ出す分は、画面に収まるだけにする：古い吹き出しが上で切れる）
let NOTICE_W = NOTICE_W0, NOTICE_H = NOTICE_H0;
// 11/11：発表用（2倍以上）は横長（幅 1.9倍・高さは吹き出し2つ分）。高さは右下の火の子の上に残っている分まで。収まらない分は、吹き出しの側で少し小さくして収める
function noticeSize() {
  const a = screen.getPrimaryDisplay().workArea, s = noticeScale(), wide = s >= 2;
  const below = gauge && gaugeShown() && gauge.isVisible() ? gauge.getBounds().height + 4 + 10 : 0;
  NOTICE_W = Math.min(Math.round(NOTICE_W0 * s * (wide ? 1.9 : 1)), a.width - 20);
  NOTICE_H = Math.max(200, Math.min(Math.round((wide ? 200 : NOTICE_H0) * s), a.height - 10 - below));
}
// 吹き出しの大きさを変える：変えたら、その大きさで試しに1つ出す（見ながら選べるように）
function setNoticeSize(key) {
  if (!GAUGE_SIZES.some((g) => g.key === key)) return;
  settings.noticeSize = key; saveSettings(); log('notice_size', { size: key }); sendPanelState();
  if (notice) notice.webContents.send('toast-clear');
  toast(['お知らせの大きさを', `〔${sizeOf(key).label}〕 に しました`], { mood: 'blow', life: 4000 });
}
function createNotice() {
  notice = new BrowserWindow({
    width: NOTICE_W, height: NOTICE_H, transparent: true, frame: false, resizable: false, movable: false, skipTaskbar: true, focusable: false,
    alwaysOnTop: true, hasShadow: false, show: false, backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'notice-preload.js'), backgroundThrottling: false }, // 1文字ずつ出す時計を間引かない
  });
  notice.setAlwaysOnTop(true, 'screen-saver');
  notice.setIgnoreMouseEvents(true); // ふだんは素通り。吹き出しの上にマウスがある間だけ、押せるようにする（右上の ×。下の noticeRects）
  notice.loadFile(path.join(__dirname, 'notice.html'));
}
function placeNotice() {
  if (!notice) return;
  noticeSize();
  let x, y;
  if (gauge && gaugeShown() && gauge.isVisible()) { const b = gauge.getBounds(); x = b.x + b.width - NOTICE_W; y = b.y - NOTICE_H - 4; }
  else { const { workArea: a } = screen.getPrimaryDisplay(); x = a.x + a.width - NOTICE_W - 10; y = a.y + a.height - NOTICE_H - 10; }
  const a = screen.getDisplayNearestPoint({ x: x + NOTICE_W, y: y + NOTICE_H }).workArea;
  x = Math.min(Math.max(a.x, x), a.x + a.width - NOTICE_W); y = Math.min(Math.max(a.y, y), a.y + a.height - NOTICE_H);
  notice.setBounds({ x: Math.round(x), y: Math.round(y), width: NOTICE_W, height: NOTICE_H });
}
ipcMain.on('notice-empty', () => { noticeRects = []; noticeGrab(false); if (notice) notice.hide(); });
// 11/13：吹き出しの上にマウスがある間だけ、通知の窓を押せる窓にする（右上の ×）。マウスの位置はアプリが見る（煙の窓のメッセージと同じやり方）
//   前は「マウスの動きだけ受けとる（forward）」設定にしていたが、Windows で、かくれている間もその場所のクリックを横取りし、右下の火の子の × が押せなくなった
let noticeRects = [], noticeGrabbing = false;
function noticeGrab(on) { if (on === noticeGrabbing || !notice) return; noticeGrabbing = on; notice.setIgnoreMouseEvents(!on); }
ipcMain.on('notice-rects', (_e, r) => { noticeRects = Array.isArray(r) ? r : []; });
setInterval(() => {
  if (!notice || !notice.isVisible() || !noticeRects.length) { noticeGrab(false); return; }
  const c = screen.getCursorScreenPoint(), b = notice.getBounds(), x = c.x - b.x, y = c.y - b.y;
  noticeGrab(noticeRects.some((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h));
}, 60);
// 11/11：吹き出しが出ている間、マウスが動いたら吹き出しに知らせる（読める時間がたったものは消える）。少しのぶれ（25px 未満）は数えない
let mouseAnchor = null;
setInterval(() => {
  if (!notice || !notice.isVisible()) { mouseAnchor = null; return; }
  const p = screen.getCursorScreenPoint();
  if (!mouseAnchor) { mouseAnchor = p; return; }
  if (Math.hypot(p.x - mouseAnchor.x, p.y - mouseAnchor.y) >= 25) { mouseAnchor = p; notice.webContents.send('mouse'); }
}, 150);
// 吹き出しを1つ出す。lines：行の並び（〔…〕は少し色をつける）。休憩の実験の間は出さない（反応テストのじゃまをしない）
function toast(lines, o = {}) {
  if (!gameMode() || !notice || trialWin) return;
  const v = fire ? fire.view() : { stage: 0 };
  placeNotice();
  notice.showInactive(); notice.moveTop();
  notice.webContents.send('toast', { lines, name: '火の子', stage: v.stage, mood: o.mood || 'idle', life: o.life, scale: noticeScale(), sticky: !demoRunning }); // sticky：マウスを動かすまで消さない（11/12）
  log('toast', { kind: o.kind });
}
// 席を離れて一服しているときの知らせは、戻ってから「おかえり」と出す
let awayToasts = [];
function toastOrKeep(lines, o) { if (!demoRunning && powerMonitor.getSystemIdleTime() >= 30) awayToasts.push([lines, o]); else toast(lines, o); }
function flushAway(had = false) { // had：まとめの吹き出しを、いま出した（「おかえり。」はそちらに付けた）
  const q = awayToasts; awayToasts = [];
  q.forEach(([lines, o], i) => setTimeout(() => toast(i === 0 && !had ? ['おかえり。', ...lines] : lines, o), (i + (had ? 1 : 0)) * 1400));
}
// 11/13：曲が終わったときの「一服おわり」の吹き出しは、すぐには出さない（続けて吸い始めても、演奏と火の粉のじゃまをしない）。
//   曲が終わったあとに、はじめてマウスかキーボードにさわったとき、何曲ぶんでも1つにまとめて出す。
//   一服の途中で段が上がった知らせ（toastUp）も、吸っている間は出さずに、このまとめに入れる
let summary = null, pendingUp = null, summaryWaitBack = false;
function addSummary(r, grew, together) {
  if (!summary) summary = { songs: 0, good: 0, words: 0, together: false, grew: '', up: null, items: [], doneAt: 0 };
  summary.songs++; summary.good += r.good || 0; summary.words += r.words || 0;
  if (together) summary.together = true;
  if (grew) summary.grew = grew;
  if (r.up || pendingUp) summary.up = r.up || pendingUp;
  pendingUp = null;
  if (r.item) summary.items.push(r.item);
  summary.doneAt = Date.now();
}
function flushSummary(prefix) {
  if (!summary || !fire) return false;
  const s = summary; summary = null;
  const v = fire.view();
  const lines = [
    s.songs > 1 ? `一服 〔${s.songs}曲〕 おわり。` : '一服 おわり。',
    s.good ? `ゆっくり 長い息が 〔${s.good}回〕` : 'つぎは そっと 長く 吸ってみよう',
    s.grew,
    s.words ? `もやもやの薪が 〔${s.words}本〕 燃えた` : '',
    s.together ? 'ふたりの火を よせて 〔焚き火〕を かこんだ' : '',
    s.up ? `火の子が 〔${s.up.name}〕に なった！` : s.items.length ? '' : '火が 少し 大きく なりました',
    ...s.items.slice(-2).map(itemLine),
    goalText(),
  ].filter(Boolean);
  toast(prefix ? [prefix, ...lines] : lines, { mood: 'blow', kind: 'done', life: 10000 });
  return true;
}
// 段が上がったとき
function toastUp(up) { if (!up) return; if (state.inSession && !demoRunning) { pendingUp = up; sendGauge(); return; } const v = fire.view(); toastOrKeep([`火の子が 〔${up.name}〕に なった！`, v.next ? `つぎは ${v.next}` : 'これからは 1本ごとに、まわりが 〔にぎやかに〕 なるよ'], { mood: 'blow', kind: 'stage', life: 9000 }); sendGauge(); }
// B：次の目印（休憩と休憩をつなぐ。11/08）。つぎの段まで あと何本ぐらいか／焚き火なら、次の1本でくる物
// C：焚き火に着いたあとは、1本ごとに焚き火のまわりに1つふえる（減らない）
const campName = (n) => CAMP[n - 1] || '星';
const CAMP_VERB = { 石の輪: 'できた', 丸太のいす: 'ころがってきた', やかん: 'のった', テント: 'たった', ほたる: 'きた' };
const CAMP_SOON = { 石の輪: 'できるよ', 丸太のいす: 'ころがってくるよ', やかん: 'のるよ', テント: 'たつよ', ほたる: 'くるよ' };
const itemLine = (item) => (item === '星' ? '夜空に 〔星〕が ひとつ ふえた' : item === '月' ? '夜空に 〔月〕が のぼった' : `焚き火のまわりに 〔${item}〕が ${CAMP_VERB[item] || 'ふえた'}`);
function goalText() { const g = fire.goal(); if (g.full) return '焚き火のまわりは、もう にぎやか'; return g.item ? (g.item === '星' ? 'つぎの 1本で、夜空に 〔星〕が ふえるよ' : g.item === '月' ? 'つぎの 1本で、夜空に 〔月〕が のぼるよ' : `つぎの 1本で、〔${g.item}〕が ${CAMP_SOON[g.item] || 'ふえるよ'}`) : `〔${g.to}〕まで あと ${g.n}本 ぐらい`; }
function goalShort() { const g = fire.goal(); if (g.full) return 'にぎやかな 焚き火'; return g.item ? `つぎは 〔${g.item}〕` : `〔${g.to}〕まで あと ${g.n}本`; }
// 煙の画面からの記録（息・吹きおわり・休憩の通知）を、火の子の育ちと吹き出しにする
function fireEvent(type, data) {
  if (!fire || trialWin) return;   // 休憩の実験の間は数えない（くじで決めた過ごし方を乱さない）
  if (type === 'breath') {
    toastUp(fire.breath(+data.sec || 0, data.source, +data.peak || 0));
    if (fire.lastStrong && fire.sess && !fire.sess.hinted) { fire.sess.hinted = true; toast(['あちち、火の粉が 散っちゃった', '〔そっと 長く〕 吸うと よく 燃えるよ'], { mood: 'scatter', kind: 'strong', life: 6000 }); }
    sendGauge();
  }
  else if (type === 'session_abandon') fire.abandon();
  else if (type === 'song_done' && !data.test) {
    // 11/11：もやもやの薪は「この曲の終わりに実際に燃えた言葉の数」で数える（煙の画面から届く words）。
    // 前は声を録った時点で数えていたので、一服が取り消されると数だけ消えて、画面に残った言葉を燃やしても育たなかった。文字で書いたもやもやも数える
    if (fire.sess && Number.isFinite(+data.words)) fire.sess.words = Math.max(0, +data.words);
    const together = connectedCount() >= 2;
    const r = fire.done({ together });
    if (!r) { sendGauge(); return; } // 本体に吹いていない1本（キーボード）では育たない
    const b = data.breaths || [], k = Math.max(1, Math.min(3, Math.floor(b.length / 2)));
    const avg = (a) => a.reduce((s, x) => s + x, 0) / a.length;
    const grew = b.length >= 2 && avg(b.slice(-k)) > avg(b.slice(0, k)) + 0.2 ? `息が ${avg(b.slice(0, k)).toFixed(1)}秒 → 〔${avg(b.slice(-k)).toFixed(1)}秒〕 に のびた` : '';
    addSummary(r, grew, together); // 11/13：すぐには出さない。曲のあと、はじめて PC にさわったときに、まとめて1つ出す
    sendGauge();
  } else if (type === 'notify' && data.kind === 'full') {
    const r = reasonNow(true);
    toast(['そろそろ 火、つけに いこ', ...((r && r.lines) || []), fire.s.ippuku ? `前の火の つづき：${goalShort()}` : ''].filter(Boolean), { mood: 'sleepy', kind: 'full', life: 12000 });
  }
}
// 火の子のためし（記録しない）：仮の火の子で、知らせ → 吹く → 育つ → お誘い → 薪 → 2人の焚き火 を約40秒で見せる（発表の練習・見た目の確かめ用）
let demoTimers = [], demoRunning = false, demoView = null;
// 11/12：火の子の育ち具合を最初（火種）に戻す（発表・ためし用）。
// 戻す前の育ち具合は settings.fireBackup に取っておき、「元の育ち具合に戻す」でいつでも戻せる（何回戻しても、取っておくのは最初の1つ＝本当の育ち具合）
function fireReset() {
  if (!fire) return;
  if (!settings.fireBackup) settings.fireBackup = { ...fire.s };
  fire.s = { warmth: 0, ippuku: 0, together: 0, camp: 0, born: Date.now() };
  fire.sess = null; fireFrozen = null; firePresent = null;
  summary = null; pendingUp = null; awayToasts = []; // 11/13：戻す前の「一服おわり」のまとめ・段が上がった知らせが、戻したあとに出ないように
  fire.save(fire.s);
  log('fire_reset', { backupWarmth: settings.fireBackup.warmth });
  sendGauge(); sendPanelState();
  toast(['はじめまして。〔火種〕です', '本体から そっと 長く 吸うと', 'ぼくの 火が あたたまるよ']);
}
function fireRestore() {
  if (!fire || !settings.fireBackup) return;
  fire.s = { ...settings.fireBackup }; delete settings.fireBackup;
  fire.sess = null; fireFrozen = null; firePresent = null;
  summary = null; pendingUp = null; awayToasts = []; // 11/13：同上
  fire.save(fire.s);
  log('fire_restore', { warmth: fire.s.warmth });
  sendGauge(); sendPanelState();
  toast([`もとの 〔${fire.view().name}〕に もどったよ`]);
}
function fireDemo() {
  if (!gameMode() || trialWin) return;
  demoRunning = true; fireFrozen = null; demoView = { pair: false, wood: 0 };
  demoTimers.forEach(clearTimeout); demoTimers = [];
  const real = fire._real || fire;
  const tmp = new Fire(() => ({ warmth: 10, born: 1 }), () => {});
  tmp._real = real; fire = tmp; sendGauge();
  log('fire_demo');
  const at = (sec, f) => demoTimers.push(setTimeout(f, sec * 1000));
  const live = (type, data) => gauge && gauge.webContents.send('live', type, data);
  // そっと吹く（len 秒）／強く吹く（火の粉が散る）
  const blow = (sec, len, dP = 30) => {
    at(sec, () => live('exhale_start'));
    for (let k = 0.2; k < len; k += 0.3) at(sec + k, () => live('level', { dP }));
    at(sec + len, () => { live('exhale_end'); fireEvent('breath', { sec: dP >= STRONG_PA ? 3 : len * 2.5, source: 'device', peak: dP }); });
  };
  const view = (v) => { Object.assign(demoView, v); sendGauge(); };
  at(0, () => toast(['そろそろ 火、つけに いこ', '55分 つづけて 作業しています', '打ち直しが、ふだんの 1.4倍です'], { mood: 'sleepy', life: 7000 }));
  blow(4, 2); blow(6.5, 2); blow(9, 1.5, 95);
  at(12, () => { const r = fire.done({}); toast(['一服 おわり。', `ゆっくり 長い息が 〔${r.good}回〕`, '息が 2.1秒 → 〔5.8秒〕 に のびた', '火が 少し 大きく なりました', goalText()], { mood: 'blow', life: 7000 }); toastUp(r.up); sendGauge(); });
  // ふたりの一服（PERSONA の 15:00）：お誘い＝火を分ける → 2台で焚き火 → 話した愚痴が札のついた薪になって1本ずつ加わる → ふたりで吹くと、薪が火へ飛びこむ
  at(17, () => toast(['お誘いが とどいた。', '〔火を わけに〕 いこう'], { mood: 'blow', life: 5000 }));
  at(19.5, () => { fire.s.warmth = 352; view({ pair: true }); toast(['本体が 2台 そろった。', 'ふたりの火を よせて', '〔焚き火〕を かこもう'], { mood: 'blow', life: 5000 }); });
  at(23, () => { view({ wood: 1, labels: ['長いレビュー'] }); fire.wood(1); toast(['「長いレビュー」を', '〔薪〕に した'], { life: 4500 }); });
  at(25.5, () => { view({ wood: 2, labels: ['長いレビュー', '急な残業'] }); fire.wood(1); toast(['「急な残業」も 〔薪〕に した。', 'ふたりで 吸うと 燃えるよ'], { life: 5000 }); });
  blow(28.5, 5); at(29.2, () => view({ wood: 1, labels: ['急な残業'] })); at(31.4, () => view({ wood: 0, labels: [] })); // 札のついた薪が1本ずつ火へ飛んで、炎がぐっと大きくなる
  at(35, () => { const r = fire.done({ together: true }); toast(['一服 おわり。', 'もやもやの薪が 〔2本〕 燃えた', 'ふたりの火を よせて', '〔焚き火〕を かこんだ'], { mood: 'blow', life: 7000 }); toastUp(r.up); sendGauge(); });
  at(40, () => view({ pair: false }));
  // 次の休憩：焚き火になったあとの1本で、まわりに石の輪 → その先は1本ごとに、にぎやかになる（ためしでは先まで見せる）
  blow(41, 2);
  at(44, () => { const r = fire.done({}); toast(['一服 おわり。', itemLine(r.item), goalText()], { mood: 'blow', life: 6000 }); sendGauge(); });
  at(48, () => { fire.s.camp = 9; sendGauge(); toast(['1本ごとに、焚き火の まわりが', '〔にぎやかに〕 なっていくよ'], { mood: 'blow', life: 5000 }); });
  at(54, () => { fire = real; demoRunning = false; demoView = null; sendGauge(); });
}
// 席を離れている間は、右下の火の子の見た目を止めておき、戻って PC にさわったら、育った様子を見せる（11/08）
// - 止める姿：PC にさわっていた最後の時の姿（離れてから吹いた分は、まだ見せない）
// - 戻ったとき：育っていれば、右下で「前の姿 → 点滅 → 今の姿」の演出をして、「おかえり」の吹き出し
let fireFrozen = null, firePresent = null;
function fireWatch(idle) {
  if (!fire || !gameMode() || demoRunning) return;
  if (idle < 30 && !fireFrozen) { firePresent = { view: fire.view(), warmth: fire.s.warmth }; return; }
  if (idle >= 30) { if (!fireFrozen && firePresent) { fireFrozen = firePresent; sendGauge(); } return; }
  if (fireFrozen && idle < 2) {
    const before = fireFrozen; fireFrozen = null;
    if (fire.s.warmth > before.warmth && !trialWin) {
      const now = fire.view();
      if (gauge) gauge.webContents.send('grow', { from: before.view, to: now });
      const hi = now.stage > before.view.stage ? ['火が 少し 大きく なりました', `〔${now.name}〕に なったよ`]
        : now.camp > (before.view.camp || 0) ? ['焚き火のまわりが 少し にぎやかに なりました', itemLine(campName(now.camp))]
        : [now.next ? '火が 少し 大きく なりました' : '火が 少し あたたまりました'];
      if (!summary) awayToasts.unshift([hi, { mood: 'blow', life: 8000 }]); // まとめがあれば、育った知らせはまとめに入っている
      awayToasts = awayToasts.filter(([, o]) => !o || o.kind !== 'stage'); // 段が上がった知らせは、上の1つにまとめる
      summaryWaitBack = true; // 育つ演出（約1.6秒）を見せてから、まとめを出す
      setTimeout(() => { summaryWaitBack = false; flushAway(flushSummary('おかえり。')); }, 1600);
      log('fire_back', { from: before.view.stage, to: fire.view().stage, warm: fire.s.warmth - before.warmth });
    } else flushAway(flushSummary('おかえり。'));
    sendGauge();
  }
}
// 見せ方を切りかえる（操作パネル・通知領域のメニュー）
function setView(v) {
  settings.view = v === 'smoke' ? 'smoke' : 'game'; saveSettings();
  call(`setGame(${gameMode()})`);
  if (gauge) { const b = gauge.getBounds(); placeGauge(b.x + b.width - gW(), b.y + b.height - gH()); } // 右下の角を動かさずに大きさを変える
  if (!gameMode()) setVisible(true); else { if (notice) notice.hide(); setVisible(visible); }
  log('view', { view: settings.view });
  sendGauge(); sendPanelState();
}

// ---------------- 戻ってきたか・作業を始めたかを見る（PC を操作していない時間で判断する） ----------------
let away = false, endedAt = 0, prevIdle = 0, awayFrom = 0, signIdle = false;
setInterval(() => {
  if (!overlay) return;
  const idle = powerMonitor.getSystemIdleTime(); // 秒
  fireWatch(idle);
  // 11/13：曲が終わったあとに、マウスかキーボードにさわった（さわっていない時間 ＜ 曲が終わってからの時間）→ まとめを1つ出す
  if (summary && !summaryWaitBack && !fireFrozen && gameMode() && idle * 1000 < Date.now() - summary.doneAt - 1000) flushSummary();
  if (state.inSession && idle >= 30 && !trialWin) away = true; // 一服の間、PC から離れていた（休憩の実験の間はのぞく）
  // 席を離れた時間の記録（2分以上 PC をさわらなかったら「離れた」）
  if (rhythm) {
    if (!awayFrom && idle >= 120) awayFrom = Date.now() - idle * 1000;
    if (awayFrom && idle < 2) { log('away', { from: new Date(awayFrom).toISOString(), sec: Math.round((Date.now() - awayFrom) / 1000) }); awayFrom = 0; }
  }
  // 一服が終わったあとに、PC にさわった → 早送りを見せる（30分以内）
  if (away && !trialWin && !state.inSession && endedAt && idle < 2 && Date.now() - endedAt < 30 * 60 * 1000) {
    away = false; endedAt = 0;
    if (gameMode()) flushAway(flushSummary('おかえり。'));
    else { showTemp(); call('userBack()'); }
  }
  // 席の札：しばらく PC をさわらなかったあとに、さわった（戻ってきた）→ おろす
  if (state.sign) { if (idle >= 20) signIdle = true; if (signIdle && idle < 2) { signIdle = false; call("signOff('back')"); } }
  else signIdle = false;
  // 煙の上の言葉（もやもや）：席にいるときだけ見せる。札が出ている間・1分 PC をさわっていない間は、まわりの人が画面を見るので消す
  const present = !state.sign && idle < 60;
  const wantLabels = settings.labels === 'always' || (settings.labels === 'present' && present);
  if (state.labelsShown !== undefined && state.labelsShown !== wantLabels) call(`setLabelsShown(${wantLabels})`);
  // メッセージが出ているときに、作業を始めた（キーやマウスにさわった）→ 消す
  if (state.msg && idle < 1 && prevIdle >= 1) call('activity()');
  prevIdle = idle;
}, 1000);

app.whenReady().then(async () => {
  if (!gotLock) return;
  loadSettings();
  fire = new Fire(() => settings.fire, (s) => { settings.fire = s; saveSettings(); });
  const port = await startServer();
  try { rhythm = new Rhythm(logDir()); rhythm.start(); log('app_start'); }
  catch (err) { console.log('[shinkokyu] リズムの記録を始められなかった：' + err.message); rhythm = null; }
  loadExp();
  stt = new Stt(path.join(app.getPath('userData'), 'voice.json'));
  labeler = new Labeler(path.join(app.getPath('userData'), 'llm.json'));
  setTimeout(warmVoice, 5000); // 11/15：話す前に、文字にする係と短い言葉にする AI を読みこんでおく
  if (!globalShortcut.register(VOICE_KEY, () => { if (panel) panel.webContents.send('voice', 'toggle'); })) console.log(`[shinkokyu] ${VOICE_KEY_LABEL} は、ほかのアプリが使っていて登録できなかった`);
  if (!globalShortcut.register(TRIAL_KEY, () => openTrial('key'))) console.log(`[shinkokyu] ${TRIAL_KEY_LABEL} は、ほかのアプリが使っていて登録できなかった`);
  // 最初のアイコン（ページから届くまでの仮の絵：灰色の四角）
  const px = Buffer.alloc(16 * 16 * 4);
  for (let i = 0; i < 16 * 16; i++) px.set([0x74, 0x64, 0x5b, 0xff], i * 4); // BGRA
  tray = new Tray(nativeImage.createFromBitmap(px, { width: 16, height: 16 }));
  tray.setToolTip('シン呼吸');
  tray.on('click', togglePanel); // 押すと操作パネル
  tray.on('right-click', () => tray.popUpContextMenu(Menu.buildFromTemplate([
    { label: '操作パネルを開く', click: togglePanel },
    { label: settings.gauge ? '煙メーターを消す' : '煙メーターを出す', click: () => setGauge(!settings.gauge) },
    { label: '煙メーターを右下に戻す', enabled: !!settings.gaugePos, click: gaugeToHome },
    { label: '右下の火の子の大きさ', submenu: GAUGE_SIZES.map((g) => ({ label: g.label, type: 'radio', checked: Math.abs(g.scale - gaugeScale()) < 0.01, click: () => setGaugeSize(g.key) })) },
    { label: 'お知らせの大きさ', submenu: GAUGE_SIZES.map((g) => ({ label: g.label, type: 'radio', checked: Math.abs(g.scale - noticeScale()) < 0.01, click: () => setNoticeSize(g.key) })) },
    { label: settings.hrShow ? '心拍数の窓を消す' : '心拍数の窓を出す', click: () => setHrShow(!settings.hrShow) },
    { label: '心拍数の窓の大きさ', submenu: HR_SIZES.map((g) => ({ label: g.label, type: 'radio', checked: Math.abs(g.scale - hrScaleNow()) < 0.01, click: () => setHrSize(g.key) })) },
    { label: '一服のお誘いを試す（本体の ▶ の長押しと同じ）', click: () => invite('tray') },
    { label: '火の子のためし（約40秒・記録しない）', enabled: gameMode(), click: fireDemo },
    { label: `休憩の実験（約10分）  ${TRIAL_KEY_LABEL}`, click: () => openTrial('tray') },
    { label: `もやもやを話す（もう一度で終わり）  ${VOICE_KEY_LABEL}`, click: () => { if (panel) panel.webContents.send('voice', 'toggle'); } },
    { label: '休憩の実験をやめる（窓を強制的に閉じる）', enabled: !!trialWin, click: quitTrial },
    { type: 'separator' },
    { label: '終わる', click: () => app.quit() },
  ])));
  createPanel();
  createOverlay(port);
  createGauge();
  createRise(); // 11/12：火の粉が画面の上までのぼる窓（ふだんはかくしておく）
  createNotice();
  createHr(); // 11/14：心拍数の窓（ふだんはかくしておく）
  if (fire.isNew) setTimeout(() => { fire.born(); toast(['はじめまして。〔火種〕です', '本体から そっと 長く 吸うと', 'ぼくの 火が あたたまるよ']); }, 4000);
  handleArgs(process.argv);
});

// 2つ目の起動（デスクトップのショートカットなど）は、動いているアプリに引きつぐ
function handleArgs(argv) { if (argv.includes('--trial')) openTrial('shortcut', argv.includes('--quick')); }
app.on('second-instance', (_e, argv) => handleArgs(argv));

app.on('window-all-closed', () => app.quit());
app.on('will-quit', () => { globalShortcut.unregisterAll(); if (stt) stt.stop(); if (labeler) labeler.stop(); if (rhythm) { log('app_quit'); rhythm.stop(); } });
