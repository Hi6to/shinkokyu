// 本体（Shinkokyu-XXXX）と Chrome の Web Bluetooth でつながり、本体が送る1行ずつの文字を読む（S01）
// 本体の送る行（firmware/shinkokyu/shinkokyu.ino の先頭の説明と同じ）
//   S dP=12.3 st=E ph=1 n=4 wait=0 mode=flute vol=5 song=amazing_grace   … 1秒に10回（song は 11/12 から）
//   START exhale / END exhale 3.2s peak=41.3 / RESET baseline / SONG done / MODE flute / VOLUME 5
//   NOTE 74（鳴らし始めた音の MIDI の番号。0 は止めた）/ HELLO Shinkokyu-XXXX song=.. mode=.. vol=.. / SONG reset / SONG restart 曲の名前（SW1 で曲を替えた）
//   INVITE（曲送りボタンの長押し＝一服のお誘い）
//   TALK（音量＋と−の同時押し＝声を録る。録っていなければ始め、録っていれば終える。11/11）
// PC から本体へ送る行：RESTART（曲を最初に戻す）／VOL 0〜10（音量。0 は音なし）／LIGHT n（n 秒、紫に点滅）
//
// 使い方：
//   const dev = new ShinkokyuDevice();
//   dev.addEventListener('status', e => console.log(e.detail));
//   await dev.connect();   // ボタンを押したときに呼ぶ（Chrome の決まり）

export const NUS_SERVICE = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
const NUS_RX = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'; // PC → 本体
const NUS_TX = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'; // 本体 → PC

export function bluetoothAvailable() {
  return typeof navigator !== 'undefined' && !!navigator.bluetooth;
}

// 11/15：いまつないでいる本体（Bluetooth の id → その本体の ShinkokyuDevice）。同じ本体を2つ分つながないための控え
//   11/14 深夜：アプリの起動直後に同じ本体（CE40）が2つ分つながり、本体の＋−同時押し（TALK）が2回届いた。
//   録音が始まった直後に止まって、声の基板から「おわり」が届かず、文字にならなかった（記録の voice_cancel noend）
const live = new Map();

export class ShinkokyuDevice extends EventTarget {
  constructor() {
    super();
    this.device = null;
    this.rx = null;
    this.buf = '';
    this.decoder = new TextDecoder();
    this.name = '';
    this.status = null;
  }

  // isDup：選んだ本体が、もうつないでいる本体と同じなら true を返す関数（11/13：同じ本体を2つ分つながないように。そのときは開かずにやめる）
  async connect(isDup) {
    const picked = await navigator.bluetooth.requestDevice({
      filters: [{ services: [NUS_SERVICE] }, { namePrefix: 'Shinkokyu' }],
      optionalServices: [NUS_SERVICE],
    });
    if (isDup && isDup(picked)) { const e = new Error('この本体は、もうつながっている'); e.dup = true; e.name0 = picked.name || ''; throw e; }
    this.device = picked;
    this.name = this.device.name || '';
    this.device.addEventListener('gattserverdisconnected', () => this.#emit('disconnect', { name: this.name }));
    await this.#open();
  }

  // 切れたあと、同じ本体につなぎ直す（選び直さなくてよい）
  async reconnect() {
    if (!this.device) throw new Error('まだ本体を選んでいない');
    await this.#open();
  }

  async #open() {
    const server = await this.device.gatt.connect();
    // 11/15：同じ本体を、別の ShinkokyuDevice がもうつないでいたら、こちらはやめる（Bluetooth はそのまま。切るともう一方も切れる）
    const other = live.get(this.device.id);
    if (other && other !== this && !other.closed) { const e = new Error('この本体は、もうつながっている'); e.dup = true; e.name0 = this.name; this.closed = true; throw e; }
    live.set(this.device.id, this);
    const service = await server.getPrimaryService(NUS_SERVICE);
    const tx = await service.getCharacteristic(NUS_TX);
    this.rx = await service.getCharacteristic(NUS_RX);
    this.buf = '';
    // 11/15：つなぎ直すたびに受けとる口を足していたので、つなぎ直したあとは1行が2回（3回…）届いていた。前の口は外してから付ける
    if (this.tx && this.onTx) this.tx.removeEventListener('characteristicvaluechanged', this.onTx);
    this.tx = tx; this.onTx = (e) => this.#onData(e.target.value);
    tx.addEventListener('characteristicvaluechanged', this.onTx);
    await tx.startNotifications();
    this.#emit('connect', { name: this.name });
  }

