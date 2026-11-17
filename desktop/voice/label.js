// 話した愚痴の文から、煙のラベル（2〜6文字の短い言葉）を作る係
// - ふだんは PC の中の Ollama＋Sarashina2.2 3B（ネットがなくても動く。愚痴が PC の外に出ない）
// - 設定ファイル（%APPDATA%\shinkokyu-desktop\llm.json）で、大学の LLM など OpenAI と同じ形のものに切りかえられる
//     { "api": "openai", "baseUrl": "https://llm.example.ac.jp/v1", "model": "モデルの名前", "apiKey": "…" }
//   API キーはこのファイルにだけ書く（GitHub には上げない）
// - AI が使えないときは、言いよどみを取って先頭を切り出すだけの、簡単なやり方にする
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const DEFAULT = {
  api: 'ollama',
  baseUrl: 'http://127.0.0.1:11434',
  model: 'hf.co/mmnga/sarashina2.2-3b-instruct-v0.1-gguf:Q4_K_M',
  // Ollama がまだ動いていなければ、ここから起動する（Hi6to の PC の置き場所）
  ollamaExe: path.join(process.env.USERPROFILE || '', 'apps', 'ollama', 'bin', 'ollama.exe'),
  ollamaModels: path.join(process.env.USERPROFILE || '', 'apps', 'ollama', 'models'),
  timeoutMs: 15000,
  keepAlive: '3h', // 11/15：前は15分で AI が下ろされ、しばらく話さないと次の1回目が遅かった
};

const SYSTEM = [
  'あなたは、職場の愚痴や、体の不調・気分のもやもやを聞いて、短い言葉（ラベル）にする係です。',
  '話の中の「もやもやのもと」を、日本語の2〜6文字の言葉にしてください。いくつもあれば、3つまで「、」で区切って答えてください。',
  '説明・記号・かぎかっこは付けず、言葉だけを出してください。人の名前・役職（部長・上司など）や、悪口・差別的な言葉は入れず、「できごと」を言葉にしてください。',
  '聞きまちがいで文がくずれていて、何の話か分からないときは「なし」とだけ答えてください。',
].join('\n');
const SHOTS = [
  ['今日また急に残業頼まれてさ、ほんと疲れた', '急な残業'],
  ['会議が長すぎて何も決まらなかった', '長い会議'],
  ['上司のチャットの返事が来ないし、資料もまた直しって言われた', '返事待ち、資料の直し'],
  ['最近ずっと目が疲れてて、首も痛いし、なんか眠い', '目の疲れ、首の痛み、眠気'],
  ['課長がまた仕様を変えてきて、手戻りばっかりでしんどい', '仕様変更、手戻り'],
  ['最期、カタゴイが一番良くなって、関係して、もう少し作ら', 'なし'],
];
const MAX_LABELS = 3;
const FILLERS = /(えっと|えーと|えー|あのー?|そのー?|なんか|まあ|うーん|ほんと(に)?|もう|ね|さ|よ)(?=[、。\s]|$)/g;

