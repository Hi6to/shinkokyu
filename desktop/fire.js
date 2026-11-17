// 火の子（11/08）：一服で育つアバター。画面の右下（煙メーターの所）にいて、結果は右の吹き出しで知らせる
// 決まり（PRODUCT.md・IDEAS.md の「ゲームではない」を守る）
// - 点数・連続日数・自己ベスト・ランキングは出さない。人と比べない
// - 育ったものは減らない・枯れない（休めなかった日に罪悪感を足さない）
// - 育つのは本体に吹いたときだけ（キーボードの「ためし」では育たない）。そっと長く吐くほど、よくあたたまる
// - 休憩と休憩をつなぐ（11/08）：B＝次の目印（つぎの段まで あと何本ぐらいか）、C＝焚き火に着いたあとは、1本ごとにまわりに物がふえる
const STAGES = [
  { key: 'tane', name: '火種', need: 0 },
  { key: 'chibi', name: 'ちび火', need: 30 },
  { key: 'tomoshibi', name: '灯', need: 90 },
  { key: 'lantern', name: 'ランタン', need: 200 },
  { key: 'takibi', name: '焚き火', need: 380 },
];
const GOOD_SEC = 4;      // この長さ以上の吐く息を「いい息」とする（ゆっくり長く）
const BREATH_MAX = 8;    // 1回の息であたたまる上限（長く吹きすぎを競わせない）
const STRONG_PA = 70;    // 息の強さ（圧の山）がこれ以上は「強すぎ」：火の粉が散って、あまりあたたまらない（ふつうの長い息は 12〜58 Pa。11/07 の記録）
const IPPUKU_BONUS = 8;  // 1曲＝1本を吹きおえたとき
const WOOD = 3;          // もやもや（愚痴のラベル）1つを薪にしたとき
const TOGETHER = 1.5;    // 本体2台以上で一緒に一服したときの倍率（焚き火を囲む）
const PER_IPPUKU = 40;   // 1本であたたまる目安（記録がまだ少ないとき。「あと何本」の見積もりに使う）
// C：焚き火に着いたあと、1本ごとに焚き火のまわりに1つふえる（減らない）。7本目からは夜空の星が1つずつ
const CAMP = ['石の輪', '丸太のいす', 'やかん', '月', 'テント', 'ほたる'];
const CAMP_MAX = CAMP.length + 16; // 星は16個まで（絵の場所の数）。そこから先は、まだ決めていない（ふえない）
const campName = (n) => (n <= CAMP.length ? CAMP[n - 1] : '星');

// 残り火の数（11/11）：0.5秒以上の息で1つ、2.5秒以上のゆっくり長い息なら2つ
const emberGain = (sec) => (sec >= 2.5 ? 2 : sec >= 0.5 ? 1 : 0);

