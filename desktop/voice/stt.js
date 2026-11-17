// 声を文字にする係（stt_worker.py）を動かしたままにして、WAV を渡すと文字が返ってくるようにする
// - Whisper 用の Python は、ふだんは %USERPROFILE%\venvs\shinkokyu-voice（firmware/README.md の「声を文字にする」で作ったもの）
// - 設定ファイル（%APPDATA%\shinkokyu-desktop\voice.json）で変えられる：{ "python": "…\\python.exe", "model": "small", "denoise": true, "beam": 1, "hotwords": "…" }
//   ふつうは small＋雑音を消す（11/07 の比べで、base は「肩こり」が「片こり」になるなど崩れた。small は10秒の声を約4秒）
//   hotwords：よく出る言葉のヒント。"hotwords": false で使わない
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

// Whisper が、無音や雑音から作ってしまいがちな文（動画の字幕で覚えたもの）
const HALLUCINATION = /^((ご視聴|ご清聴)?ありがとうございました[。！!]?|.*チャンネル登録.*|.*(字幕|翻訳)(は|：|:).*|おやすみなさい[。]?|はい[。]?)$/;

// よく出る愚痴の言葉。Whisper に「この言葉が出やすい」と教える（「仕様変更」が「使用変更」になる、などを防ぐ）
const HOTWORDS = '仕様変更 残業 締め切り 会議 上司 部長 肩こり 腰痛 頭痛 目の疲れ 寝不足 手足の冷え';

class Stt {
  constructor(configPath) {
    this.configPath = configPath;
    this.proc = null; this.ready = null; this.pending = new Map(); this.nextId = 1; this.buf = '';
  }
  config() {
    let c = {};
    try { c = JSON.parse(fs.readFileSync(this.configPath, 'utf8')); } catch {}
    return { python: path.join(process.env.USERPROFILE || '', 'venvs', 'shinkokyu-voice', 'Scripts', 'python.exe'), model: 'small', denoise: true, beam: 1, hotwords: HOTWORDS, ...c };
  }
  available() { return fs.existsSync(this.config().python); }
  // 動いていなければ起動する（モデルの読みこみに数秒かかるので、話し始めたときに呼ぶ）
  start() {
    if (this.ready) return this.ready;
    const c = this.config();
    if (!fs.existsSync(c.python)) return Promise.reject(new Error('Whisper 用の Python が見つからない'));
    this.proc = spawn(c.python, ['-u', path.join(__dirname, 'stt_worker.py'), '--model', c.model, '--beam', String(c.beam), ...(c.threads ? ['--threads', String(c.threads)] : [])], { env: { ...process.env, PYTHONIOENCODING: 'utf-8', HF_HUB_DISABLE_SYMLINKS_WARNING: '1' }, windowsHide: true });
    this.ready = new Promise((resolve, reject) => {
      this.onReady = resolve;
      this.proc.on('error', (e) => { reject(e); this.reset(); });
      this.proc.on('exit', () => { reject(new Error('Whisper の係が止まった')); this.reset(); });
    });
    this.ready.catch(() => {});
    this.proc.stdout.setEncoding('utf8');
    this.proc.stdout.on('data', (d) => {
      this.buf += d;
      let i;
      while ((i = this.buf.indexOf('\n')) >= 0) {
        const line = this.buf.slice(0, i).trim(); this.buf = this.buf.slice(i + 1);
        if (!line) continue;
        let o; try { o = JSON.parse(line); } catch { continue; }
        if (o.ready) { this.info = o; this.onReady(o); continue; }
        const p = this.pending.get(o.id);
        if (p) {
          this.pending.delete(o.id);
          if (o.text && HALLUCINATION.test(o.text.trim())) o.text = ''; // 無音から作られがちな文は、聞きとれなかった扱い
          o.error ? p.reject(new Error(o.error)) : p.resolve(o);
        }
      }
    });
    this.proc.stderr.on('data', () => {}); // 進み具合の表示などは読み捨てる
    return this.ready;
  }
  reset() {
    for (const p of this.pending.values()) p.reject(new Error('Whisper の係が止まった'));
    this.pending.clear(); this.proc = null; this.ready = null; this.buf = '';
  }
  // opts：{ model: 'small', denoise: true, hotwords: false }（なければ設定どおり）
  async transcribe(wavPath, opts = {}) {
    await this.start();
    const id = this.nextId++;
    const c = this.config();
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.proc.stdin.write(JSON.stringify({ id, wav: wavPath, model: opts.model, denoise: opts.denoise ?? !!c.denoise, hotwords: (opts.hotwords ?? true) && c.hotwords ? String(c.hotwords) : '', ...(opts.vad === false ? { vad: false } : {}) }) + '\n');
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); reject(new Error('文字にするのに時間がかかりすぎた')); } }, 60000);
    });
  }
  // 11/15：アプリを起動したら、先にモデルを読みこみ、1秒の声を一度文字にして慣らしておく。
  //   前は話し始めてから読みこんでいて、短い AI の読みこみと重なり、起動直後の1回目は6.7秒の声に24秒かかった
  async warm(tmpDir) {
    const t0 = Date.now();
    await this.start();
    const n = 16000, buf = Buffer.alloc(44 + n * 2);
    buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 2, 4); buf.write('WAVE', 8); buf.write('fmt ', 12);
    buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22); buf.writeUInt32LE(16000, 24); buf.writeUInt32LE(32000, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34);
    buf.write('data', 36); buf.writeUInt32LE(n * 2, 40);
    for (let i = 0; i < n; i++) buf.writeInt16LE(Math.round(800 * Math.sin(i / 8) * Math.sin(i / 3000)), 44 + i * 2); // 小さな音（無音だと途中を飛ばすので）
    const wav = path.join(tmpDir, `shinkokyu-warm-${Date.now()}.wav`);
    fs.writeFileSync(wav, buf);
    try { await this.transcribe(wav, { vad: false }); } finally { fs.unlink(wav, () => {}); }
    return { ms: Date.now() - t0, threads: this.info && this.info.threads };
  }
  stop() { if (this.proc) { try { this.proc.kill(); } catch {} } this.reset(); }
}

module.exports = { Stt };