// 文字の幅：全角は1、半角は0.5（「Wi-Fi遅い」が収まるように）
const width = (s) => [...s].reduce((w, c) => w + (/[\x20-\x7e]/.test(c) ? 0.5 : 1), 0);
function fit(s, max = 6) {
  let out = '';
  for (const c of s) { if (width(out + c) > max) break; out += c; }
  return out;
}
function cleanRaw(s) {
  const m = String(s || '').match(/^([^（(]*)[（(]([^）)]*)[）)]?/); // かっこ入り：ふつうはかっこの前、前が短すぎるときだけ中
  if (m) s = width(m[1].trim()) >= 2 ? m[1] : m[2];
  s = String(s || '').replace(/<think>[\s\S]*?<\/think>/g, '').replace(/<\/s>/g, '').trim().split(/\r?\n/)[0] || '';
  return s.replace(/^(ラベル|答え)[:：]\s*/, '').replace(/[「」『』"'。、.!！?？\s]/g, '');
}
function clean(s) { return fit(cleanRaw(s)); }
// 話の中身ではない言葉（聞きとりが崩れたとき、AI が「話の内容が…」「要点を…」のように答えてしまう）と、
// それだけでは何のことか分からない言葉。これらは煙にしない
const META = /^なし$|(話の内容|内容|要点|まとめ|説明|ラベル|分からない|わからない|不明|聞き取れ|すみません|申し訳|話者|文脈|推測|長くな|長いので|途中で|最初の)/;
const VAGUE = /^(多さ|少なさ|遅さ|速さ|大変|つらさ|辛さ|しんどさ|問題|こと|もの|変化|規則)$/;
// 話に出てきた言葉か：ラベルの漢字かカタカナが1字でも話の文の中にあるか（ひらがなだけのラベルは、そのまま文の中にあるか）
// 聞きとりが崩れると、AI が「正確に把握できません」のような、話にない言葉を返すため（11/07）
function grounded(label, text) {
  const keys = [...label].filter((c) => /[一-鿿゠-ヿ]/.test(c) && c !== 'ー');
  return keys.length ? keys.some((c) => text.includes(c)) : text.includes(label);
}
// 役職の言葉（煙のラベルには出さない）
const ROLE = /(部長|課長|係長|主任|上司|社長|専務|常務|先輩|後輩|店長|先生|リーダー|マネージャー|ボス)/;
function stripRole(s) { const t = s.replace(new RegExp(ROLE.source + '(の|が|から)?', 'g'), ''); return width(t) >= 2 ? t : ''; }
// 長すぎるとき：「部長の仕様変更」→「仕様変更」のように、前の「〇〇の」を外す（人の役職も煙に出なくなる）
function dropPrefix(s) {
  const i = s.lastIndexOf('の');
  const rest = i >= 0 ? s.slice(i + 1) : '';
  return width(rest) >= 2 && width(rest) <= 6 ? rest : '';
}
// AI が使えないときの、簡単なやり方
function simpleLabel(text) {
  const s = String(text || '').replace(FILLERS, '').replace(/[「」『』"'。、.!！?？\s]/g, '');
  return fit(s);
}

class Labeler {
  constructor(configPath) {
    this.configPath = configPath;
    this.ollama = null; // 自分で起動した Ollama（アプリを終わるときに止める）
  }
  config() {
    let c = {};
    try { c = JSON.parse(fs.readFileSync(this.configPath, 'utf8')); } catch {}
    return { ...DEFAULT, ...c };
  }
  async reachable(c) {
    try {
      const r = await fetch(c.api === 'ollama' ? `${c.baseUrl}/api/version` : `${c.baseUrl}/models`, { headers: this.headers(c), signal: AbortSignal.timeout(1500) });
      return r.ok;
    } catch { return false; }
  }
  headers(c) { return { 'Content-Type': 'application/json', ...(c.apiKey ? { Authorization: `Bearer ${c.apiKey}` } : {}) }; }
  // Ollama が動いていなければ起動する（PC の中だけで聞く。ネットからは呼べない）
  async ensureOllama(c) {
    if (c.api !== 'ollama' || await this.reachable(c)) return true;
    if (!fs.existsSync(c.ollamaExe)) return false;
    if (!this.ollama) {
      this.ollama = spawn(c.ollamaExe, ['serve'], { env: { ...process.env, OLLAMA_MODELS: c.ollamaModels, OLLAMA_HOST: '127.0.0.1:11434' }, stdio: 'ignore', windowsHide: true });
      this.ollama.on('exit', () => { this.ollama = null; });
    }
    for (let i = 0; i < 40; i++) { await new Promise((r) => setTimeout(r, 250)); if (await this.reachable(c)) return true; }
    return false;
  }
  // 話し始めたときに呼ぶ：モデルを先に読みこんでおく（話し終わってから待たないように）
  async warm() {
    const c = this.config();
    if (!(await this.ensureOllama(c))) return;
    if (c.api === 'ollama') fetch(`${c.baseUrl}/api/generate`, { method: 'POST', headers: this.headers(c), body: JSON.stringify({ model: c.model, keep_alive: c.keepAlive }) }).catch(() => {});
  }
  async chat(c, messages) {
    if (c.api === 'ollama') {
      const r = await fetch(`${c.baseUrl}/api/chat`, {
        method: 'POST', headers: this.headers(c), signal: AbortSignal.timeout(c.timeoutMs),
        body: JSON.stringify({ model: c.model, messages, stream: false, keep_alive: c.keepAlive, options: { temperature: 0.2, num_predict: 40, stop: ['</s>', '\n'] } }),
      });
      return (await r.json()).message?.content;
    }
    // OpenAI と同じ形（大学の LLM など）
    const r = await fetch(`${c.baseUrl}/chat/completions`, {
      method: 'POST', headers: this.headers(c), signal: AbortSignal.timeout(c.timeoutMs),
      body: JSON.stringify({ model: c.model, messages, temperature: 0.2, max_tokens: 40, stop: ['\n'] }),
    });
    return (await r.json()).choices?.[0]?.message?.content;
  }
  async label(text) {
    const c = this.config();
    const messages = [{ role: 'system', content: SYSTEM }];
    for (const [q, a] of SHOTS) messages.push({ role: 'user', content: q }, { role: 'assistant', content: a });
    messages.push({ role: 'user', content: text });
    const t0 = Date.now();
    try {
      if (!(await this.ensureOllama(c))) throw new Error('つなぎ先の AI が動いていない');
      const line = String(await this.chat(c, messages) || '').replace(/<\/s>/g, '').trim().split(/\r?\n/)[0] || '';
      // 「、」で区切られた言葉（3つまで）を、1つずつ整える：長すぎれば前の「〇〇の」を外すか切る、役職の言葉は外す
      const labels = []; let dropped = 0;
      for (const part of line.split(/[、,，・/]/)) {
        let l = cleanRaw(part);
        if (width(l) < 1) continue;
        // 長すぎるとき：「部長の仕様変更」→ 後ろの「仕様変更」。後ろがぼんやりした言葉なら（「仕様変更の多さ」→「多さ」）前の「仕様変更」
        if (width(l) > 6) { const tail = dropPrefix(l), head = l.slice(0, l.indexOf('の')); l = tail && !VAGUE.test(tail) ? tail : (l.includes('の') && width(head) >= 2 && width(head) <= 6 ? head : fit(l)); }
        if (ROLE.test(l)) l = stripRole(l);
        if (META.test(l) || VAGUE.test(l) || !grounded(l, text)) { dropped++; continue; }
        if (width(l) >= 2 && !labels.includes(l)) labels.push(l);
        if (labels.length >= MAX_LABELS) break;
      }
      // AI は答えたが、中身のある言葉がなかった：聞きとりが崩れていたとみて、煙にしない（文をそのまま煙にもしない）
      if (!labels.length && dropped) return { labels: [], label: '', by: c.api === 'ollama' ? 'local' : 'remote', ms: Date.now() - t0, error: '話の中身を言葉にできなかった' };
      if (!labels.length) throw new Error('言葉が返ってこなかった');
      return { labels, label: labels[0], by: c.api === 'ollama' ? 'local' : 'remote', ms: Date.now() - t0 };
    } catch (err) {
      const l = simpleLabel(text);
      return { labels: l ? [l] : [], label: l, by: 'simple', ms: Date.now() - t0, error: err.message };
    }
  }
  stop() { if (this.ollama) { try { this.ollama.kill(); } catch {} this.ollama = null; } }
}

module.exports = { Labeler, clean, simpleLabel, fit, width, dropPrefix };