class Fire {
  constructor(load, save) {
    this.s = { warmth: 0, ippuku: 0, together: 0, camp: 0, ...(load() || {}) };
    this.save = save;
    this.sess = null;
  }
  get isNew() { return !this.s.born; }
  born() { this.s.born = Date.now(); this.save(this.s); }
  stageIndex(w = this.s.warmth) { let i = 0; STAGES.forEach((st, k) => { if (w >= st.need) i = k; }); return i; }
  view() {
    const i = this.stageIndex(), cur = STAGES[i], next = STAGES[i + 1];
    return { stage: i, key: cur.key, name: cur.name, next: next ? next.name : null, progress: next ? (this.s.warmth - cur.need) / (next.need - cur.need) : 1, camp: this.s.camp || 0 };
  }
  // B：次の目印。つぎの段まで あと何本ぐらいか（その人の最近の1本のあたたまりで見積もる）／焚き火なら、次にふえる物
  goal() {
    const i = this.stageIndex(), next = STAGES[i + 1];
    if (!next) return (this.s.camp || 0) < CAMP_MAX ? { item: campName((this.s.camp || 0) + 1) } : { full: true };
    const r = this.s.recent || [], avg = r.length >= 2 ? Math.max(10, r.reduce((a, b) => a + b, 0) / r.length) : PER_IPPUKU;
    return { to: next.name, n: Math.max(1, Math.ceil((next.need - this.s.warmth) / avg)) };
  }
  session() {
    if (!this.sess) this.sess = { good: 0, longest: 0, warm: 0, words: 0, strong: 0, device: false, st0: this.stageIndex(), embers: 0 };
    return this.sess;
  }
  // 本体に吹いた息1回。いい息なら、その場で少しあたたまる（右下の火が明るくなる）
  breath(sec, source, peak = 0) {
    this.lastStrong = false;
    // 11/11：曲が終わった瞬間に吹いていた息は、終わった「あと」に届く（吹きおわりで記録されるので）。
    // それで新しい一服を始めてしまうと、残り火が 1 にもどって、火に吸いこまれる演出が止まっていた。
    // 吹きはじめが曲の終わりより前なら、その息は終わった1本のしっぽ：あたたまりはそのまま足すが、新しい一服は始めない
    const tail = !this.sess && this.doneAt && Date.now() - sec * 1000 < this.doneAt + 300;
    // スペースキーの息（11/11）：残り火だけふやす（見せるため）。あたたまり・育ちは本体に吹いたときだけ（キーでは育たない、の決まりはそのまま）
    if (source !== 'device') { if (!tail) this.session().embers += emberGain(sec); return null; }
    const s = tail ? { good: 0, longest: 0, warm: 0, words: 0, strong: 0, embers: 0 } : this.session();
    s.device = true;
    s.longest = Math.max(s.longest, sec);
    // 11/11 残り火：一服の間、吹いた息（0.5秒以上）ごとに、火の子の足元に熾火が1つふえる。一服が終わると火に吸いこまれる（見せ方だけ。あたたまり方は変えない）
    s.embers = (s.embers || 0) + emberGain(sec);
    let pts = 0;
    if (peak >= STRONG_PA) { s.strong++; this.lastStrong = true; pts = sec >= 1.5 ? 1 : 0; } // 強すぎ：火の粉が散る
    else if (sec >= GOOD_SEC) { s.good++; pts = Math.min(BREATH_MAX, Math.round(sec)); }
    else if (sec >= 1.5) pts = 1;
    s.warm += pts;
    return this.add(pts);
  }
  // もやもやを薪にした（吹くと燃える）
  wood(n = 1) { this.session().words += n; }
  // 1曲吹きおえた。together：本体2台以上がつながっていた。本体に吹いていない1本（キーボード）では育たない → null
  done({ together = false } = {}) {
    const s = this.sess;
    this.sess = null;
    this.doneAt = Date.now(); // このあとに届く「しっぽの息」を見分けるため
    if (!s || !s.device) return null;
    let bonus = IPPUKU_BONUS + s.words * WOOD;
    if (together) bonus = Math.round((s.warm + bonus) * (TOGETHER - 1) + bonus);
    this.s.ippuku++;
    if (together) this.s.together++;
    const up = this.add(bonus);
    // C：この1本を始めたときに、もう焚き火だったら、まわりに1つふえる（焚き火に着いた1本は、段が上がったことがごほうび）
    let item = null;
    if (s.st0 === STAGES.length - 1 && (this.s.camp || 0) < CAMP_MAX) { this.s.camp = (this.s.camp || 0) + 1; item = campName(this.s.camp); }
    this.s.recent = [...(this.s.recent || []), s.warm + bonus].slice(-5);
    this.save(this.s);
    return { good: s.good, longest: s.longest, warm: s.warm + bonus, words: s.words, together, up, item };
  }
  abandon() { this.sess = null; }
  // あたためる。段が上がったら、その段を返す
  add(pts) {
    if (!pts) return null;
    const before = this.stageIndex();
    this.s.warmth += pts;
    this.save(this.s);
    const after = this.stageIndex();
    return after > before ? STAGES[after] : null;
  }
}

module.exports = { Fire, STAGES, CAMP, GOOD_SEC, STRONG_PA };
