// 休みどきの理由（口実）を、作業のリズムの記録から短い文にする
// - つづけて作業した時間：5分以上 手が止まった所（または一服の終わり）から数える。
//   厚生労働省のガイドラインの目安は「一連続作業時間が1時間を超えないように、10〜15分の作業休止」
// - ふだんとのちがい：直近15分を、その人のふだん（過去7日の真ん中の値）と比べて、いちばん大きくずれた1つだけを出す
// - 言い方は、見たままの事実だけにする（「集中が落ちている」とは言わない。確かめた判定ではないため）
const BREAK_MIN = 5;        // これだけ手が止まったら、休んだとみなす（分）
const RECENT_MIN = 15;      // 「いま」として見る長さ（分）
const MIN_BASE_ROWS = 60;   // ふだんの値を出すのに要る記録（操作のあった1分の数）
const MIN_RECENT_ROWS = 5;  // いまの値を出すのに要る記録
const SHOW_RATIO = 1.2;     // ふだんの1.2倍以上ずれたら出す
const GUIDE_MIN = 50;       // これを超えたら、国の目安も添える

const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : null; };

// 見る値（どれも「大きいほど、ふだんより乱れている」向き）
const METRICS = [
  { key: 'corr', label: '打ち直し', ok: (r) => r.keys >= 20 && r.corrRate != null, val: (r) => r.corrRate, floor: 0.01 },
  { key: 'pause', label: '手が止まる回数', ok: (r) => r.activeSec >= 10, val: (r) => r.pauses, floor: 0.3 },
  { key: 'iki', label: '打つ間隔のばらつき', ok: (r) => r.keys >= 20 && r.ikiCv != null, val: (r) => r.ikiCv, floor: 0.1 },
  { key: 'mouse', label: 'マウスの迷い', ok: (r) => r.mouseEff != null && r.mouseDist >= 500, val: (r) => 1 - r.mouseEff, floor: 0.03 },
];

// つづけて作業した時間（分）。rows は時間の順、tMs はその1分の終わり
function continuousWork(rows, now, lastBreakAt = 0) {
  let start = null, zeros = 0, prevT = now;
  for (let i = rows.length - 1; i >= 0; i--) {
    const r = rows[i];
    if (r.tMs <= lastBreakAt) break;                           // 一服が終わった所
    if (prevT - r.tMs > (BREAK_MIN + 1) * 60000) break;        // アプリが止まっていた（記録がない）
    prevT = r.tMs;
    if (r.activeSec > 0) { start = r.tMs - 60000; zeros = 0; }
    else if (++zeros >= BREAK_MIN) break;                      // 5分以上、手が止まっていた
  }
  return start ? Math.max(0, Math.round((now - start) / 60000)) : 0;
}

// ふだんとのちがい：いちばん大きいもの1つ（なければ null）
function biggestChange(rows, now) {
  const from = now - RECENT_MIN * 60000;
  const usable = rows.filter((r) => !r.testing && r.activeSec >= 10);
  const base = usable.filter((r) => r.tMs < from), recent = usable.filter((r) => r.tMs >= from);
  if (base.length < MIN_BASE_ROWS) return { best: null, ready: false };
  let best = null;
  for (const m of METRICS) {
    const b = base.filter(m.ok).map(m.val), c = recent.filter(m.ok).map(m.val);
    if (b.length < MIN_BASE_ROWS / 2 || c.length < MIN_RECENT_ROWS) continue;
    const ratio = median(c) / Math.max(median(b), m.floor);
    if (!best || ratio > best.ratio) best = { key: m.key, label: m.label, ratio: +ratio.toFixed(2) };
  }
  return { best: best && best.ratio >= SHOW_RATIO ? best : null, ready: true, top: best };
}

// 通知・煙の画面・操作パネルに出す文
function makeReason(rows, now = Date.now(), lastBreakAt = 0) {
  const minutes = continuousWork(rows, now, lastBreakAt);
  const { best, ready, top } = biggestChange(rows, now);
  const parts = [], lines = [];
  if (minutes >= 10) { parts.push(`${minutes}分つづけて作業しています`); lines.push(`${minutes}分 つづけて 作業しています`); }
  if (best) {
    const x = best.ratio.toFixed(1);
    parts.push(`${best.label}が、ふだんの${x}倍です`);
    lines.push(`${best.label}が ふだんの ${x}倍`);
  }
  if (minutes >= GUIDE_MIN) lines.push('国の目安は 1時間ごとに 10〜15分の休み');
  return {
    minutes, metric: best, top, baselineReady: ready,
    line: parts.join('。'), // 通知の1行
    lines,                  // 煙の画面の窓（短い行）
  };
}

module.exports = { makeReason, continuousWork, biggestChange, BREAK_MIN };