  disconnect() {
    // 11/15：自分で切った（操作パネルの「切る」）ときは控えから外す。次に手でつなぐときに、2つ目扱いされないように
    if (this.device && live.get(this.device.id) === this) live.delete(this.device.id);
    if (this.tx && this.onTx) { this.tx.removeEventListener('characteristicvaluechanged', this.onTx); this.onTx = null; } // 切った台からは、もう受けとらない
    if (this.device && this.device.gatt.connected) this.device.gatt.disconnect();
  }

  get connected() {
    return !!(this.device && this.device.gatt.connected);
  }

  // 本体の曲を最初に戻す（煙の画面で「いっぱいにする」を押したときなど）
  async restart() {
    await this.send('RESTART');
  }

  // 本体の音量を変える（0〜10。0 は音なし）（11/12：最大 8 → 10）
  async setVolume(v) {
    await this.send(`VOL ${Math.max(0, Math.min(10, Math.round(v)))}`);
  }

  // 本体の LED を n 秒、紫に点滅させる（一服のお誘いが届いたしるし）
  async light(sec) {
    await this.send(`LIGHT ${Math.max(0, Math.min(60, Math.round(sec)))}`);
  }

  // 本体に1行送る
  async send(line) {
    if (!this.rx) return;
    await this.rx.writeValue(new TextEncoder().encode(line + '\n'));
  }

  #onData(dataView) {
    this.feed(this.decoder.decode(dataView, { stream: true }));
  }

  // 届いた文字を入れる（本体なしで試すときにも使う。行の終わりに改行を付けて渡す）
  feed(text) {
    this.buf += text;
    let i;
    while ((i = this.buf.indexOf('\n')) >= 0) {
      const line = this.buf.slice(0, i).trim();
      this.buf = this.buf.slice(i + 1);
      if (line) this.#parse(line);
    }
  }

  #parse(line) {
    this.#emit('line', { line });
    const [head, ...rest] = line.split(' ');
    const kv = {};
    for (const t of rest) {
      const j = t.indexOf('=');
      if (j > 0) kv[t.slice(0, j)] = t.slice(j + 1);
    }
    switch (head) {
      case 'S':
        this.status = {
          dP: parseFloat(kv.dP),
          state: kv.st === 'E' ? 'exhale' : kv.st === 'I' ? 'inhale' : 'idle',
          phrase: parseInt(kv.ph, 10),
          note: parseInt(kv.n, 10),
          waiting: kv.wait === '1',
          mode: kv.mode,
          volume: parseInt(kv.vol, 10),
          song: kv.song, // 11/12：今の曲（前の本体のプログラムでは来ない）
        };
        this.#emit('status', this.status);
        break;
      case 'START':
        this.#emit('breathstart', { kind: rest[0] });
        break;
      case 'END':
        this.#emit('breathend', { kind: rest[0], seconds: parseFloat(rest[1]), peak: parseFloat(kv.peak) });
        break;
      case 'NOTE':
        this.#emit('note', { midi: parseInt(rest[0], 10) });
        break;
      case 'SONG':
        if (rest[0] === 'done') this.#emit('songdone', {});
        else if (rest[0] === 'restart' && rest[1]) this.#emit('songchange', { song: rest[1] }); // 11/12：SW1 で曲を替えた（次の曲の名前）
        break;
      case 'HELLO':
        this.#emit('hello', { name: rest[0], song: kv.song, mode: kv.mode, volume: parseInt(kv.vol, 10) });
        break;
      case 'RESET':
        this.#emit('reset', {});
        break;
      case 'INVITE':
        this.#emit('invite', {});
        break;
      case 'TALK':
        this.#emit('talk', {});
        break;
      case 'SENSOR': // 11/12 夜：本体の気圧センサーが見つからない（ng）・また見つかった（ok）
        this.#emit('sensor', { ok: rest[0] === 'ok' });
        break;
    }
  }

  #emit(type, detail) {
    if (this.closed) return; // 11/15：やめた（2つ目だった）ものからは、何も知らせない
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }
}
