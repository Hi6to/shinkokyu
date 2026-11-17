// 作業のリズムを数える（キーボードとマウス）
// - どの文字を打ったか・どのキーを押したかは記録しない。「消すキー（Backspace・Delete）かどうか」だけを数える
// - 1分ごとにまとめて、PC の中のファイル（日付ごと）に1行ずつ書く。外には送らない
const fs = require('fs');
const path = require('path');
const { uIOhook, UiohookKey } = require('uiohook-napi');

class Rhythm {
  constructor(logDir) {
    this.logDir = logDir;
    fs.mkdirSync(logDir, { recursive: true });
    this.reset();
    this.lastInput = 0;
    this.lastKeyAt = 0;
    this.lastKeyCode = -1;
    this.seg = null; // マウスの1回の動き（止まるまで）
    this.latest = null; // 直近1分のまとめ（操作パネルに出す）
    this.paused = false; // 反応テストの間は数えない（テストのキーが作業のリズムに混ざらないように）
    this.rows = [];        // 過去7日の1分ごとのまとめ（休みどきの理由に使う。tMs はその1分の終わりの時刻）
    this.lastSessionEnd = 0; // 最後に一服が終わった時刻
    this.loadHistory();
  }

  // 過去7日の記録を読む（アプリを起動し直しても、ふだんの値とつづけて作業した時間が分かるように）
  loadHistory(days = 7) {
    const now = Date.now();
    for (let d = days - 1; d >= 0; d--) {
      const day = new Date(now - d * 86400000).toLocaleDateString('sv-SE');
      let text = '';
      try { text = fs.readFileSync(path.join(this.logDir, `${day}.jsonl`), 'utf8'); } catch { continue; }
      for (const line of text.split('\n')) {
        if (!line) continue;
        let o; try { o = JSON.parse(line); } catch { continue; }
        const tMs = Date.parse(o.t);
        if (o.type === 'rhythm') this.rows.push({ ...o, tMs });
        else if (o.type === 'session_end') this.lastSessionEnd = Math.max(this.lastSessionEnd, tMs);
      }
    }
    this.rows.sort((a, b) => a.tMs - b.tMs);
  }

  // 休憩の実験の間は、キーボードとマウスを見る仕組みごと止める（反応テストのキーの届き方に影響しないように）
  pause() {
    if (this.paused) return;
    this.paused = true; this.w.testing = true;
    if (this.hooked) { try { uIOhook.stop(); } catch {} this.hooked = false; }
  }
  resume() {
    if (!this.paused) return;
    this.paused = false; this.lastInput = 0; this.lastKeyAt = 0; this.seg = null; // 止めていた間を「手が止まった」と数えない
    if (!this.hooked) { try { uIOhook.start(); this.hooked = true; } catch {} }
  }

  reset() {
    this.w = { keys: 0, corr: 0, iki: [], pauses: 0, longPauses: 0, mouseDist: 0, clicks: 0, eff: [], activeSec: new Set(), testing: this.paused };
  }

  // 操作があったとき：手が止まっていた時間を数える
  input(now) {
    if (this.lastInput) {
      const gap = now - this.lastInput;
      if (gap >= 2000 && gap < 30000) this.w.pauses++; // 小さな止まり（ぼんやり）
      else if (gap >= 30000) this.w.longPauses++;
    }
    this.lastInput = now;
    this.w.activeSec.add(Math.floor(now / 1000));
  }

  key(e) {
    if (this.paused) return;
    const now = Date.now();
    // キーを押しっぱなしの連続入力は数えない（キーの番号はこの判定にだけ使い、記録しない）
    if (e.keycode === this.lastKeyCode && now - this.lastKeyAt < 40) { this.lastKeyAt = now; return; }
    this.input(now);
    if (this.lastKeyAt && now - this.lastKeyAt < 2000) this.w.iki.push(now - this.lastKeyAt);
    this.lastKeyAt = now;
    this.lastKeyCode = e.keycode;
    this.w.keys++;
    if (e.keycode === UiohookKey.Backspace || e.keycode === UiohookKey.Delete) this.w.corr++;
  }

