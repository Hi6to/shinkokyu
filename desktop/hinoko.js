// 火の子のドット絵（右下の小窓と、右の吹き出しの顔で使う）。レトロ版の決まり：白＋濃いふち、色は少しだけ、動くときはまるごと
// drawHinoko(canvas, {
//   stage: 0〜4, mood: 'idle' | 'blow'（そっと吹いている）| 'scatter'（強すぎて火の粉が散る）| 'sleepy',
//   t: ミリ秒, fill: 0〜1（まわりの煙）, pair: null | 0〜1（2台：0＝2つの火がはなれている → 1＝寄って焚き火）,
//   wood: 0〜3（そばに積んだ薪＝もやもや。白い帯＝愚痴の札が巻いてある）, drop: null | { p: 0〜1, text }（札のついた薪が上から落ちてきて積まれる）,
//   flare: 0〜1（炎がぐっと大きくなって戻る。0.3 から）, burn: { p: 0〜1, text }（もやもやの薪をくべる：火の子の真下へ飛ぶ → 火がつく → ぼっ。札の言葉は絵の上に）,
//   burstRing: { n, q }（薪が燃えて、熾火が一気に飛び出す。一服の外のとき）,
//   camp: 0〜（焚き火のまわりにふえた物の数）, span: 決まった範囲のマス数,
//   embers: 0〜（残り火：この一服で吹いた息の数。長い息は2つ。火のまわりの輪に熾火がふえる。20まで）, emberFly: 0〜1（一服が終わって、熾火がうずを巻いて火へ吸いこまれる）,
//   emberSpawn: 0〜1（新しい熾火が火から飛び出すところ）, emberFrom: この番号から先が新しい熾火, emberHot: true（吹いている間は熾火が明るい）, emberT: 輪の回りぐあいに使う時間,
//   charge: 0〜1（炎をこの大きさ以上にしておく。ためきった所で止めるときに使う）, mega: 0〜1（炎の大きくなり方を大げさに：残り火を吸いこんだとき）,
//   emberOut: 1〜（熾火の輪を少し広げる：吸いこむ前の「ため」）, suck: 0〜1（集中線）, shock: 半径（衝撃の輪）, wobble: 0〜1（炎の先を左右に大きくふる）,
//   11/12 追加：mood 'happy'（目が ^ ^。もやもやの薪を食べてうれしい）| 'listen'（耳をすます：声の波が左から届く）| 'think'（言葉にしている：上に「…」）,
//   voice: 0〜1（話している声の大きさ。炎が声に合わせてゆれる）, hop: 0〜1（ぴょんとはねる）,
//   onFire: { fly: 0〜1, lit: 0〜1 }（曲を吹いている間、もやもやの薪が火の真下で、曲の進みに合わせて左から燃えていく）,
//   stamp: { i, q: 0〜1 }（積んだ i 本目の薪に、言葉が焼き印のように押される：帯が橙に光って白に戻る） }
//   戻り値：{ ox, oy, px }（マス (x, y) は canvas の (ox + x*px, oy + y*px)。言葉や火の粉を、絵の上の別の層に重ねるのに使う）
(function () {
  const COL = { o: '#0b0d12', w: '#f2f4f8', y: '#ffe08a', r: '#ff9b54', s: '#c9ced8', m: '#e9d9a6', g: '#a9b3c6', b: '#8a6240', k: '#0b0d12', p: '#ffd36e' };
  let MEGA = 0; // 0〜1：残り火を吸いこんだときだけ、炎の大きくなり方を大げさにする（ふだんの薪は 0）
  let WOBBLE = 0; // 0〜1：炎の先を左右に大きくふる（残り火を吸いこんで「どん」のとき）
  let VOICE = 0;  // 0〜1：話している声の大きさ（耳をすましている間、炎が声に合わせてのびる）
  const set = (g, x, y, c) => g.set(`${Math.round(x)},${Math.round(y)}`, c);
  const put = (g, x, y, c) => { const k = `${Math.round(x)},${Math.round(y)}`; if (!g.has(k)) g.set(k, c); }; // 空いている所だけ
  const rect = (g, x0, y0, x1, y1, c) => { for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) set(g, x, y, c); };

  // 炎の形：下は丸く、上はとがる。tip は先のゆれ（左右のずれ）。hot（0〜1）は薪をくべた勢い：黄色と橙の所が広がる
  function flame(g, cx, bottom, w, h, tip, mood, hot = 0) {
    const r = w / 2, cy = bottom - r, top = bottom - h + 1;
    for (let y = top; y <= bottom; y++) {
      let hw, c = cx;
      if (y >= cy) hw = Math.sqrt(Math.max(0, r * r - (y - cy) * (y - cy)));
      else { const k = (y - top) / Math.max(1, cy - top); hw = r * Math.pow(Math.max(0, k), 1.25); c = cx + tip * Math.pow(1 - k, 2); }
      for (let x = Math.round(c - hw); x <= Math.round(c + hw); x++) {
        const d = Math.abs(x - c) / Math.max(0.5, hw), v = (y - (bottom - h)) / h;
        let col = 'w';
        if (v > 0.35 - hot * 0.2 && d < 0.72 + hot * 0.12) col = mood === 'sleepy' ? 'm' : 'y';
        if (v > 0.6 - hot * 0.2 && d < 0.42 + hot * 0.15) col = 'r';
        if (mood === 'sleepy' && col === 'w') col = 's';
        set(g, x, y, col);
      }
    }
  }
  function eyes(g, cx, y, gap, mood) {
    for (const s of [-1, 1]) {
      const x = Math.round(cx + s * gap);
      if (mood === 'sleepy') { set(g, x, y + 1, 'k'); set(g, x + s, y + 1, 'k'); }   // うとうと：横の線
      else if (mood === 'happy') { set(g, x, y, 'k'); set(g, x - 1, y + 1, 'k'); set(g, x + 1, y + 1, 'k'); } // うれしい：^ ^
      else if (mood === 'listen') { set(g, x - 1, y, 'k'); set(g, x - 1, y + 1, 'k'); }                        // 耳をすます：左（声のする方）を見る
      else if (mood === 'think') { set(g, x + 1, y - 1, 'k'); set(g, x + 1, y, 'k'); }                         // 考えている：右上を見る
      else if (mood === 'scatter') { set(g, x, y, 'k'); set(g, x + s, y + 1, 'k'); }  // 強すぎ：目をぎゅっと
      else { set(g, x, y, 'k'); set(g, x, y + 1, 'k'); }                              // ふつう：たての点
    }
  }
  function logs(g, w, y) { for (let i = -w; i <= w; i++) { const d = Math.round(i * 0.25); set(g, i, y + d, 'b'); set(g, i, y - d, 'b'); set(g, i, y + 1 + d, 'b'); set(g, i, y + 1 - d, 'b'); } }
  // 火の粉：そっと＝まっすぐ上へ、強すぎ＝左右に散って落ちる
  function sparks(g, t, top, n, mood) {
    if (mood === 'scatter') {
      for (let i = 0; i < 8; i++) {
        const k = ((t / 70 + i * 2.3) % 8) / 8, a = (i / 8) * Math.PI * 2;
        set(g, Math.cos(a) * (4 + k * 9), top + 6 + Math.sin(a) * 3 + k * k * 6, 'p');
      }
      return;
    }
    for (let i = 0; i < n; i++) { const k = (Math.floor(t / 120) + i * 3) % 6; set(g, [-4, 3, -2, 5][i % 4], top - k, 'p'); }
  }
  // 薪をくべたとき：火の粉が勢いよく、たくさん噴き上がる
  function burst(g, t, top, b) {
    const n = Math.round(b * 8);
    for (let i = 0; i < n; i++) { const k = ((t / 45 + i * 1.9) % 7) / 7; set(g, [-5, -2, 1, 4, -4, 3, -1, 5][i] * (0.5 + k * 0.8), top - 1 - k * 8, i % 2 ? 'p' : 'y'); }
  }

  // ひとりの火（段ごと）。boost（0〜1）＝薪をくべて炎が大きくなっている度合い
  function single(stage, mood, t, boost) {
    const g = new Map();
    const fast = mood === 'blow' || mood === 'scatter' || mood === 'happy' || (mood === 'listen' && VOICE > 0.3), f = Math.floor(t / (fast ? 90 : 220)) % 4;
    const tip = WOBBLE > 0 ? Math.round(WOBBLE * [5, -5, 4, -4][Math.floor(t / 60) % 4]) : mood === 'scatter' ? [2, -2, 1, -1][f] : [0, 1, 0, -1][f];
    const grow = mood === 'blow' || mood === 'happy' ? 2 : mood === 'listen' ? Math.round(VOICE * 3) : mood === 'sleepy' || mood === 'scatter' ? -1 : 0;
    const bh = Math.round(boost * (6 + 7 * MEGA)), bw = Math.round(boost * (2 + 4 * MEGA));
    let top;
    if (stage === 0) {           // 火種：炭の上に小さな火
      rect(g, -3, 0, 3, 2, 'r'); rect(g, -2, -1, 2, -1, 'r'); set(g, -1, 1, 'y'); set(g, 1, 0, 'y');
      flame(g, 0, -2, 3 + (mood === 'blow' || mood === 'happy' ? 2 : 0) + bw * 2, 3 + grow + (mood === 'blow' || mood === 'happy' ? 1 : 0) + bh, tip, mood, boost); eyes(g, 0, 0, 1.5, mood); top = -5 - bh;
    } else if (stage === 1) {    // ちび火
      flame(g, 0, 4, 7 + bw, 10 + grow + bh, tip, mood, boost); eyes(g, 0, 0, 1.6, mood); top = -8 - bh;
    } else if (stage === 2) {    // 灯：ろうそくの上
      flame(g, 0, 2, 9 + bw, 12 + grow + bh, tip, mood, boost); eyes(g, 0, -2, 2, mood); rect(g, -2, 3, 2, 7, 'w'); top = -11 - bh;
    } else if (stage === 3) {    // ランタン：枠の中の火（くべたときは、枠のまわりに光がもれる）
      flame(g, 0, 3, 7 + Math.min(bw, 2), 9 + grow + Math.min(bh, 2), tip, mood, boost); eyes(g, 0, -1, 1.6, mood);
      for (let y = -7; y <= 5; y++) { set(g, -6, y, 'g'); set(g, 6, y, 'g'); }
      rect(g, -6, -8, 6, -8, 'g'); rect(g, -6, 6, 6, 7, 'g'); rect(g, -2, -10, 2, -10, 'g'); set(g, -3, -9, 'g'); set(g, 3, -9, 'g'); top = -11;
      if (boost > 0) for (const [x, y] of [[-8, -4], [-9, -4], [8, -4], [9, -4], [-8, 1], [-9, 2], [8, 1], [9, 2], [0, -12], [0, -13]]) set(g, x, y, 'p');
    } else {                     // 焚き火：交差した薪の上の大きな火
      flame(g, 0, 2, 13 + bw, 15 + grow + bh, tip, mood, boost); eyes(g, 0, -3, 2.6, mood); logs(g, 7, 4); top = -14 - bh;
    }
    if (boost > 0) burst(g, t, top, boost);
    else if (mood === 'blow' || mood === 'scatter' || mood === 'happy' || stage === 4) sparks(g, t, top, mood === 'blow' || mood === 'happy' ? 4 : 2, mood);
    g.top = top;
    return g;
  }
  // ふたりの火（2台）：k＝0 ではなれた2つの小さな火 → 1 で寄って、顔が2つの大きな焚き火
  function pair(k, mood, t, boost) {
    const g = new Map();
    const f = Math.floor(t / (mood === 'blow' ? 90 : 220)) % 4, tip = WOBBLE > 0 ? Math.round(WOBBLE * [5, -5, 4, -4][Math.floor(t / 60) % 4]) : [0, 1, 0, -1][f], grow = mood === 'blow' ? 2 : 0;
    const bh = Math.round(boost * (6 + 7 * MEGA)), bw = Math.round(boost * (2 + 4 * MEGA));
    if (k < 1) {
      const d = 2.5 + 5 * (1 - k);
      for (const s of [-1, 1]) { flame(g, s * d, 4, 7 + bw, 9 + grow + bh, -s * tip, mood, boost); eyes(g, s * d, 0, 1.6, mood); }
      if (boost > 0) burst(g, t, -8 - bh, boost); else sparks(g, t, -8, 3, 'blow');
    } else {
      flame(g, 0, 2, 15 + bw, 16 + grow + bh, tip, mood, boost); eyes(g, -4, -3, 1, mood); eyes(g, 4, -2, 1, mood); logs(g, 8, 4); // 顔が2つ（高さを少しずらして、2人とわかるように）
      if (boost > 0) burst(g, t, -15 - bh, boost); else sparks(g, t, -15, 4, 'blow');
    }
    return g;
  }
  // 残り火（11/11 改）：吹いた息ごとに、火のまわりの輪に熾火（2×2 の橙と黄のかたまり）が1つずつふえる。
  //   輪はゆっくり回る。新しい熾火は火の中から飛び出して、輪の空いた所へ（spawn 0〜1）。
  //   fly（0〜1）：一服が終わって、熾火が1つずつ、うずを巻きながら火へ吸いこまれる（着いた数だけ炎がためる）
  const EMBER_MAX = 20, ER_X = 12, ER_Y = 10, EC_Y = -3, GOLD = 2.39996; // 黄金角でまわりに散らして、数が少なくても片よらない
  const emberStagger = (n) => Math.min(0.07, 0.55 / Math.max(1, n));
  function emberArrived(n, fly) { // 火に着いた割合（0〜1）
    n = Math.min(EMBER_MAX, n); if (!n || fly <= 0) return 0;
    const s = emberStagger(n), d = 1 - (n - 1) * s; let a = 0;
    for (let i = 0; i < n; i++) if ((fly - i * s) / d >= 1) a++;
    return a / n;
  }
  function blob(g, x, y, i, t, hot, small) {
    const f = (Math.floor(t / 180) + i) % 4;
    const a = hot || f === 0 ? 'y' : 'r', b = hot ? (f % 2 ? 'p' : 'r') : f === 2 ? 'y' : 'r'; // 11/11：白は使わない（火の色だけ）
    put(g, x, y, a);
    if (small) return;
    put(g, x + 1, y, b); put(g, x, y + 1, 'r'); put(g, x + 1, y + 1, a);
  }
  function embers(g, n, t, fly, o, fx) {
    n = Math.min(EMBER_MAX, n);
    const spin = (o.emberT != null ? o.emberT : t) / 2600, s = emberStagger(n), d = 1 - (n - 1) * s, out = o.emberOut || 1;
    for (let i = 0; i < n; i++) {
      const raw = fly > 0 ? (fly - i * s) / d : 0, p = Math.max(0, Math.min(1, raw));
      if (p >= 1) { if (raw < 1.12) pop(fx, raw); continue; } // もう火に入った（入った瞬間だけ、火の中心がぱっと光る）
      const at = (p) => { const ang = i * GOLD + spin + p * p * Math.PI * 1.6, r = (1 - p * p * (3 - 2 * p)) * out; return [Math.cos(ang) * ER_X * r, EC_Y + Math.sin(ang) * ER_Y * r]; }; // うずを巻いて、なめらかに輪から火の中心へ
      let [x, y] = at(p);
      if (p > 0.03) for (const [dp, c] of [[0.06, 'y'], [0.13, 'r'], [0.2, 'r'], [0.28, 'p']]) { const [tx, ty] = at(Math.max(0, p - dp)); put(fx, Math.round(tx), Math.round(ty), c); } // 尾：通ってきた所に、長い火の粉の線
      y += ((Math.floor(t / 400) + i) % 2) * (p ? 0 : 1) * 0.6;  // 輪にいる間は、ふわふわ上下
      let small = p > 0.55;
      const from = Math.min(o.emberFrom != null ? o.emberFrom : n - 1, n - 1); // この息でふえた熾火（2つのときは少しずらして）
      const q = o.emberSpawn != null && i >= from ? Math.max(0, Math.min(1, o.emberSpawn * 1.3 - (i - from) * 0.3)) : 1;
      if (q < 1) { // 新しい熾火：火の中からぽんと飛び出す
        const e = 1 - (1 - q) * (1 - q);
        x = x * e; y = (EC_Y - 2) + (y - (EC_Y - 2)) * e - Math.sin(Math.PI * q) * 4;
        small = q < 0.5;
      }
      blob(g, Math.round(x), Math.round(y), i, t, o.emberHot || fly > 0, small);
    }
  }
  // 熾火が火に入った瞬間：火の中心に、小さな輪がぱっと出る
  function pop(fx, raw) {
    const r = 1 + Math.round((raw - 1) * 25);
    for (let a = 0; a < 8; a++) put(fx, Math.round(Math.cos(a * Math.PI / 4) * r), Math.round(EC_Y + Math.sin(a * Math.PI / 4) * r), r <= 2 ? 'y' : 'p');
  }
  // 吸いこむ間の「集中線」：まわりから火へ向かう線が、内へ内へ流れる（マンガの集中線のように、吸いこまれる向きを見せる）
  function suckLines(fx, t, k) {
    const N = 14;
    for (let i = 0; i < N; i++) {
      if ((i * 7 + Math.floor(t / 110)) % 5 === 0) continue;     // ところどころ消えて、ちらつく
      const a = (i / N) * Math.PI * 2 + (i % 2) * 0.12, len = 3 + (i % 3);
      const r0 = 22 - ((t / 40 + i * 5) % 9);                    // 外から内へ流れる
      for (let j = 0; j < len; j++) {
        const r = r0 - j; if (r < 8) break;
        put(fx, Math.round(Math.cos(a) * r * 1.1), Math.round(EC_Y + Math.sin(a) * r), j === 0 ? (k > 0.5 ? 'y' : 'p') : 'r'); // 火の色の線（先は明るく）
      }
    }
  }
  // 衝撃の輪：ためきった火が「どん」と大きくなるとき、火の中心から輪が広がる（r＝半径のマス数）
  function shock(fx, r) {
    const n = Math.max(12, Math.round(r * 6));
    for (let i = 0; i < n; i++) { const a = (i / n) * Math.PI * 2; put(fx, Math.round(Math.cos(a) * r * 1.15), Math.round(EC_Y + Math.sin(a) * r), r < 9 ? 'y' : r < 14 ? 'p' : 'r'); }
  }
  // そばに積んだ薪（もやもや）：左下に、横に寝かせた丸太を下から積む
  const woodAt = (i) => [-14 + (i % 2), 6 - i * 2];
  const logAt = (g, x0, y, f = put) => { for (let k = 0; k < 5; k++) f(g, x0 + k, y, k === 4 ? 'm' : k === 2 ? 'w' : 'b'); }; // まん中の白い帯＝愚痴の札
  function wood(g, n, stamp, t) {
    for (let i = 0; i < Math.min(3, n); i++) {
      const [x0, y] = woodAt(i); logAt(g, x0, y);
      if (stamp && stamp.i === Math.min(2, i) && stamp.q < 1) { // 焼き印：帯が橙・黄にちらちら光って、白に戻る
        const q = stamp.q, c = q < 0.5 ? ((Math.floor(t / 70) % 2) ? 'y' : 'r') : q < 0.8 ? 'r' : 'm';
        set(g, x0 + 1, y, c); set(g, x0 + 2, y, c); set(g, x0 + 3, y, q < 0.5 ? 'r' : 'b');
      }
    }
  }
  // 曲を吹いている間：もやもやの薪が、積んだ所から火の真下へ（fly）→ 曲の進みに合わせて左から燃えていく（lit）
  function onFireLog(g, fx, i, o, t, stage) {
    const by = BURN_Y[Math.max(0, Math.min(4, stage))];
    const q = Math.max(0, Math.min(1, o.fly)), e = q * q * (3 - 2 * q), [x0, y0] = woodAt(Math.min(2, i));
    const x = Math.round(x0 + (-3 - x0) * e), y = Math.round(y0 + (by - y0) * e - Math.sin(Math.PI * q) * 2);
    const lit = q < 1 ? 0 : Math.ceil(Math.max(0, Math.min(1, o.lit)) * 7);
    bigLog(g, x, y, lit, t);
    for (let k = 0; k < Math.min(7, lit); k++) if ((Math.floor(t / 90) + k) % 2) put(fx, x + k, y - 1 - ((Math.floor(t / 90) + k) % 3 === 0 ? 1 : 0), (k + Math.floor(t / 90)) % 2 ? 'y' : 'r'); // 燃えている所の上に、小さな炎の舌
    if (lit > 0 && lit < 7) put(fx, x + lit, y - 1, 'p'); // 火の先（燃え進んでいる所）
  }
  // 耳をすます：声の波（弧）が、左から火へ届く。声が大きいほど多く、明るく
  function listenWaves(fx, t, v) {
    const n = 1 + Math.round(v * 2);
    for (let j = 0; j < n; j++) {
      const r = 14 - ((t / 90 + j * 4) % 10);
      for (let a = -3; a <= 3; a++) { const ang = Math.PI + a * 0.16; put(fx, Math.round(Math.cos(ang) * r * 1.1), Math.round(EC_Y + Math.sin(ang) * r), v > 0.5 && j === 0 ? 'y' : 'g'); }
    }
  }
  // 考えている：火の上に「…」が1つずつ出る
  function thinkDots(fx, t, top) { const n = Math.floor(t / 300) % 4; for (let i = 0; i < n; i++) put(fx, -2 + i * 2, top - 3, 'y'); }
  // くべる薪（11/11 改）：積んだ所から弧をえがいて、火の子の「真下」へ（火に重ねない）→ 火がついてちらちら → ぼっ（燃えつきる）
  //   p：0〜0.3 飛ぶ／0.3〜0.5 真下で火がつく／0.5〜 ぼっ（薪は消えて、炎が大きくなる）
  const BURN_AT = 0.5;
  const BURN_Y = [3, 5, 8, 8, 7]; // 段ごとの、火の根もとのすぐ下（太い薪の上の行）
  // 太い薪（7×2マス）。まん中の白い帯＝愚痴の札。lit：左から何マス火がまわったか
  function bigLog(g, x0, y0, lit, t) {
    for (let x = 0; x < 7; x++) for (let r = 0; r < 2; r++) {
      const on = x < lit;
      set(g, x0 + x, y0 + r, on ? ['r', 'y', 'r', 'p'][(Math.floor(t / 70) + x + r) % 4] : x === 3 ? 'w' : x === 0 || x === 6 ? 'm' : 'b');
    }
  }
  function burningLog(g, fx, i, p, t, stage) {
    if (p >= BURN_AT) return;
    const by = BURN_Y[Math.max(0, Math.min(4, stage))];
    if (p < 0.3) { // 積んだ所から、弧をえがいて火の子の真下へ
      const q = p / 0.3, e = q * q * (3 - 2 * q), [x0, y0] = woodAt(Math.min(2, i));
      bigLog(g, Math.round(x0 + (-3 - x0) * e), Math.round(y0 + (by - y0) * e - Math.sin(Math.PI * q) * 2), 0, t); // 地面をすべるように（火に重ならない高さで）
      return;
    }
    const k = (p - 0.3) / (BURN_AT - 0.3); // 0〜1：火が左から右へまわっていく
    const lit = Math.ceil(k * 8);
    bigLog(g, -3, by, lit, t);
    for (let x = 0; x < Math.min(7, lit); x++) if ((Math.floor(t / 90) + x) % 2) put(fx, -3 + x, by - 1 - ((Math.floor(t / 90) + x) % 3 === 0 ? 1 : 0), (x + Math.floor(t / 90)) % 2 ? 'y' : 'r'); // 薪の上に、小さな炎の舌
  }
  // 薪が燃えたときに、火から一気に飛び出す熾火（一服の外で燃えたとき用：飛び出して、少しして上へ消えていく）。q＝0〜1
  function burstRing(g, n, q, t) {
    for (let i = 0; i < n; i++) {
      const out = Math.min(1, q / 0.2), e = 1 - (1 - out) * (1 - out), ang = i * GOLD + 0.7;
      let x = Math.cos(ang) * ER_X * e, y = EC_Y - 2 + (Math.sin(ang) * ER_Y + 2) * e;
      if (q > 0.6) { y -= (q - 0.6) * 30; if (y < -20 || (q > 0.85 && (Math.floor(t / 80) + i) % 2)) continue; } // 上へのぼって、ちらちら消える
      blob(g, Math.round(x), Math.round(y), i, t, true, q > 0.75);
    }
  }
  // 札のついた薪が、上から落ちてきて積まれる（0〜0.35 で落ちる → 小さくはねる → 止まる）
  function droppingLog(g, i, p) {
    const [x0, y1] = woodAt(Math.min(2, i)), y0 = -20;
    const y = p < 0.35 ? y0 + (y1 - y0) * (p / 0.35) * (p / 0.35) : p < 0.45 ? y1 - 1 : y1;
    logAt(g, x0, y, set);
    return [x0 + 2, y];
  }
  // C：焚き火のまわり（1本ごとに1つふえる。減らない）。石の輪 → 丸太のいす → やかん → 月 → テント → ほたる → 夜空の星
  const STARS = [[-9, -19], [10, -20], [12, -16], [-6, -21], [13, -21], [-11, -12], [7, -18], [-2, -22], [3, -21], [-13, -8], [13, -10], [-7, -16], [6, -21], [0, -20], [-12, -16], [11, -13]];
  function camp(g, n, t) {
    if (n >= 1) for (const x of [-8, -7, -3, -2, 2, 3, 7, 8]) put(g, x, 8, 's');                                          // 石の輪
    if (n >= 2) for (let x = 10; x <= 13; x++) { put(g, x, 6, x === 13 ? 'm' : 'b'); put(g, x, 7, x === 13 ? 'm' : 'b'); } // 丸太のいす（右下）
    if (n >= 3) { put(g, 11, 2, 's'); for (let x = 10; x <= 12; x++) { put(g, x, 3, 's'); put(g, x, 4, 's'); put(g, x, 5, 's'); } put(g, 9, 3, 's'); put(g, 11, 4, 'g'); } // やかん（いすの上。銀色、左に注ぎ口）
    if (n >= 4) for (const [x, y] of [[-12, -21], [-11, -21], [-13, -20], [-13, -19], [-13, -18], [-12, -17], [-11, -17]]) put(g, x, y, 'y'); // 月（左上）
    if (n >= 5) { put(g, -12, -5, 'm'); for (let y = -4; y <= -3; y++) for (let x = -13; x <= -11; x++) put(g, x, y, 'm'); for (let y = -2; y <= -1; y++) for (let x = -14; x <= -10; x++) put(g, x, y, x === -12 ? 'k' : 'm'); } // テント（左、薪の上）
    if (n >= 6) { const b = Math.floor(t / 500) % 2; put(g, b ? -9 : -8, -7 + b, 'p'); put(g, b ? 10 : 11, -9 - b, 'p'); }  // ほたる（ふわふわ）
    const tw = Math.floor(t / 700);
    for (let i = 0; i < Math.min(STARS.length, n - 6); i++) put(g, STARS[i][0], STARS[i][1], i === tw % Math.max(1, n - 6) ? 'w' : 'y'); // 星（1つずつ、またたく）
  }
  // まわりの煙：たまり具合で数が増える、まるい灰色のかたまり（焚き火のまわりの物がある所は、なるべく避ける）
  const PUFF = [[0, -1], [1, -1], [2, -1], [-1, 0], [0, 0], [1, 0], [2, 0], [3, 0], [0, 1], [1, 1], [2, 1]]; // よこ長の丸
  function smoke(g, fill, t) {
    const n = Math.round(fill * 7), spots = [[-12, -9], [10, -6], [-9, -15], [10, -13], [-4, -20], [5, -20], [0, -22]];
    for (let i = 0; i < n; i++) {
      const [sx, sy] = spots[i], dy = (Math.floor(t / 700) + i) % 2;
      for (const [x, y] of PUFF) put(g, sx + x, sy + y - dy, 'g');
    }
  }
  // ふち：塗った所のとなりの空いたマスを濃い色に。うとうとのときは z
  function finish(g, mood, t, zx, zy) {
    const out = new Map(g);
    for (const key of g.keys()) {
      const [x, y] = key.split(',').map(Number);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const k2 = `${x + dx},${y + dy}`; if (!g.has(k2)) out.set(k2, 'o'); }
    }
    if (mood === 'sleepy') { const zz = Math.floor(t / 600) % 2; for (const [x, y] of [[0, 0], [1, 0], [2, 0], [3, 0], [2, 1], [1, 2], [0, 3], [1, 3], [2, 3], [3, 3]]) out.set(`${zx + x},${zy + y - zz}`, 'g'); }
    return out;
  }

  function tag(ctx, canvas, text, x, y, hot) {
    const fs = 10;
    ctx.font = `${fs}px "DotGothic16", "MS Gothic", monospace`;
    const w = Math.ceil(ctx.measureText(text).width) + 6, h = fs + 5;
    x = Math.max(2, Math.min(canvas.width - w - 2, Math.round(x - w / 2))); y = Math.max(2, Math.round(y - h));
    ctx.fillStyle = '#0b0d12'; ctx.fillRect(x - 1, y - 1, w + 2, h + 2);
    ctx.fillStyle = hot ? '#ff9b54' : '#f2f4f8'; ctx.fillRect(x, y, w, h);
    ctx.fillStyle = '#0b0d12'; ctx.textBaseline = 'middle'; ctx.fillText(text, x + 3, y + h / 2 + 1);
  }
  window.drawHinoko = function (canvas, o = {}) {
    const ctx = canvas.getContext('2d'), t = o.t || 0, stage = o.stage || 0, fl = o.flare || 0, bn = o.burn ? o.burn.p : -1;
    // 薪をくべる：0〜0.3 で飛んでいき、着いたらぐっと大きく（すぐ最大）→ ゆっくり戻る。カクッと4段で
    const q = fl >= 0.3 ? (fl - 0.3) / 0.7 : -1;
    MEGA = Math.max(0, Math.min(1, o.mega || 0)); WOBBLE = Math.max(0, Math.min(1, o.wobble || 0)); VOICE = Math.max(0, Math.min(1, o.voice || 0));
    if (o.mood === 'listen' && VOICE > 0.15) WOBBLE = Math.max(WOBBLE, VOICE * 0.45); // 声に合わせて、炎の先がゆれる
    // 薪がぼっと燃えたとき：炎が一気に大きく（ふだんより大げさに）→ ゆっくり戻る。炎の先も左右にふれる
    let burnBoost = 0, burnQ = -1;
    if (bn >= 0.3) {
      if (bn < 0.5) burnBoost = 0.125;                                                     // 火がついた：少しだけふくらむ
      else { burnQ = (bn - 0.5) / 0.5; burnBoost = burnQ < 0.08 ? burnQ / 0.08 : 1 - (burnQ - 0.08) / 0.92; MEGA = Math.max(MEGA, 0.55); WOBBLE = Math.max(WOBBLE, 0.8 * Math.max(0, 1 - burnQ * 1.6)); }
    }
    let boost = q < 0 ? 0 : Math.round((q < 0.12 ? q / 0.12 : 1 - (q - 0.12) / 0.88) * (MEGA ? 8 : 4)) / (MEGA ? 8 : 4);
    // 残り火が火に入るごとに、炎がためこんで大きくなる（全部入ると 0.6。そのあとの「どん」は flare で 1 に）
    if (o.embers && o.emberFly > 0) boost = Math.max(boost, Math.round(emberArrived(o.embers, o.emberFly) * 0.6 * 8) / 8);
    if (o.charge) boost = Math.max(boost, o.charge);
    if (burnBoost) boost = Math.max(boost, Math.round(burnBoost * 8) / 8);
    const fx = new Map(); // ふちを付けない光の線（尾・集中線・衝撃の輪）。絵の位置合わせにも使わない
    const mood = boost > 0 && o.mood !== 'scatter' && o.mood !== 'happy' ? 'blow' : o.mood || 'idle'; // くべたら、うとうとも目がさめる（うれしい顔はそのまま）
    const g = o.pair != null ? pair(o.pair, mood, t, boost) : single(stage, mood, t, boost);
    if (o.camp) camp(g, o.camp, t);
    const gTop = g.top != null ? g.top : -10; // 炎のいちばん上（「…」を出す高さ）
    if (o.wood) wood(g, o.wood, o.stamp, t);
    if (o.onFire) onFireLog(g, fx, o.wood || 0, o.onFire, t, o.pair != null ? 4 : stage);
    if (mood === 'listen') listenWaves(fx, t, VOICE);
    if (mood === 'think') thinkDots(fx, t, gTop);
    if (o.embers) embers(g, o.embers, t, o.emberFly || 0, o, fx);
    if (o.suck) suckLines(fx, t, o.suck);
    if (o.shock) shock(fx, o.shock);
    if (o.burn) burningLog(g, fx, o.wood || 0, bn, t, o.pair != null ? 4 : stage);
    if (burnQ >= 0 && burnQ < 0.35) shock(fx, 2 + (burnQ / 0.35) * 15); // ぼっ：火の中心から輪が広がる
    if (o.burstRing) burstRing(g, o.burstRing.n, o.burstRing.q, t);
    let tagAt = null, tagHot = false, tagTop = false;
    // くべる薪の札の言葉は、火に重ならないように、絵のいちばん上に出す（火がついたら橙に、燃えたらカクカク消える）
    if (bn >= 0 && (bn < 0.45 || (bn < 0.6 && Math.floor(bn * 40) % 3 !== 0))) { tagAt = [0, 0]; tagTop = true; tagHot = bn >= 0.3; }
    if (o.drop) { const at = droppingLog(g, o.wood || 0, o.drop.p); if (o.drop.p < 0.9) tagAt = at; }
    const tagText = o.drop ? o.drop.text : o.burn ? o.burn.text : o.flareText;
    if (o.fill) smoke(g, Math.max(0, Math.min(1, o.fill)), t);
    const big = o.pair === 1 || stage === 4;
    const out = finish(g, mood, t, big ? 9 : 6, big ? -18 : -9);
    let y1 = -Infinity;
    for (const k of out.keys()) y1 = Math.max(y1, +k.split(',')[1]);
    // 段が変わっても大きさがはねないように、マスの大きさは決まった範囲で決める（左右は真ん中、下はそろえる。石の輪の下まで入るように 9 にそろえる）
    const span = o.span || 26, px = Math.max(1, Math.floor(Math.min(canvas.width, canvas.height) / span));
    const ox = Math.round(canvas.width / 2), oy = Math.round(canvas.height - (Math.max(y1, 9) + 1.5) * px) - (o.hop ? Math.round(Math.max(0, Math.min(1, o.hop)) * 2) * px : 0); // hop：ぴょんとはねる
    for (const [k, col] of fx) if (!out.has(k)) out.set(k, col); // 光の線は、絵の空いている所にだけ
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const [k, col] of out) { const [x, y] = k.split(',').map(Number); ctx.fillStyle = COL[col]; ctx.fillRect(ox + x * px, oy + y * px, px, px); }
    if (tagAt && tagText) tag(ctx, canvas, tagText, tagTop ? canvas.width / 2 : ox + (tagAt[0] + 0.5) * px, tagTop ? 18 : oy + (tagAt[1] - 1) * px, tagHot); // 札の言葉（席にいないときなど、言葉を出さない設定のときは届かない）
    return { ox, oy, px };
  };
  window.HINOKO = { woodAt, BURN_Y }; // 11/12：言葉の層（gauge.html）が、薪の場所を知るため
})();
