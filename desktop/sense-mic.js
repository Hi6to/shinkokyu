// Sense 版のマイク（ShinkokyuMic-XXXX）と Bluetooth でつながり、届いた声を元にもどす（V02）
// 送られてくる形は firmware/sense_mic/sense_mic.ino の先頭に書いてある（A5 5A・種類・長さ・中身）
// 使い方：const mic = new SenseMic(); await mic.connect(); mic.rec(true) … mic.rec(false)
//   'start'（{ by }：0＝PC から・1＝基板のボタン）、'end'（{ samples: Float32Array, rate, reason, dropped, lost }）、'connect'、'disconnect'
(function () {
  const NUS = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
  const NUS_RX = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'; // PC → 基板
  const NUS_TX = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'; // 基板 → PC
  const STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767];
  const INDEX = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8];
  const BLOCK = 400;

  // IMA ADPCM の 4bit を、元の声（-1〜1）にもどす。pred と idx はそのまとまりの頭の値（基板が一緒に送ってくる）
  function decodeBlock(bytes, pred, idx, n) {
    const out = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const code = (i & 1) ? bytes[i >> 1] >> 4 : bytes[i >> 1] & 15;
      const step = STEP[idx];
      let d = step >> 3;
      if (code & 4) d += step;
      if (code & 2) d += step >> 1;
      if (code & 1) d += step >> 2;
      pred += (code & 8) ? -d : d;
      if (pred > 32767) pred = 32767; else if (pred < -32768) pred = -32768;
      idx += INDEX[code];
      if (idx < 0) idx = 0; else if (idx > 88) idx = 88;
      out[i] = pred / 32768;
    }
    return out;
  }

  class SenseMic extends EventTarget {
    constructor() { super(); this.device = null; this.buf = new Uint8Array(0); this.take = null; this.reconnecting = false; this.q = Promise.resolve(); this.lastFrameAt = 0; }
    get connected() { return !!(this.device && this.device.gatt.connected && this.rx); }
    get name() { return this.device ? this.device.name : ''; }
    emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }

    async connect() {
      this.device = await navigator.bluetooth.requestDevice({ filters: [{ namePrefix: 'ShinkokyuMic' }], optionalServices: [NUS] });
      this.device.addEventListener('gattserverdisconnected', () => { this.rx = null; this.emit('disconnect'); this.reconnect(); });
      await this.open();
    }
    async open() {
      const server = await this.device.gatt.connect();
      const svc = await server.getPrimaryService(NUS);
      this.rx = await svc.getCharacteristic(NUS_RX);
      const tx = await svc.getCharacteristic(NUS_TX);
      // 11/15：つなぎ直すたびに受けとる口を足していたので、つなぎ直したあとは同じ声が2回ずつ入り、声がこわれていた。前の口は外してから付ける
      if (this.tx && this.onTx) this.tx.removeEventListener('characteristicvaluechanged', this.onTx);
      this.tx = tx; this.onTx = (e) => { const v = e.target.value; this.feed(new Uint8Array(v.buffer, v.byteOffset, v.byteLength)); };
      this.buf = new Uint8Array(0);
      await tx.startNotifications();
      tx.addEventListener('characteristicvaluechanged', this.onTx);
      this.emit('connect', { name: this.name });
    }
    // 切れたら、5秒ごとにつなぎ直す（近づけば戻る）
    async reconnect() {
      if (this.reconnecting) return;
      this.reconnecting = true;
      while (this.device && !this.connected) {
        await new Promise((r) => setTimeout(r, 5000));
        try { await this.open(); } catch {}
      }
      this.reconnecting = false;
    }
    // 11/15：基板へ送る行は、届いたと返事のある送り方（writeValue）で、1つずつ順に送る。だめなら 0.3秒あけて3回まで。
    //   前は返事のない送り方で、本体2台もつないで Bluetooth が混むと「REC 0」が届かず、録音が止まらないことがあった
    send(line) {
      const data = new TextEncoder().encode(line + '\n');
      const job = this.q.then(async () => {
        for (let i = 0; i < 3; i++) {
          if (!this.rx) return false;
          // 11/15 朝：返事が来ないまま止まると、後の行がずっと送れなくなる（REC 1 が届かず録れなかった）。2秒で見切る
          try { await Promise.race([this.rx.writeValue(data), new Promise((_, no) => setTimeout(() => no(new Error('timeout')), 2000))]); return true; } catch { await new Promise((r) => setTimeout(r, 300)); }
        }
        return false;
      });
      this.q = job.catch(() => false);
      return job;
    }
    // 11/15 朝：基板が返事をしなくなった（Bluetooth が混んで、送る途中で止まったまま）。いったん切ってつなぎ直す（5秒ほどで戻る）
    kick() {
      this.q = Promise.resolve(); this.take = null; this.buf = new Uint8Array(0);
      try { if (this.device && this.device.gatt.connected) this.device.gatt.disconnect(); } catch {}
    }
    // 11/15：録っている途中の声を、そこまでで受けとる（「おわり」が届かないとき、捨てずに文字にするため）
    takeSoFar() {
      const t = this.take; this.take = null;
      if (!t) return null;
      const n = t.chunks.reduce((s, c) => s + c.length, 0), samples = new Float32Array(n);
      let o = 0; for (const c of t.chunks) { samples.set(c, o); o += c.length; }
      return { samples, rate: t.rate, lost: t.lost };
    }
    rec(on) { return this.send(on ? 'REC 1' : 'REC 0'); }

    // 届いたバイトをためて、まとまりごとに読む
    feed(bytes) {
      const b = new Uint8Array(this.buf.length + bytes.length);
      b.set(this.buf); b.set(bytes, this.buf.length);
      let p = 0;
      while (b.length - p >= 5) {
        if (b[p] !== 0xA5 || b[p + 1] !== 0x5A) { p++; continue; } // 頭の印を探す
        const type = b[p + 2], len = b[p + 3] | (b[p + 4] << 8);
        if (b.length - p < 5 + len) break; // まだ全部届いていない
        this.frame(type, b.subarray(p + 5, p + 5 + len));
        p += 5 + len;
      }
      this.buf = b.slice(p);
    }
    frame(type, d) {
      const v = new DataView(d.buffer, d.byteOffset, d.byteLength);
      this.lastFrameAt = Date.now();
      if (type === 1) { // はじめ
        this.take = { rate: v.getUint16(0, true), by: d[3], chunks: [], next: 0, lost: 0 };
        this.emit('start', { by: this.take.by });
      } else if (type === 2 && this.take) { // 声
        const seq = v.getUint16(0, true), pred = v.getInt16(2, true), idx = d[4];
        if (seq > this.take.next) { this.take.lost += seq - this.take.next; this.take.chunks.push(new Float32Array((seq - this.take.next) * BLOCK)); } // 抜けたところは無音でうめる
        this.take.next = seq + 1;
        const blk = decodeBlock(d.subarray(5), pred, idx, Math.min(BLOCK, (d.length - 5) * 2));
        this.take.chunks.push(blk);
        { let s = 0; for (let i = 0; i < blk.length; i++) s += blk[i] * blk[i]; this.emit('level', { rms: Math.sqrt(s / Math.max(1, blk.length)) }); } // 11/12：話している間の声の大きさ（右下の火の子が耳をすませて、声に合わせてゆれる）
      } else if (type === 3 && this.take) { // おわり
        const t = this.take; this.take = null;
        const n = t.chunks.reduce((s, c) => s + c.length, 0), samples = new Float32Array(n);
        let o = 0; for (const c of t.chunks) { samples.set(c, o); o += c.length; }
        this.emit('end', { samples, rate: t.rate, reason: d[2], dropped: v.getUint32(3, true), lost: t.lost });
      }
    }
  }
  window.SenseMic = SenseMic;
  window.SenseMicCodec = { decodeBlock }; // 確かめ用
})();