  move(e) {
    if (this.paused) return;
    const now = Date.now();
    // 300ms 以上止まったら、そこで1回の動きを区切る（まっすぐさ＝始点から終点の距離 ÷ 動いた道のり）
    if (!this.seg || now - this.seg.t > 300) {
      this.closeSeg();
      this.seg = { x0: e.x, y0: e.y, x: e.x, y: e.y, len: 0, t: now };
      this.input(now);
      return;
    }
    const d = Math.hypot(e.x - this.seg.x, e.y - this.seg.y);
    this.seg.len += d; this.seg.x = e.x; this.seg.y = e.y; this.seg.t = now;
    this.w.mouseDist += d;
    if (now - this.lastInput > 1000) this.input(now);
  }

  closeSeg() {
    const s = this.seg;
    if (s && s.len > 80) this.w.eff.push(Math.hypot(s.x - s.x0, s.y - s.y0) / s.len);
    this.seg = null;
  }

  click() { if (this.paused) return; this.input(Date.now()); this.w.clicks++; }

  // 1分ごとのまとめ
  flush() {
    this.closeSeg();
    const w = this.w;
    const iki = [...w.iki].sort((a, b) => a - b);
    const mean = iki.length ? iki.reduce((s, x) => s + x, 0) / iki.length : 0;
    const sd = iki.length > 1 ? Math.sqrt(iki.reduce((s, x) => s + (x - mean) ** 2, 0) / (iki.length - 1)) : 0;
    const row = {
      type: 'rhythm',
      t: new Date().toISOString(),
      keys: w.keys,                                         // キーを押した回数
      corr: w.corr,                                         // 消すキーの回数
      corrRate: w.keys ? +(w.corr / w.keys).toFixed(3) : null, // 打ち直しの割合
      ikiMed: iki.length ? iki[Math.floor(iki.length / 2)] : null, // 打つ間隔（ふつう、ms）
      ikiCv: mean ? +(sd / mean).toFixed(3) : null,         // 打つ間隔のばらつき
      pauses: w.pauses,                                     // 2〜30秒の小さな止まり
      longPauses: w.longPauses,                             // 30秒以上の止まり
      mouseDist: Math.round(w.mouseDist),                   // マウスの動いた量（px）
      mouseEff: w.eff.length ? +(w.eff.reduce((s, x) => s + x, 0) / w.eff.length).toFixed(3) : null, // まっすぐさ（1に近いほど迷いがない）
      clicks: w.clicks,
      activeSec: w.activeSec.size,                          // 操作のあった秒数
      testing: w.testing || undefined,                      // この1分に反応テストをしていた（その分は数えていない）
    };
    this.latest = row;
    this.write(row);
    this.rows.push({ ...row, tMs: Date.now() });
    while (this.rows.length && this.rows[0].tMs < Date.now() - 7 * 86400000) this.rows.shift();
    this.reset();
  }

  write(obj) {
    const day = new Date().toLocaleDateString('sv-SE'); // 2026-11-06 の形
    try { fs.appendFileSync(path.join(this.logDir, `${day}.jsonl`), JSON.stringify(obj) + '\n'); } catch {} // 書いた順に並ぶように、1行ずつ書く
  }

  event(type, data = {}) { this.write({ type, t: new Date().toISOString(), ...data }); }

  start() {
    uIOhook.on('keydown', (e) => this.key(e));
    uIOhook.on('mousemove', (e) => this.move(e));
    uIOhook.on('mousedown', () => this.click());
    uIOhook.on('wheel', () => { if (!this.paused) this.input(Date.now()); });
    uIOhook.start(); this.hooked = true;
    this.timer = setInterval(() => this.flush(), 60 * 1000);
  }

  stop() {
    clearInterval(this.timer);
    if (this.hooked) { try { uIOhook.stop(); } catch {} this.hooked = false; }
    this.flush();
  }
}

module.exports = { Rhythm };
